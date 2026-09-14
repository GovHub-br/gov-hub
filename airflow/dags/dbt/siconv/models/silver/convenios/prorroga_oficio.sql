-- Silver do SICONV: prorroga_oficio tipada a partir do source (papel que,
-- antes do ADR-0017, era da camada Bronze modelada). Sem filtro de órgão —
-- vive no pacote compartilhado (ADR-0004). Chave natural composta
-- declarada em airflow/plugins/tabelas_siconv.py (nr_convenio, nr_prorroga, dt_inicio_prorroga, dt_fim_prorroga,
-- dt_assinatura_prorroga, sit_prorroga);
-- a ingestão faz full-refresh desta entidade (truncate_before_insert)
-- porque a fonte não distingue registro excluído de inalterado.
--
-- Portado de data-application-mir (siconv_dbt/bronze/prorroga_oficio.sql).
-- Granularidade: uma linha por prorrogação de ofício.
with
    prorroga_oficio_raw as (
        select
            nullif(nr_convenio, '')::text as nr_convenio,
            nr_prorroga::text as nr_prorroga,
            to_date(nullif(dt_inicio_prorroga, ''), 'DD/MM/YYYY') as dt_inicio_prorroga,
            to_date(nullif(dt_fim_prorroga, ''), 'DD/MM/YYYY') as dt_fim_prorroga,
            nullif(dias_prorroga, '')::integer as dias_prorroga,
            to_date(nullif(dt_assinatura_prorroga, ''), 'DD/MM/YYYY') as dt_assinatura_prorroga,
            sit_prorroga::text as sit_prorroga,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siconv", "prorroga_oficio") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". Sem isto, a Gold soma a
    -- mesma linha uma vez por execução.
    versionado as (
        select
            prorroga_oficio_raw.*,
            row_number() over (
                partition by
                    nr_convenio, nr_prorroga, dt_inicio_prorroga, dt_fim_prorroga, dt_assinatura_prorroga, sit_prorroga
                order by dt_ingest desc
            ) as nu_versao
        from prorroga_oficio_raw
    )

select
    nr_convenio,
    nr_prorroga,
    dt_inicio_prorroga,
    dt_fim_prorroga,
    dias_prorroga,
    dt_assinatura_prorroga,
    sit_prorroga,
    dt_ingest
from versionado
where nu_versao = 1
