-- Silver do MIR: convênio com seus pagamentos de tributo. Cruza o pacote
-- siconv (via convenios_consolidados), por isso vive em dbt/mir/ (ADR-0004).
--
-- Portado de data-application-mir
-- (siconv_dbt/silver/convenio_pagamento_tributo.sql), sem alteração de
-- lógica de negócio — só o `ref()` da entidade do SICONV mudou de projeto.
with
    convenio as (select * from {{ ref("convenios_consolidados") }}),
    pagamento_tributo as (select * from {{ ref("siconv", "pagamento_tributo") }})

select c.*, pt.data_tributo, pt.vl_pag_tributos
from convenio c
left join pagamento_tributo pt on c.nr_convenio = pt.nr_convenio
