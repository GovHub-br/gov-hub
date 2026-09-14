-- Silver do MIR: convênio com suas licitações. Cruza o pacote siconv (via
-- convenios_consolidados), por isso vive em dbt/mir/ (ADR-0004).
--
-- Portado de data-application-mir (siconv_dbt/silver/convenio_licitacao.sql),
-- sem alteração de lógica de negócio — só o `ref()` da entidade do SICONV
-- mudou de projeto.
with
    convenio as (select * from {{ ref("convenios_consolidados") }}),
    licitacao as (select * from {{ ref("siconv", "licitacao") }})

select
    c.*,
    l.id_licitacao,
    l.nr_licitacao,
    l.modalidade_licitacao,
    l.tp_processo_compra,
    l.tipo_licitacao,
    l.nr_processo_licitacao,
    l.data_publicacao_licitacao,
    l.data_abertura_licitacao,
    l.data_encerramento_licitacao,
    l.data_homologacao_licitacao,
    l.status_licitacao,
    l.situacao_aceite_processo_execu,
    l.sistema_origem,
    l.situacao_sistema,
    l.valor_licitacao,
    l.data_analise_aceite,
    l.data_envio_analise
from convenio c
left join licitacao l on c.nr_convenio = l.nr_convenio
