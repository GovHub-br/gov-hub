-- Silver do SICONV: licitacao tipada a partir do source (papel que, antes do
-- ADR-0017, era da camada Bronze modelada). Sem filtro de órgão — vive no
-- pacote compartilhado (ADR-0004).
--
-- Portado de data-application-mir (siconv_dbt/bronze/licitacao.sql).
-- Granularidade: uma linha por licitação.
with
    licitacao_raw as (
        select
            nullif(id_licitacao, '')::integer as id_licitacao,
            nullif(nr_convenio, '')::text as nr_convenio,
            nr_licitacao::text as nr_licitacao,
            modalidade_licitacao::text as modalidade_licitacao,
            tp_processo_compra::text as tp_processo_compra,
            tipo_licitacao::text as tipo_licitacao,
            nr_processo_licitacao::text as nr_processo_licitacao,
            to_date(nullif(data_publicacao_licitacao, ''), 'DD/MM/YYYY') as data_publicacao_licitacao,
            to_date(nullif(data_abertura_licitacao, ''), 'DD/MM/YYYY') as data_abertura_licitacao,
            to_date(nullif(data_encerramento_licitacao, ''), 'DD/MM/YYYY') as data_encerramento_licitacao,
            to_date(nullif(data_homologacao_licitacao, ''), 'DD/MM/YYYY') as data_homologacao_licitacao,
            status_licitacao::text as status_licitacao,
            situacao_aceite_processo_execu::text as situacao_aceite_processo_execu,
            sistema_origem::text as sistema_origem,
            situacao_sistema::text as situacao_sistema,
            replace(nullif(valor_licitacao, ''), ',', '.')::numeric(20, 2) as valor_licitacao,
            to_date(nullif(data_analise_aceite, ''), 'DD/MM/YYYY') as data_analise_aceite,
            to_date(nullif(data_envio_analise, ''), 'DD/MM/YYYY') as data_envio_analise,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siconv", "licitacao") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". Sem isto, a Gold soma a
    -- mesma linha uma vez por execução.
    versionado as (
        select licitacao_raw.*, row_number() over (partition by id_licitacao order by dt_ingest desc) as nu_versao
        from licitacao_raw
    )

select
    id_licitacao,
    nr_convenio,
    nr_licitacao,
    modalidade_licitacao,
    tp_processo_compra,
    tipo_licitacao,
    nr_processo_licitacao,
    data_publicacao_licitacao,
    data_abertura_licitacao,
    data_encerramento_licitacao,
    data_homologacao_licitacao,
    status_licitacao,
    situacao_aceite_processo_execu,
    sistema_origem,
    situacao_sistema,
    valor_licitacao,
    data_analise_aceite,
    data_envio_analise,
    dt_ingest
from versionado
where nu_versao = 1
