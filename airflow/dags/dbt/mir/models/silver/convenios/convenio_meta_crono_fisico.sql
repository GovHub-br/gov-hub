-- Silver do MIR: convênio com suas metas físicas. Cruza o pacote siconv (via
-- convenios_consolidados), por isso vive em dbt/mir/ (ADR-0004).
--
-- Portado de data-application-mir
-- (siconv_dbt/silver/convenio_meta_crono_fisico.sql), sem alteração de
-- lógica de negócio — só o `ref()` da entidade do SICONV mudou de projeto.
with
    convenio as (select * from {{ ref("convenios_consolidados") }}),
    meta_crono_fisico as (select * from {{ ref("siconv", "meta_crono_fisico") }})

select
    c.*,
    m.id_meta,
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
    m.cod_programa as cod_programa_meta,
    m.nome_programa as nome_programa_meta
from convenio c
left join meta_crono_fisico m on c.nr_convenio = m.nr_convenio
