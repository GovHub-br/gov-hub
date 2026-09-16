-- Silver do SICONV: meta_crono_fisico tipado a partir do source (papel que,
-- antes do ADR-0017, era da camada Bronze modelada). Sem filtro de órgão —
-- vive no pacote compartilhado (ADR-0004).
--
-- Portado de data-application-mir (siconv_dbt/bronze/meta_crono_fisico.sql).
-- Granularidade: uma linha por meta física.
with
    meta_crono_fisico_raw as (
        select
            nullif(id_meta, '')::integer as id_meta,
            nullif(id_proposta, '')::integer as id_proposta,
            nullif(nr_convenio, '')::text as nr_convenio,
            cod_programa::text as cod_programa,
            nome_programa::text as nome_programa,
            nullif(nr_meta, '')::integer as nr_meta,
            tipo_meta::text as tipo_meta,
            desc_meta::text as desc_meta,
            to_date(nullif(data_inicio_meta, ''), 'DD/MM/YYYY') as data_inicio_meta,
            to_date(nullif(data_fim_meta, ''), 'DD/MM/YYYY') as data_fim_meta,
            uf_meta::text as uf_meta,
            municipio_meta::text as municipio_meta,
            endereco_meta::text as endereco_meta,
            cep_meta::text as cep_meta,
            replace(nullif(qtd_meta, ''), ',', '.')::numeric(15, 2) as qtd_meta,
            und_fornecimento_meta::text as und_fornecimento_meta,
            replace(nullif(vl_meta, ''), ',', '.')::numeric(15, 2) as vl_meta,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siconv", "meta_crono_fisico") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". Sem isto, a Gold soma a
    -- mesma linha uma vez por execução.
    versionado as (
        select meta_crono_fisico_raw.*, row_number() over (partition by id_meta order by dt_ingest desc) as nu_versao
        from meta_crono_fisico_raw
    )

select
    id_meta,
    id_proposta,
    nr_convenio,
    cod_programa,
    nome_programa,
    nr_meta,
    tipo_meta,
    desc_meta,
    data_inicio_meta,
    data_fim_meta,
    uf_meta,
    municipio_meta,
    endereco_meta,
    cep_meta,
    qtd_meta,
    und_fornecimento_meta,
    vl_meta,
    dt_ingest
from versionado
where nu_versao = 1
