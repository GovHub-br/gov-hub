-- Silver do SICONV: historico_situacao tipado a partir do source (papel que,
-- antes do ADR-0017, era da camada Bronze modelada). Sem filtro de órgão —
-- vive no pacote compartilhado (ADR-0004). Chave natural composta
-- declarada em airflow/plugins/tabelas_siconv.py (id_proposta, nr_convenio, dia_historico_sit, historico_sit,
-- dias_historico_sit, cod_historico_sit);
-- a ingestão faz full-refresh desta entidade (truncate_before_insert)
-- porque a fonte não distingue registro excluído de inalterado.
--
-- Portado de data-application-mir (siconv_dbt/bronze/historico_situacao.sql).
-- Granularidade: uma linha por mudança de situação.
with
    historico_situacao_raw as (
        select
            nullif(id_proposta, '')::integer as id_proposta,
            nullif(nr_convenio, '')::text as nr_convenio,
            to_date(nullif(dia_historico_sit, ''), 'DD/MM/YYYY') as dia_historico_sit,
            historico_sit::text as historico_sit,
            nullif(dias_historico_sit, '')::integer as dias_historico_sit,
            nullif(cod_historico_sit, '')::integer as cod_historico_sit,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siconv", "historico_situacao") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". Sem isto, a Gold soma a
    -- mesma linha uma vez por execução.
    versionado as (
        select
            historico_situacao_raw.*,
            row_number() over (
                partition by
                    id_proposta, nr_convenio, dia_historico_sit, historico_sit, dias_historico_sit, cod_historico_sit
                order by dt_ingest desc
            ) as nu_versao
        from historico_situacao_raw
    )

select id_proposta, nr_convenio, dia_historico_sit, historico_sit, dias_historico_sit, cod_historico_sit, dt_ingest
from versionado
where nu_versao = 1
