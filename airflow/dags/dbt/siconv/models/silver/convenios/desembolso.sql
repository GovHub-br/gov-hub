-- Silver do SICONV: desembolso tipado a partir do source (papel que, antes
-- do ADR-0017, era da camada Bronze modelada). Sem filtro de órgão — vive no
-- pacote compartilhado (ADR-0004).
--
-- Portado de data-application-mir (siconv_dbt/bronze/desembolso.sql).
-- Granularidade: uma linha por desembolso.
with
    desembolso_raw as (
        select
            nullif(id_desembolso, '')::integer as id_desembolso,
            nullif(nr_convenio, '')::text as nr_convenio,
            to_date(nullif(dt_ult_desembolso, ''), 'DD/MM/YYYY') as dt_ult_desembolso,
            nullif(qtd_dias_sem_desembolso, '')::integer as qtd_dias_sem_desembolso,
            to_date(nullif(data_desembolso, ''), 'DD/MM/YYYY') as data_desembolso,
            nullif(ano_desembolso, '')::integer as ano_desembolso,
            nullif(mes_desembolso, '')::integer as mes_desembolso,
            nr_siafi::text as nr_siafi,
            nullif(ug_emitente_dh, '')::integer as ug_emitente_dh,
            observacao_dh::text as observacao_dh,
            replace(nullif(vl_desembolsado, ''), ',', '.')::numeric(15, 2) as vl_desembolsado,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siconv", "desembolso") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". Sem isto, a Gold soma a
    -- mesma linha uma vez por execução.
    versionado as (
        select desembolso_raw.*, row_number() over (partition by id_desembolso order by dt_ingest desc) as nu_versao
        from desembolso_raw
    )

select
    id_desembolso,
    nr_convenio,
    dt_ult_desembolso,
    qtd_dias_sem_desembolso,
    data_desembolso,
    ano_desembolso,
    mes_desembolso,
    nr_siafi,
    ug_emitente_dh,
    observacao_dh,
    vl_desembolsado,
    dt_ingest
from versionado
where nu_versao = 1
