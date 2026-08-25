-- Silver de compras_gov.contratos — verdade única do dado (ADR-0006).
--
-- Granularidade: uma linha por unidade gestora, número de contrato e fornecedor.
--
-- Gerado por `make modelo` a partir do catálogo. As chaves conformadas e a
-- deduplicação já vêm prontas; acrescente à mão as colunas de negócio que
-- este modelo precisa expor.
with
    bronze as (select * from {{ source("compras_gov", "contratos") }}),

    conformado as (
        select
            {{ gov_bricks.chave_conformada("co_uasg", "codigounidadegestora") }} as co_uasg,
            {{ gov_bricks.chave_conformada("nu_ni", "nifornecedor") }} as nu_ni,
            codigounidadegestora,
            numerocontrato,
            nifornecedor,
            dt_ingest
        from bronze
    ),

    versionado as (
        select
            conformado.*,
            row_number() over (
                partition by codigounidadegestora, numerocontrato, nifornecedor order by dt_ingest desc
            ) as nu_versao
        from conformado
    )

select co_uasg, nu_ni, codigounidadegestora, numerocontrato, nifornecedor, dt_ingest
from versionado
where nu_versao = 1
