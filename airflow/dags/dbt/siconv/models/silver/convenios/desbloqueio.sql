-- Silver do SICONV: desbloqueio tipado a partir do source (papel que, antes
-- do ADR-0017, era da camada Bronze modelada). Sem filtro de órgão — vive no
-- pacote compartilhado (ADR-0004). Chave natural composta
-- declarada em airflow/plugins/tabelas_siconv.py (nr_convenio, nr_ob, data_cadastro, data_envio,
-- tipo_recurso_desbloqueio);
-- a ingestão faz full-refresh desta entidade (truncate_before_insert)
-- porque a fonte não distingue registro excluído de inalterado.
--
-- Portado de data-application-mir (siconv_dbt/bronze/desbloqueio.sql).
-- Granularidade: uma linha por desbloqueio.
with
    desbloqueio_raw as (
        select
            nr_convenio::text as nr_convenio,
            nr_ob::text as nr_ob,
            to_date(nullif(data_cadastro, ''), 'DD/MM/YYYY') as data_cadastro,
            to_date(nullif(data_envio, ''), 'DD/MM/YYYY') as data_envio,
            tipo_recurso_desbloqueio::text as tipo_recurso_desbloqueio,
            replace(nullif(vl_total_desbloqueio, ''), ',', '.')::numeric(15, 2) as vl_total_desbloqueio,
            replace(nullif(vl_desbloqueado, ''), ',', '.')::numeric(15, 2) as vl_desbloqueado,
            replace(nullif(vl_bloqueado, ''), ',', '.')::numeric(15, 2) as vl_bloqueado,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siconv", "desbloqueio") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". Sem isto, a Gold soma a
    -- mesma linha uma vez por execução.
    versionado as (
        select
            desbloqueio_raw.*,
            row_number() over (
                partition by nr_convenio, nr_ob, data_cadastro, data_envio, tipo_recurso_desbloqueio
                order by dt_ingest desc
            ) as nu_versao
        from desbloqueio_raw
    )

select
    nr_convenio,
    nr_ob,
    data_cadastro,
    data_envio,
    tipo_recurso_desbloqueio,
    vl_total_desbloqueio,
    vl_desbloqueado,
    vl_bloqueado,
    dt_ingest
from versionado
where nu_versao = 1
