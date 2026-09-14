-- Silver do MIR: convênio com seus termos aditivos. Cruza o pacote siconv
-- (via convenios_consolidados), por isso vive em dbt/mir/ (ADR-0004).
--
-- Portado de data-application-mir
-- (siconv_dbt/silver/convenio_termo_aditivo.sql), sem alteração de lógica de
-- negócio — só o `ref()` da entidade do SICONV mudou de projeto.
with
    convenio as (select * from {{ ref("convenios_consolidados") }}),
    termo_aditivo as (select * from {{ ref("siconv", "termo_aditivo") }})

select
    c.*,
    t.numero_ta,
    t.tipo_ta,
    t.vl_global_ta,
    t.vl_repasse_ta,
    t.vl_contrapartida_ta,
    t.dt_assinatura_ta,
    t.dt_inicio_ta,
    t.dt_fim_ta,
    t.justificativa_ta
from convenio c
left join termo_aditivo t on c.nr_convenio = t.nr_convenio
