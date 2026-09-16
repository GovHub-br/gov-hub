{{ config(materialized="table") }}

-- Silver de senado_federal.senadores_historico — verdade única do dado
-- (ADR-0006).
--
-- Granularidade: uma linha por evento de filiação partidária de um senador,
-- restrita a datas de filiação a partir de 1995-01-01 (dado confiável).
--
-- Tipagem portada de data-application-mir
-- (dados_abertos_dbt/bronze/senadores_historico.sql). A coluna
-- 'data_desfiliação' do modelo original foi renomeada para 'data_desfiliacao'
-- (sem acento) para manter o identificador ASCII, consistente com o resto do
-- schema.
with
    bronze as (select * from {{ source("senado_federal", "senadores_historico") }}),

    tipado as (
        select
            parlamentar_id::integer as parlamentar_id,
            partido__codigopartido::text as codigo_partido,
            partido__siglapartido::text as sigla_partido,
            partido__nomepartido::text as nome_partido,
            case
                when lower(trim(datafiliacao::text)) in ('', 'nan', 'null') then null else datafiliacao::timestamptz
            end as data_filiacao,
            case
                when lower(trim(datadesfiliacao::text)) in ('', 'nan', 'null')
                then null
                else datadesfiliacao::timestamptz
            end as data_desfiliacao,
            fonte::text as fonte,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from bronze
    ),

    filtrado as (
        select *
        from tipado
        -- data confiável
        where data_filiacao is not null and data_filiacao >= '1995-01-01'::timestamptz
    ),

    -- A zona raw é append-only (ADR-0012/ADR-0021) e a DAG reprocessa o
    -- histórico completo de um senador a cada ciclo de elegibilidade, então o
    -- mesmo evento de filiação volta idêntico. Deduplicar é responsabilidade
    -- desta camada (ver airflow/helpers/landing_zone.py). A chave espelha a
    -- deduplicação em memória que a ingestão de filiações já faz:
    -- parlamentar, partido e data de filiação.
    versionado as (
        select
            filtrado.*,
            row_number() over (
                partition by parlamentar_id, sigla_partido, data_filiacao order by dt_ingest desc
            ) as nu_versao
        from filtrado
    )

select parlamentar_id, codigo_partido, sigla_partido, nome_partido, data_filiacao, data_desfiliacao, fonte, dt_ingest
from versionado
where nu_versao = 1
