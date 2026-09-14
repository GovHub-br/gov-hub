-- Silver do MIR: convênio com suas solicitações de alteração. Cruza o
-- pacote siconv (via convenios_consolidados), por isso vive em dbt/mir/
-- (ADR-0004).
--
-- Portado de data-application-mir
-- (siconv_dbt/silver/convenio_solicitacao_alteracao.sql), sem alteração de
-- lógica de negócio — só o `ref()` da entidade do SICONV mudou de projeto.
with
    convenio as (select * from {{ ref("convenios_consolidados") }}),
    solicitacao_alteracao as (select * from {{ ref("siconv", "solicitacao_alteracao") }})

select c.*, s.id_solicitacao, s.nr_solicitacao, s.situacao_solicitacao, s.objeto_solicitacao, s.data_solicitacao
from convenio c
left join solicitacao_alteracao s on c.nr_convenio = s.nr_convenio
