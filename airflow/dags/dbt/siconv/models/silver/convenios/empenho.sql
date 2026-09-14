-- Silver do SICONV: empenho tipado a partir do source (papel que, antes do
-- ADR-0017, era da camada Bronze modelada). Sem filtro de órgão — vive no
-- pacote compartilhado (ADR-0004). Chave natural composta
-- declarada em airflow/plugins/tabelas_siconv.py (id_empenho, nr_empenho, tipo_nota);
-- a ingestão faz full-refresh desta entidade (truncate_before_insert)
-- porque a fonte não distingue registro excluído de inalterado.
--
-- Portado de data-application-mir (siconv_dbt/bronze/empenho.sql).
-- Granularidade: uma linha por empenho.
with
    empenho_raw as (
        select
            nullif(id_empenho, '')::integer as id_empenho,
            nullif(nr_convenio, '')::text as nr_convenio,
            nr_empenho::text as nr_empenho,
            tipo_nota::text as tipo_nota,
            desc_tipo_nota::text as desc_tipo_nota,
            to_date(nullif(data_emissao, ''), 'DD/MM/YYYY') as data_emissao,
            cod_situacao_empenho::text as cod_situacao_empenho,
            desc_situacao_empenho::text as desc_situacao_empenho,
            nullif(ug_emitente, '')::integer as ug_emitente,
            nullif(ug_responsavel, '')::integer as ug_responsavel,
            fonte_recurso::text as fonte_recurso,
            natureza_despesa::text as natureza_despesa,
            plano_interno::text as plano_interno,
            ptres::text as ptres,
            replace(nullif(valor_empenho, ''), ',', '.')::numeric(15, 2) as valor_empenho,
            resultado_primario::text as resultado_primario,
            observacao_empenho::text as observacao_empenho,
            descricao_emenda_siafi::text as descricao_emenda_siafi,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siconv", "empenho") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". Sem isto, a Gold soma a
    -- mesma linha uma vez por execução.
    versionado as (
        select
            empenho_raw.*,
            row_number() over (partition by id_empenho, nr_empenho, tipo_nota order by dt_ingest desc) as nu_versao
        from empenho_raw
    )

select
    id_empenho,
    nr_convenio,
    nr_empenho,
    tipo_nota,
    desc_tipo_nota,
    data_emissao,
    cod_situacao_empenho,
    desc_situacao_empenho,
    ug_emitente,
    ug_responsavel,
    fonte_recurso,
    natureza_despesa,
    plano_interno,
    ptres,
    valor_empenho,
    resultado_primario,
    observacao_empenho,
    descricao_emenda_siafi,
    dt_ingest
from versionado
where nu_versao = 1
