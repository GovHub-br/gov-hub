{{ config(materialized="table") }}

-- Silver do MIR: programação financeira de TED tipada a partir da Bronze.
--
-- Sem cruzamento com nenhum outro sistema — mesmo racional de posicionamento
-- de planos_acao_ted.sql/programas_ted.sql (ver cabeçalho daqueles
-- arquivos). Mantém o nome `pf_transfere` do modelo original (distinto do
-- nome da entidade Bronze, `programacao_financeira`) porque é assim que
-- pf_unificado.sql, em dbt/mir/, referencia este modelo.
--
-- Portado de data-application-mir (dags/dbt/mir/models/empenhos_ted_dbt/
-- bronze/pf_transfere.sql).
with
    pf_transfere_raw as (
        select
            id_programacao::integer as id_programacao,
            id_plano_acao::integer as id_plano_acao,
            tp_pf_tipo_programacao::text as tp_pf_tipo_programacao,
            tx_minuta_programacao::text as tx_minuta_programacao,
            tx_numero_programacao::text as tx_numero_programacao,
            tx_situacao_programacao::text as tx_situacao_programacao,
            tx_observacao_programacao::text as tx_observacao_programacao,
            ug_emitente_programacao::text as ug_emitente_programacao,
            ug_favorecida_programacao::text as ug_favorecida_programacao,
            dh_recebimento_programacao::timestamp as dh_recebimento_programacao,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("transferegov_ted", "programacao_financeira") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". A chave abaixo é a mesma
    -- `primary_key` que a DAG de ingestão declara, para que a definição de
    -- linha repetida seja única entre ingestão e transformação.
    versionado as (
        select pf_transfere_raw.*, row_number() over (partition by id_programacao order by dt_ingest desc) as nu_versao
        from pf_transfere_raw
    )

select
    id_programacao,
    id_plano_acao,
    tp_pf_tipo_programacao,
    tx_minuta_programacao,
    tx_numero_programacao,
    tx_situacao_programacao,
    tx_observacao_programacao,
    ug_emitente_programacao,
    ug_favorecida_programacao,
    dh_recebimento_programacao,
    dt_ingest
from versionado
where nu_versao = 1
