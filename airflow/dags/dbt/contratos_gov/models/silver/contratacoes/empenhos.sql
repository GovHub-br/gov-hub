-- Silver de contratos_gov.empenhos — verdade única do dado (ADR-0006).
--
-- Granularidade: uma linha por empenho de um contrato.
--
-- Tipagem portada de data-application-mir (compras_gov_dbt/bronze/empenhos.sql).
with
    bronze as (select * from {{ source("contratos_gov", "empenhos") }}),

    tipado as (
        select
            cast(id as text) as id,
            cast(contrato_id as text) as contrato_id,
            unidade_gestora,
            gestao,
            numero as nota_empenho,
            credor,
            fonte_recurso,
            programa_trabalho,
            planointerno,
            naturezadespesa,
            informacao_complementar,
            sistema_origem,
            links__documento_pagamento as links_documento_pagamento,
            credor_obj__tipo as credor_obj_tipo,
            credor_obj__cnpj_cpf_idgener as credor_obj_cnpj_cpf_idgener,
            credor_obj__nome as credor_obj_nome,
            replace(replace(cast(empenhado as text), '.', ''), ',', '.')::numeric(15, 2) as empenhado,
            replace(replace(cast(aliquidar as text), '.', ''), ',', '.')::numeric(15, 2) as aliquidar,
            replace(replace(cast(liquidado as text), '.', ''), ',', '.')::numeric(15, 2) as liquidado,
            replace(replace(cast(pago as text), '.', ''), ',', '.')::numeric(15, 2) as pago,
            replace(replace(cast(rpinscrito as text), '.', ''), ',', '.')::numeric(15, 2) as rpinscrito,
            replace(replace(cast(rpaliquidar as text), '.', ''), ',', '.')::numeric(15, 2) as rpaliquidar,
            replace(replace(cast(rpliquidado as text), '.', ''), ',', '.')::numeric(15, 2) as rpliquidado,
            replace(replace(cast(rppago as text), '.', ''), ',', '.')::numeric(15, 2) as rppago,
            case
                when data_emissao is not null and cast(data_emissao as text) ~ '^\d{4}-\d{2}-\d{2}$'
                then to_date(cast(data_emissao as text), 'YYYY-MM-DD')
            end as data_emissao,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from bronze
    ),

    versionado as (
        select tipado.*, row_number() over (partition by id, contrato_id order by dt_ingest desc) as nu_versao
        from tipado
    )

select
    id,
    contrato_id,
    unidade_gestora,
    gestao,
    nota_empenho,
    credor,
    fonte_recurso,
    programa_trabalho,
    planointerno,
    naturezadespesa,
    informacao_complementar,
    sistema_origem,
    links_documento_pagamento,
    credor_obj_tipo,
    credor_obj_cnpj_cpf_idgener,
    credor_obj_nome,
    empenhado,
    aliquidar,
    liquidado,
    pago,
    rpinscrito,
    rpaliquidar,
    rpliquidado,
    rppago,
    data_emissao,
    dt_ingest
from versionado
where nu_versao = 1
