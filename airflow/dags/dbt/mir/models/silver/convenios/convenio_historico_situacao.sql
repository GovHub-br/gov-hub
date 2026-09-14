-- Silver do MIR: convênio com seu histórico de situação. Cruza o pacote
-- siconv (via convenios_consolidados), por isso vive em dbt/mir/ (ADR-0004).
--
-- Portado de data-application-mir
-- (siconv_dbt/silver/convenio_historico_situacao.sql), sem alteração de
-- lógica de negócio — só o `ref()` da entidade do SICONV mudou de projeto.
with
    convenio as (select * from {{ ref("convenios_consolidados") }}),
    historico_situacao as (select * from {{ ref("siconv", "historico_situacao") }})

select c.*, h.dia_historico_sit, h.historico_sit, h.dias_historico_sit, h.cod_historico_sit
from convenio c
left join historico_situacao h on c.nr_convenio = h.nr_convenio
