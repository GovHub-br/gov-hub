-- Silver de compras_gov.fornecedor — verdade única do dado (ADR-0006).
--
-- Granularidade: um registro por fornecedor ativo, identificado por CNPJ ou CPF.
--
-- Gerado por `make modelo` a partir do catálogo. As chaves conformadas e a
-- deduplicação já vêm prontas; acrescente à mão as colunas de negócio que
-- este modelo precisa expor.
with
    bronze as (select * from {{ source("compras_gov", "fornecedor") }}),

    conformado as (
        select
            {{ gov_bricks.chave_conformada("nu_cnpj", "cnpj") }} as nu_cnpj,
            {{ gov_bricks.chave_conformada("nu_cpf", "cpf") }} as nu_cpf,
            cnpj,
            cpf,
            dt_ingest
        from bronze
    ),

    versionado as (
        select conformado.*, row_number() over (partition by cnpj, cpf order by dt_ingest desc) as nu_versao
        from conformado
    )

select nu_cnpj, nu_cpf, cnpj, cpf, dt_ingest
from versionado
where nu_versao = 1
