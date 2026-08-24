-- Gold: contratos_por_orgao — produto de dados (ADR-0006).
--
-- Cruzamento gerado por `make modelo` a partir das chaves conformadas do
-- catálogo: compras_gov.contratos ⨝ compras_gov.uasg ⨝ compras_gov.orgao ⨝ compras_gov.fornecedor.
--
-- PREENCHER: a pergunta de negócio que esta tabela responde, e a regra de
-- cálculo de cada coluna derivada (ADR-0013).
--
-- O cruzamento traz apenas as chaves; as colunas de negócio de cada entidade
-- ficam disponíveis para projetar em: uasg.*, orgao.*, fornecedor.*.
-- ATENÇÃO: o cruzamento com compras_gov.fornecedor usa a ponte nu_ni → nu_cnpj, de confiabilidade total.
with
    contratos as (select * from {{ ref("compras_gov", "contratos") }}),
    uasg as (select * from {{ ref("compras_gov", "uasg") }}),
    orgao as (select * from {{ ref("compras_gov", "orgao") }}),
    fornecedor as (select * from {{ ref("compras_gov", "fornecedor") }}),

    cruzado as (
        select contratos.*, uasg.co_orgao, fornecedor.nu_cpf
        from contratos
        left join uasg on contratos.co_uasg = uasg.co_uasg
        left join orgao on uasg.co_orgao = orgao.co_orgao
        -- ponte nu_ni → nu_cnpj (confiabilidade: total)
        -- a derivação só vale onde length(nu_ni) = 14; as demais linhas ficam sem par.
        left join fornecedor on contratos.nu_ni = fornecedor.nu_cnpj
    )

select *
from cruzado
