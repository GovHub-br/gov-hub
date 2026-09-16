{{ config(materialized="table") }}

-- Silver de tesouro_gerencial: programações financeiras do exercício
-- corrente, tipadas a partir da Bronze.
--
-- Sem cruzamento com nenhum outro sistema — só tipagem sobre o próprio
-- source de tesouro_gerencial — por isso vive na raiz do pacote (ADR-0004/
-- 0009), não em dbt/mir/. Consumido por pf_unificado.sql, em
-- dbt/mir/models/silver/transferencias/ (que aí sim cruza com
-- transferegov_ted).
--
-- Portado de data-application-mir (dags/dbt/mir/models/empenhos_ted_dbt/
-- bronze/pf_tesouro.sql).
with
    pf_tesouro_raw as (
        select
            emissao_mes::text as emissao_mes,
            to_date(nullif(emissao_dia, ''), 'DD/MM/YYYY') as emissao_dia,
            ug_emitente::text as ug_emitente,
            ug_emitente_descricao::text as ug_emitente_descricao,
            ug_favorecido::text as ug_favorecido,
            ug_favorecido_descricao::text as ug_favorecido_descricao,
            pf_evento::text as pf_evento,
            pf_evento_descricao::text as pf_evento_descricao,
            pf::text as pf,
            pf_inscricao::text as pf_inscricao,
            pf_acao::text as pf_acao,
            pf_acao_descricao::text as pf_acao_descricao,
            pf_fonte_recursos::text as pf_fonte_recursos,
            pf_fonte_recursos_descricao::text as pf_fonte_recursos_descricao,
            doc_observacao::text as doc_observacao,
            {{ gov_bricks.parse_financial_value("pf_valor_linha") }} as pf_valor_linha,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("tesouro_gerencial", "pf_tesouro") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". A chave abaixo é a mesma
    -- `primary_key` que a DAG de ingestão declara, para que a definição de
    -- linha repetida seja única entre ingestão e transformação.
    versionado as (
        select
            pf_tesouro_raw.*,
            row_number() over (
                partition by
                    emissao_mes,
                    emissao_dia,
                    ug_emitente,
                    ug_favorecido,
                    pf_evento,
                    pf,
                    pf_inscricao,
                    pf_acao,
                    pf_fonte_recursos,
                    doc_observacao,
                    pf_valor_linha
                order by dt_ingest desc
            ) as nu_versao
        from pf_tesouro_raw
    )

select
    emissao_mes,
    emissao_dia,
    ug_emitente,
    ug_emitente_descricao,
    ug_favorecido,
    ug_favorecido_descricao,
    pf_evento,
    pf_evento_descricao,
    pf,
    pf_inscricao,
    pf_acao,
    pf_acao_descricao,
    pf_fonte_recursos,
    pf_fonte_recursos_descricao,
    doc_observacao,
    pf_valor_linha,
    dt_ingest
from versionado
where nu_versao = 1
