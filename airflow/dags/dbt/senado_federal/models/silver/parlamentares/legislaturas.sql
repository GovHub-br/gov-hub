{{ config(materialized="table") }}

-- Silver de senado_federal.legislaturas — verdade única do dado (ADR-0006).
--
-- Granularidade: um registro por legislatura.
--
-- Tipagem portada de data-application-mir
-- (dados_abertos_dbt/bronze/legislaturas.sql). No repositório antigo essa
-- tipagem era um passo "bronze" à parte; aqui a Bronze é só o source
-- (ADR-0017), então a tipagem entra direto na Silver.
with
    bronze as (select * from {{ source("senado_federal", "legislaturas") }}),

    tipado as (
        select
            id::integer as id,
            data_inicio::date as data_inicio,
            data_fim::date as data_fim,
            data_eleicao::date as data_eleicao,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from bronze
    ),

    -- A zona raw é append-only (ADR-0012/ADR-0021): a DAG roda @weekly e cada
    -- execução acrescenta uma cópia da lista de legislaturas, então manter só
    -- a versão mais recente de cada uma é responsabilidade desta camada — ver
    -- airflow/helpers/landing_zone.py, "a deduplicação é responsabilidade da
    -- Silver". A chave é a mesma `primary_key` da DAG de ingestão.
    versionado as (
        select tipado.*, row_number() over (partition by id order by dt_ingest desc) as nu_versao from tipado
    )

select id, data_inicio, data_fim, data_eleicao, dt_ingest
from versionado
where nu_versao = 1
