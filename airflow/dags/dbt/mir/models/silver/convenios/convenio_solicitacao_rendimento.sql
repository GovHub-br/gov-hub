-- Silver do MIR: convênio com suas solicitações de uso do rendimento de
-- aplicação. Cruza o pacote siconv (via convenios_consolidados), por isso
-- vive em dbt/mir/ (ADR-0004).
--
-- Portado de data-application-mir
-- (siconv_dbt/silver/convenio_solicitacao_rendimento.sql), sem alteração de
-- lógica de negócio — só o `ref()` da entidade do SICONV mudou de projeto.
with
    convenio as (select * from {{ ref("convenios_consolidados") }}),
    solicitacao_rendimento as (select * from {{ ref("siconv", "solicitacao_rendimento_aplicacao") }})

select
    c.*,
    r.id_solicitacao_rend_aplicacao,
    r.nr_solicitacao_rend_aplicacao,
    r.status_solicitacao_rend_aplicacao,
    r.data_solicitacao_rend_aplicacao,
    r.valor_solicitacao_rend_aplicacao,
    r.valor_aprovado_solicitacao_rend_aplicacao
from convenio c
left join solicitacao_rendimento r on c.nr_convenio = r.nr_convenio
