-- Silver do MIR: convênio com seu cronograma de desembolso. Cruza o pacote
-- siconv (via convenios_consolidados), por isso vive em dbt/mir/ (ADR-0004).
--
-- Portado de data-application-mir
-- (siconv_dbt/silver/convenio_cronograma_desembolso.sql), sem alteração de
-- lógica de negócio — só o `ref()` da entidade do SICONV mudou de projeto.
with
    convenio as (select * from {{ ref("convenios_consolidados") }}),
    cronograma_desembolso as (select * from {{ ref("siconv", "cronograma_desembolso") }})

select
    c.*,
    cd.nr_parcela_crono_desembolso,
    cd.mes_crono_desembolso,
    cd.ano_crono_desembolso,
    cd.tipo_resp_crono_desembolso,
    cd.valor_parcela_crono_desembolso
from convenio c
left join cronograma_desembolso cd on c.nr_convenio = cd.nr_convenio
