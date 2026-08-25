-- Silver de compras_gov.orgao — verdade única do dado (ADR-0006).
--
-- Granularidade: um registro por código de órgão.
--
-- Gerado por `make modelo` a partir do catálogo. As chaves conformadas e a
-- deduplicação já vêm prontas; acrescente à mão as colunas de negócio que
-- este modelo precisa expor.
with
    bronze as (select * from {{ source("compras_gov", "orgao") }}),

    conformado as (
        select {{ gov_bricks.chave_conformada("co_orgao", "codigoorgao") }} as co_orgao, codigoorgao, dt_ingest
        from bronze
    ),

    versionado as (
        select conformado.*, row_number() over (partition by codigoorgao order by dt_ingest desc) as nu_versao
        from conformado
    )

select co_orgao, codigoorgao, dt_ingest
from versionado
where nu_versao = 1
