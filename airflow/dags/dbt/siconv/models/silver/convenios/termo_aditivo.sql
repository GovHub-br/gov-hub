-- Silver do SICONV: termo_aditivo tipado a partir do source (papel que,
-- antes do ADR-0017, era da camada Bronze modelada). Sem filtro de órgão —
-- vive no pacote compartilhado (ADR-0004).
--
-- Portado de data-application-mir (siconv_dbt/bronze/termo_aditivo.sql).
-- Granularidade: uma linha por termo aditivo de um convênio.
with
    termo_aditivo_raw as (
        select
            nullif(nr_convenio, '')::text as nr_convenio,
            nullif(id_solicitacao, '')::integer as id_solicitacao,
            numero_ta::text as numero_ta,
            tipo_ta::text as tipo_ta,
            replace(nullif(vl_global_ta, ''), ',', '.')::numeric(15, 2) as vl_global_ta,
            replace(nullif(vl_repasse_ta, ''), ',', '.')::numeric(15, 2) as vl_repasse_ta,
            replace(nullif(vl_contrapartida_ta, ''), ',', '.')::numeric(15, 2) as vl_contrapartida_ta,
            to_date(nullif(dt_assinatura_ta, ''), 'DD/MM/YYYY') as dt_assinatura_ta,
            to_date(nullif(dt_inicio_ta, ''), 'DD/MM/YYYY') as dt_inicio_ta,
            to_date(nullif(dt_fim_ta, ''), 'DD/MM/YYYY') as dt_fim_ta,
            justificativa_ta::text as justificativa_ta,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siconv", "termo_aditivo") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". Sem isto, a Gold soma a
    -- mesma linha uma vez por execução.
    versionado as (
        select
            termo_aditivo_raw.*,
            row_number() over (partition by nr_convenio, numero_ta order by dt_ingest desc) as nu_versao
        from termo_aditivo_raw
    )

select
    nr_convenio,
    id_solicitacao,
    numero_ta,
    tipo_ta,
    vl_global_ta,
    vl_repasse_ta,
    vl_contrapartida_ta,
    dt_assinatura_ta,
    dt_inicio_ta,
    dt_fim_ta,
    justificativa_ta,
    dt_ingest
from versionado
where nu_versao = 1
