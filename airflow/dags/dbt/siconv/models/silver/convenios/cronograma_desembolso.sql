-- Silver do SICONV: cronograma_desembolso tipado a partir do source (papel
-- que, antes do ADR-0017, era da camada Bronze modelada). Sem filtro de
-- órgão — vive no pacote compartilhado (ADR-0004).
--
-- Portado de data-application-mir (siconv_dbt/bronze/cronograma_desembolso.sql).
-- Granularidade: uma linha por parcela do cronograma de desembolso.
with
    cronograma_desembolso_raw as (
        select
            nullif(id_proposta, '')::integer as id_proposta,
            nullif(nr_convenio, '')::text as nr_convenio,
            nullif(nr_parcela_crono_desembolso, '')::integer as nr_parcela_crono_desembolso,
            nullif(mes_crono_desembolso, '')::integer as mes_crono_desembolso,
            nullif(ano_crono_desembolso, '')::integer as ano_crono_desembolso,
            tipo_resp_crono_desembolso::text as tipo_resp_crono_desembolso,
            replace(nullif(valor_parcela_crono_desembolso, ''), ',', '.')::numeric(
                15, 2
            ) as valor_parcela_crono_desembolso,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siconv", "cronograma_desembolso") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". Sem isto, a Gold soma a
    -- mesma linha uma vez por execução.
    versionado as (
        select
            cronograma_desembolso_raw.*,
            row_number() over (
                partition by id_proposta, nr_convenio, nr_parcela_crono_desembolso order by dt_ingest desc
            ) as nu_versao
        from cronograma_desembolso_raw
    )

select
    id_proposta,
    nr_convenio,
    nr_parcela_crono_desembolso,
    mes_crono_desembolso,
    ano_crono_desembolso,
    tipo_resp_crono_desembolso,
    valor_parcela_crono_desembolso,
    dt_ingest
from versionado
where nu_versao = 1
