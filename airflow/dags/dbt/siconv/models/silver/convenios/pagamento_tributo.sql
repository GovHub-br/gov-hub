-- Silver do SICONV: pagamento_tributo tipado a partir do source (papel que,
-- antes do ADR-0017, era da camada Bronze modelada). Sem filtro de órgão —
-- vive no pacote compartilhado (ADR-0004).
--
-- Portado de data-application-mir (siconv_dbt/bronze/pagamento_tributo.sql).
-- Granularidade: uma linha por pagamento de tributo, por convênio e data.
with
    pagamento_tributo_raw as (
        select
            nr_convenio::text as nr_convenio,
            to_date(nullif(data_tributo, ''), 'DD/MM/YYYY') as data_tributo,
            replace(nullif(vl_pag_tributos, ''), ',', '.')::numeric(15, 2) as vl_pag_tributos,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siconv", "pagamento_tributo") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". Sem isto, a Gold soma a
    -- mesma linha uma vez por execução.
    versionado as (
        select
            pagamento_tributo_raw.*,
            row_number() over (partition by nr_convenio, data_tributo order by dt_ingest desc) as nu_versao
        from pagamento_tributo_raw
    )

select nr_convenio, data_tributo, vl_pag_tributos, dt_ingest
from versionado
where nu_versao = 1
