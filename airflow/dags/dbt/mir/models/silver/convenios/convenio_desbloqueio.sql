-- Silver do MIR: convênio com seus desbloqueios de conta. Cruza o pacote
-- siconv (via convenios_consolidados), por isso vive em dbt/mir/ (ADR-0004).
--
-- Portado de data-application-mir (siconv_dbt/silver/convenio_desbloqueio.sql),
-- sem alteração de lógica de negócio — só o `ref()` da entidade do SICONV
-- mudou de projeto.
with
    convenio as (select * from {{ ref("convenios_consolidados") }}),
    desbloqueio as (select * from {{ ref("siconv", "desbloqueio") }})

select
    c.*,
    d.nr_ob,
    d.data_cadastro,
    d.data_envio,
    d.tipo_recurso_desbloqueio,
    d.vl_total_desbloqueio,
    d.vl_desbloqueado,
    d.vl_bloqueado
from convenio c
left join desbloqueio d on c.nr_convenio = d.nr_convenio
