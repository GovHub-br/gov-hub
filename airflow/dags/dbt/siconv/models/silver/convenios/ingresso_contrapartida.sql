-- Silver do SICONV: ingresso_contrapartida tipado a partir do source (papel
-- que, antes do ADR-0017, era da camada Bronze modelada). Sem filtro de
-- órgão — vive no pacote compartilhado (ADR-0004).
--
-- Portado de data-application-mir (siconv_dbt/bronze/ingresso_contrapartida.sql).
-- Granularidade: uma linha por ingresso de contrapartida, por convênio e data.
with
    ingresso_contrapartida_raw as (
        select
            nr_convenio::text as nr_convenio,
            to_date(nullif(dt_ingresso_contrapartida, ''), 'DD/MM/YYYY') as dt_ingresso_contrapartida,
            replace(nullif(vl_ingresso_contrapartida, ''), ',', '.')::numeric(15, 2) as vl_ingresso_contrapartida,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siconv", "ingresso_contrapartida") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". Sem isto, a Gold soma a
    -- mesma linha uma vez por execução.
    versionado as (
        select
            ingresso_contrapartida_raw.*,
            row_number() over (partition by nr_convenio, dt_ingresso_contrapartida order by dt_ingest desc) as nu_versao
        from ingresso_contrapartida_raw
    )

select nr_convenio, dt_ingresso_contrapartida, vl_ingresso_contrapartida, dt_ingest
from versionado
where nu_versao = 1
