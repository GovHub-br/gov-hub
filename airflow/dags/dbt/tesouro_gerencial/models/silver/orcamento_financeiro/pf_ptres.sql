{{ config(materialized="table") }}

-- Silver de tesouro_gerencial: programação de ação por PTRES do exercício
-- corrente, tipada a partir da Bronze.
--
-- Sem cruzamento com nenhum outro sistema — mesmo racional de pf_tesouro.sql
-- (ver cabeçalho daquele arquivo). Consumido por nc_unificado.sql, em
-- dbt/mir/models/silver/transferencias/.
--
-- Portado de data-application-mir (dags/dbt/mir/models/empenhos_ted_dbt/
-- bronze/pf_ptres.sql).
with
    pf_ptres_raw as (
        select
            programa_governo::text as programa_governo,
            programa_governo_descricao::text as programa_governo_descricao,
            plano_orcamentario::text as plano_orcamentario,
            plano_orcamentario_descricao_1::text as plano_orcamentario_descricao_1,
            plano_orcamentario_descricao_2::text as plano_orcamentario_descricao_2,
            plano_orcamentario_descricao_3::text as plano_orcamentario_descricao_3,
            plano_orcamentario_descricao_4::text as plano_orcamentario_descricao_4,
            plano_orcamentario_descricao_5::text as plano_orcamentario_descricao_5,
            plano_orcamentario_descricao_6::text as plano_orcamentario_descricao_6,
            acao_governo::text as acao_governo,
            acao_governo_descricao::text as acao_governo_descricao,
            ptres::text as ptres,
            natureza_despesa::text as natureza_despesa,
            natureza_despesa_descricao::text as natureza_despesa_descricao,
            {{ gov_bricks.parse_financial_value("dotacao_inicial") }} as dotacao_inicial,
            {{ gov_bricks.parse_financial_value("dotacao_suplementar") }} as dotacao_suplementar,
            {{ gov_bricks.parse_financial_value("dotacao_atualizada") }} as dotacao_atualizada,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("tesouro_gerencial", "programacao_acao_ptres") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". A chave abaixo é a mesma
    -- `primary_key` que a DAG de ingestão declara, para que a definição de
    -- linha repetida seja única entre ingestão e transformação.
    versionado as (
        select
            pf_ptres_raw.*,
            row_number() over (
                partition by
                    programa_governo,
                    plano_orcamentario,
                    acao_governo,
                    ptres,
                    natureza_despesa,
                    dotacao_inicial,
                    dotacao_suplementar,
                    dotacao_atualizada
                order by dt_ingest desc
            ) as nu_versao
        from pf_ptres_raw
    )

select
    programa_governo,
    programa_governo_descricao,
    plano_orcamentario,
    plano_orcamentario_descricao_1,
    plano_orcamentario_descricao_2,
    plano_orcamentario_descricao_3,
    plano_orcamentario_descricao_4,
    plano_orcamentario_descricao_5,
    plano_orcamentario_descricao_6,
    acao_governo,
    acao_governo_descricao,
    ptres,
    natureza_despesa,
    natureza_despesa_descricao,
    dotacao_inicial,
    dotacao_suplementar,
    dotacao_atualizada,
    dt_ingest
from versionado
where nu_versao = 1
