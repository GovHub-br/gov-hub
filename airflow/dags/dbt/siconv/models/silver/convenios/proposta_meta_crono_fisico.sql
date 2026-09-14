-- Silver do SICONV: proposta com suas metas físicas. Junta duas entidades do
-- próprio pacote, sem filtro de órgão e sem cruzar nenhum outro sistema —
-- granularidade nacional, por isso fica em dbt/siconv/, não em dbt/mir/
-- (ADR-0004).
--
-- Portado de data-application-mir
-- (siconv_dbt/silver/proposta_meta_crono_fisico.sql).
with
    proposta as (select * from {{ ref("proposta") }}),
    meta_crono_fisico as (select * from {{ ref("meta_crono_fisico") }})

select
    p.*,
    m.id_meta,
    m.nr_convenio as nr_convenio_meta,
    m.nr_meta,
    m.tipo_meta,
    m.desc_meta,
    m.data_inicio_meta,
    m.data_fim_meta,
    m.uf_meta,
    m.municipio_meta,
    m.endereco_meta,
    m.cep_meta,
    m.qtd_meta,
    m.und_fornecimento_meta,
    m.vl_meta,
    m.cod_programa,
    m.nome_programa
from proposta p
left join meta_crono_fisico m on p.id_proposta = m.id_proposta
