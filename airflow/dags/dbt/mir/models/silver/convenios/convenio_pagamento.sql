-- Silver do MIR: convênio com seus pagamentos a fornecedores. Cruza o
-- pacote siconv (via convenios_consolidados), por isso vive em dbt/mir/
-- (ADR-0004).
--
-- Portado de data-application-mir (siconv_dbt/silver/convenio_pagamento.sql),
-- sem alteração de lógica de negócio — só o `ref()` da entidade do SICONV
-- mudou de projeto.
with
    convenio as (select * from {{ ref("convenios_consolidados") }}),
    pagamento as (select * from {{ ref("siconv", "pagamento") }})

select
    c.*,
    p.nr_mov_fin,
    p.identif_fornecedor,
    p.nome_fornecedor,
    p.tp_mov_financeira,
    p.data_pag,
    p.nr_dl,
    p.desc_dl,
    p.vl_pago,
    p.id_dl,
    p.data_emissao_dl
from convenio c
left join pagamento p on c.nr_convenio = p.nr_convenio
