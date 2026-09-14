-- Silver do SICONV: solicitacao_alteracao tipada a partir do source (papel
-- que, antes do ADR-0017, era da camada Bronze modelada). Sem filtro de
-- órgão — vive no pacote compartilhado (ADR-0004).
--
-- Portado de data-application-mir (siconv_dbt/bronze/solicitacao_alteracao.sql).
-- Granularidade: uma linha por solicitação de alteração.
with
    solicitacao_alteracao_raw as (
        select
            nullif(id_solicitacao, '')::integer as id_solicitacao,
            nullif(nr_convenio, '')::text as nr_convenio,
            nr_solicitacao::text as nr_solicitacao,
            situacao_solicitacao::text as situacao_solicitacao,
            objeto_solicitacao::text as objeto_solicitacao,
            case
                when nullif(data_solicitacao, '') is null
                then null
                when data_solicitacao ~ '^\d{2}/\d{2}/\d{4}$'
                then to_date(data_solicitacao, 'DD/MM/YYYY')
                else to_date(data_solicitacao, 'YYYY-MM-DD')
            end as data_solicitacao,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siconv", "solicitacao_alteracao") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". Sem isto, a Gold soma a
    -- mesma linha uma vez por execução.
    versionado as (
        select
            solicitacao_alteracao_raw.*,
            row_number() over (partition by id_solicitacao order by dt_ingest desc) as nu_versao
        from solicitacao_alteracao_raw
    )

select
    id_solicitacao, nr_convenio, nr_solicitacao, situacao_solicitacao, objeto_solicitacao, data_solicitacao, dt_ingest
from versionado
where nu_versao = 1
