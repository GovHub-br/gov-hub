-- Silver do MIR: notas de empenho do SIAFI filtradas pelas UGs do MIR.
--
-- Filtra o próprio pacote de sistema (tesouro_gerencial) pelas UASGs do MIR
-- (230002 e 810008), sem cruzar nenhum outro pacote — por isso vive dentro
-- de dbt/tesouro_gerencial/mir/ (ADR-0004, situação 2: sistema compartilhado,
-- modelo específico de um órgão), não no projeto do órgão (dbt/mir/): só
-- passaria a exigir o projeto do órgão se cruzasse outro sistema.
--
-- Portado de data-application-mir (compras_gov_dbt/bronze/empenhos_tesouro.sql).
-- Granularidade: uma linha por nota de empenho da UG do MIR.
with
    empenhos_tesouro_raw as (
        select
            programa_governo::text as programa_governo,
            programa_governo_descricao::text as programa_governo_descricao,
            acao_governo::text as acao_governo,
            acao_governo_descricao::text as acao_governo_descricao,
            emissao_mes::text as emissao_mes,
            emissao_dia::text as emissao_dia,
            ne_ccor::text as ne_ccor,
            regexp_replace(ne_num_processo, '[./-]', '', 'g') as ne_num_processo,
            ne_info_complementar::text as ne_info_complementar,
            ne_ccor_descricao::text as ne_ccor_descricao,
            doc_observacao::text as doc_observacao,
            natureza_despesa::text as natureza_despesa,
            natureza_despesa_descricao::text as natureza_despesa_descricao,
            upper(ne_ccor_favorecido::text) as ne_ccor_favorecido,
            ne_ccor_favorecido_descricao::text as ne_ccor_favorecido_descricao,
            ne_ccor_ano_emissao::integer as ne_ccor_ano_emissao,
            ptres::text as ptres,
            fonte_recursos_detalhada::text as fonte_recursos_detalhada,
            fonte_recursos_detalhada_descricao::text as fonte_recursos_detalhada_descricao,
            {{ gov_bricks.parse_financial_value("despesas_empenhadas") }} as despesas_empenhadas,
            {{ gov_bricks.parse_financial_value("despesas_liquidadas") }} as despesas_liquidadas,
            {{ gov_bricks.parse_financial_value("despesas_pagas") }} as despesas_pagas,
            {{ gov_bricks.parse_financial_value("restos_a_pagar_inscritos") }} as restos_a_pagar_inscritos,
            {{ gov_bricks.parse_financial_value("restos_a_pagar_pagos") }} as restos_a_pagar_pagos,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("tesouro_gerencial", "ne_tesouro") }}
        where left(ne_ccor, 6) in ('230002', '810008') and ne_ccor_ano_emissao ~ '^[0-9]{4}$'
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". A chave abaixo é a mesma
    -- `primary_key` que a DAG de ingestão declara, para que a definição de
    -- linha repetida seja única entre ingestão e transformação.
    versionado as (
        select
            empenhos_tesouro_raw.*,
            row_number() over (
                partition by
                    ne_ccor,
                    natureza_despesa,
                    doc_observacao,
                    ne_ccor_ano_emissao,
                    emissao_dia,
                    emissao_mes,
                    despesas_empenhadas,
                    despesas_liquidadas,
                    despesas_pagas
                order by dt_ingest desc
            ) as nu_versao
        from empenhos_tesouro_raw
    )

select
    programa_governo,
    programa_governo_descricao,
    acao_governo,
    acao_governo_descricao,
    emissao_mes,
    emissao_dia,
    ne_ccor,
    ne_num_processo,
    ne_info_complementar,
    ne_ccor_descricao,
    doc_observacao,
    natureza_despesa,
    natureza_despesa_descricao,
    ne_ccor_favorecido,
    ne_ccor_favorecido_descricao,
    ne_ccor_ano_emissao,
    ptres,
    fonte_recursos_detalhada,
    fonte_recursos_detalhada_descricao,
    despesas_empenhadas,
    despesas_liquidadas,
    despesas_pagas,
    restos_a_pagar_inscritos,
    restos_a_pagar_pagos,
    dt_ingest
from versionado
where nu_versao = 1
