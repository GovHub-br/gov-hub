-- Silver do MIR: convênio com seus ingressos de contrapartida. Cruza o
-- pacote siconv (via convenios_consolidados), por isso vive em dbt/mir/
-- (ADR-0004).
--
-- Portado de data-application-mir
-- (siconv_dbt/silver/convenio_ingresso_contrapartida.sql), sem alteração de
-- lógica de negócio — só o `ref()` da entidade do SICONV mudou de projeto.
with
    convenio as (select * from {{ ref("convenios_consolidados") }}),
    ingresso_contrapartida as (select * from {{ ref("siconv", "ingresso_contrapartida") }})

select c.*, ic.dt_ingresso_contrapartida, ic.vl_ingresso_contrapartida as vl_ingresso_contrapartida_real
from convenio c
left join ingresso_contrapartida ic on c.nr_convenio = ic.nr_convenio
