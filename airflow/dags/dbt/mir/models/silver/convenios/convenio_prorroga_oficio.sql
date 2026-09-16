-- Silver do MIR: convênio com suas prorrogações de ofício. Cruza o pacote
-- siconv (via convenios_consolidados), por isso vive em dbt/mir/ (ADR-0004).
--
-- Portado de data-application-mir
-- (siconv_dbt/silver/convenio_prorroga_oficio.sql), sem alteração de lógica
-- de negócio — só o `ref()` da entidade do SICONV mudou de projeto.
with
    convenio as (select * from {{ ref("convenios_consolidados") }}),
    prorroga_oficio as (select * from {{ ref("siconv", "prorroga_oficio") }})

select
    c.*,
    p.nr_prorroga,
    p.dt_inicio_prorroga,
    p.dt_fim_prorroga,
    p.dias_prorroga,
    p.dt_assinatura_prorroga,
    p.sit_prorroga
from convenio c
left join prorroga_oficio p on c.nr_convenio = p.nr_convenio
