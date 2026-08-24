-- Silver de compras_gov.uasg — verdade única do dado (ADR-0006).
--
-- Granularidade: um registro por código de UASG.
--
-- Gerado por `make modelo` a partir do catálogo. As chaves conformadas e a
-- deduplicação já vêm prontas; acrescente à mão as colunas de negócio que
-- este modelo precisa expor.
-- ATENÇÃO: o mapeamento co_orgao → codigoorgao ainda
-- não foi verificado contra o dado ingerido.
with
    bronze as (select * from {{ source("compras_gov", "uasg") }}),

    conformado as (
        select
            {{ chave_conformada("co_uasg", "codigouasg") }} as co_uasg,
            {{ chave_conformada("co_orgao", "codigoorgao") }} as co_orgao,
            codigouasg,
            codigoorgao,
            dt_ingest
        from bronze
    ),

    versionado as (
        select conformado.*, row_number() over (partition by codigouasg order by dt_ingest desc) as nu_versao
        from conformado
    )

select co_uasg, co_orgao, codigouasg, codigoorgao, dt_ingest
from versionado
where nu_versao = 1
