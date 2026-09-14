-- Silver do MIR: convênio com dados completos da proposta de origem. Cruza
-- o pacote siconv (via convenios_consolidados), por isso vive em dbt/mir/
-- (ADR-0004).
--
-- Portado de data-application-mir (siconv_dbt/silver/convenio_proposta.sql),
-- sem alteração de lógica de negócio — só o `ref()` da entidade do SICONV
-- mudou de projeto.
with
    convenio as (select * from {{ ref("convenios_consolidados") }}),
    proposta as (select * from {{ ref("siconv", "proposta") }})

select
    c.*,
    p.uf_proponente,
    p.munic_proponente,
    p.cod_munic_ibge,
    p.natureza_juridica,
    p.nr_proposta,
    p.dia_prop,
    p.mes_prop,
    p.ano_prop,
    p.dia_proposta,
    p.cod_orgao,
    p.desc_orgao,
    p.modalidade,
    p.identif_proponente,
    p.nm_proponente,
    p.cep_proponente,
    p.endereco_proponente,
    p.bairro_proponente,
    p.nm_banco,
    p.situacao_conta,
    p.situacao_projeto_basico,
    p.sit_proposta,
    p.dia_inic_vigencia_proposta,
    p.dia_fim_vigencia_proposta,
    p.objeto_proposta,
    p.item_investimento,
    p.enviada_mandataria,
    p.nome_subtipo_proposta,
    p.descricao_subtipo_proposta,
    p.vl_global_prop,
    p.vl_repasse_prop,
    p.vl_contrapartida_prop
from convenio c
left join proposta p on c.id_proposta = p.id_proposta
