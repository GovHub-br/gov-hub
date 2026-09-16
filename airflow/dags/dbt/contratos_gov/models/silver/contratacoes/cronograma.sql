-- Silver de contratos_gov.cronograma — verdade única do dado (ADR-0006).
--
-- Granularidade: uma linha por item de cronograma de um contrato.
--
-- Tipagem portada de data-application-mir (compras_gov_dbt/bronze/cronograma.sql).
with
    bronze as (select * from {{ source("contratos_gov", "cronograma") }}),

    tipado as (
        select
            nullif(cast(id as text), '')::integer as id,
            cast(contrato_id as text) as contrato_id,
            tipo,
            numero,
            receita_despesa,
            observacao,
            nullif(cast(mesref as text), '')::integer as mesref,
            nullif(cast(anoref as text), '')::integer as anoref,
            case
                when vencimento is not null and cast(vencimento as text) ~ '^\d{4}-\d{2}-\d{2}$'
                then cast(vencimento as date)
            end as vencimento,
            retroativo,
            replace(replace(nullif(cast(valor as text), ''), '.', ''), ',', '.')::numeric(15, 2) as valor,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from bronze
    ),

    versionado as (
        select tipado.*, row_number() over (partition by id, contrato_id order by dt_ingest desc) as nu_versao
        from tipado
    )

select
    id, contrato_id, tipo, numero, receita_despesa, observacao, mesref, anoref, vencimento, retroativo, valor, dt_ingest
from versionado
where nu_versao = 1
