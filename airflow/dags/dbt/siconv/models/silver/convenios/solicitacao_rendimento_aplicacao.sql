-- Silver do SICONV: solicitacao_rendimento_aplicacao tipada a partir do
-- source (papel que, antes do ADR-0017, era da camada Bronze modelada). Sem
-- filtro de órgão — vive no pacote compartilhado (ADR-0004).
--
-- Portado de data-application-mir
-- (siconv_dbt/bronze/solicitacao_rendimento_aplicacao.sql).
-- Granularidade: uma linha por solicitação de rendimento de aplicação.
with
    solicitacao_rendimento_aplicacao_raw as (
        select
            nullif(id_solicitacao_rend_aplicacao, '')::integer as id_solicitacao_rend_aplicacao,
            nullif(nr_convenio, '')::text as nr_convenio,
            nr_solicitacao_rend_aplicacao::text as nr_solicitacao_rend_aplicacao,
            status_solicitacao_rend_aplicacao::text as status_solicitacao_rend_aplicacao,
            case
                when nullif(data_solicitacao_rend_aplicacao, '') is null
                then null
                when data_solicitacao_rend_aplicacao ~ '^\d{2}/\d{2}/\d{4}$'
                then to_date(data_solicitacao_rend_aplicacao, 'DD/MM/YYYY')
                else to_date(data_solicitacao_rend_aplicacao, 'YYYY-MM-DD')
            end as data_solicitacao_rend_aplicacao,
            replace(nullif(valor_solicitacao_rend_aplicacao, ''), ',', '.')::numeric(
                15, 2
            ) as valor_solicitacao_rend_aplicacao,
            replace(nullif(valor_aprovado_solicitacao_rend_aplicacao, ''), ',', '.')::numeric(
                15, 2
            ) as valor_aprovado_solicitacao_rend_aplicacao,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siconv", "solicitacao_rendimento_aplicacao") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". Sem isto, a Gold soma a
    -- mesma linha uma vez por execução.
    versionado as (
        select
            solicitacao_rendimento_aplicacao_raw.*,
            row_number() over (partition by id_solicitacao_rend_aplicacao order by dt_ingest desc) as nu_versao
        from solicitacao_rendimento_aplicacao_raw
    )

select
    id_solicitacao_rend_aplicacao,
    nr_convenio,
    nr_solicitacao_rend_aplicacao,
    status_solicitacao_rend_aplicacao,
    data_solicitacao_rend_aplicacao,
    valor_solicitacao_rend_aplicacao,
    valor_aprovado_solicitacao_rend_aplicacao,
    dt_ingest
from versionado
where nu_versao = 1
