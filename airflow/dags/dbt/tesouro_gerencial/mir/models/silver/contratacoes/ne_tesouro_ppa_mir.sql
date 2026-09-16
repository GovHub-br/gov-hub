-- Silver do MIR: notas de empenho do relatório "Notas de empenhos por
-- programa PPA" do Tesouro Gerencial (fonte: tesouro_gerencial.ne_tesouro_ppa).
--
-- Relatório distinto de empenhos_tesouro_mir.sql (fonte: ne_tesouro): já sai
-- escopado às UGs do MIR na origem, sem precisar de filtro por UASG aqui.
-- Reúne os dois grãos que vêm na tabela raw: grão de empenho (ne_ccor <>
-- '-9', com despesas_*/restos_a_pagar_* preenchidos) e grão de dotação
-- (ne_ccor = '-9', com dotacao_atualizada preenchida) — mesma convenção do
-- pacote. Acrescenta UG responsável, classificação do plano orçamentário e
-- resultado EOF, ausentes em empenhos_tesouro_mir.sql.
--
-- Portado de data-application-mir (dags/dbt/mir/models/empenhos_ted_dbt/
-- bronze/ppa_tesouro.sql). Vive em dbt/tesouro_gerencial/mir/ (ADR-0004,
-- situação 2: sistema compartilhado, modelo específico do MIR), assim como
-- empenhos_tesouro_mir.sql — nenhum dos dois cruza outro sistema aqui.
with
    ppa_tesouro_raw as (
        select
            programa_governo::text as programa_governo,
            programa_governo_descricao::text as programa_governo_descricao,
            acao_governo::text as acao_governo,
            acao_governo_descricao::text as acao_governo_descricao,
            emissao_mes::text as emissao_mes,
            emissao_dia::text as emissao_dia,
            ne_ccor::text as ne_ccor,
            ug_responsavel_codigo::text as ug_responsavel_codigo,
            ug_responsavel_nome::text as ug_responsavel_nome,
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
            plano_orcamentario_codigo_uo::text as plano_orcamentario_codigo_uo,
            plano_orcamentario_codigo_funcao::text as plano_orcamentario_codigo_funcao,
            plano_orcamentario_codigo_subfuncao::text as plano_orcamentario_codigo_subfuncao,
            plano_orcamentario_codigo_programa::text as plano_orcamentario_codigo_programa,
            plano_orcamentario_codigo_acao::text as plano_orcamentario_codigo_acao,
            plano_orcamentario_codigo_po::text as plano_orcamentario_codigo_po,
            plano_orcamentario_nome::text as plano_orcamentario_nome,
            resultado_eof_codigo::integer as resultado_eof_codigo,
            resultado_eof_nome::text as resultado_eof_nome,
            grupo_despesa::integer as grupo_despesa,
            grupo_despesa_desc::text as grupo_despesa_desc,
            {{ gov_bricks.parse_financial_value("dotacao_atualizada") }} as dotacao_atualizada,
            {{ gov_bricks.parse_financial_value("despesas_empenhadas") }} as despesas_empenhadas,
            {{ gov_bricks.parse_financial_value("despesas_liquidadas") }} as despesas_liquidadas,
            {{ gov_bricks.parse_financial_value("despesas_pagas") }} as despesas_pagas,
            {{ gov_bricks.parse_financial_value("restos_a_pagar_inscritos") }} as restos_a_pagar_inscritos,
            {{ gov_bricks.parse_financial_value("restos_a_pagar_pagos") }} as restos_a_pagar_pagos,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("tesouro_gerencial", "ne_tesouro_ppa") }}
        -- O filtro garante apenas que o ano seja um inteiro válido para o
        -- cast (empenhos trazem AAAA; dotação traz o sentinela -9).
        where ne_ccor_ano_emissao ~ '^-?[0-9]+$'
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". A chave abaixo é a mesma
    -- `primary_key` que a DAG de ingestão declara, para que a definição de
    -- linha repetida seja única entre ingestão e transformação.
    versionado as (
        select
            ppa_tesouro_raw.*,
            row_number() over (
                partition by
                    ne_ccor,
                    natureza_despesa,
                    doc_observacao,
                    ne_ccor_ano_emissao,
                    emissao_dia,
                    emissao_mes,
                    ne_ccor_favorecido,
                    fonte_recursos_detalhada,
                    ptres,
                    plano_orcamentario_codigo_po,
                    grupo_despesa,
                    dotacao_atualizada,
                    despesas_empenhadas,
                    despesas_liquidadas,
                    despesas_pagas,
                    restos_a_pagar_inscritos,
                    restos_a_pagar_pagos
                order by dt_ingest desc
            ) as nu_versao
        from ppa_tesouro_raw
    )

select
    programa_governo,
    programa_governo_descricao,
    acao_governo,
    acao_governo_descricao,
    emissao_mes,
    emissao_dia,
    ne_ccor,
    ug_responsavel_codigo,
    ug_responsavel_nome,
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
    plano_orcamentario_codigo_uo,
    plano_orcamentario_codigo_funcao,
    plano_orcamentario_codigo_subfuncao,
    plano_orcamentario_codigo_programa,
    plano_orcamentario_codigo_acao,
    plano_orcamentario_codigo_po,
    plano_orcamentario_nome,
    resultado_eof_codigo,
    resultado_eof_nome,
    grupo_despesa,
    grupo_despesa_desc,
    dotacao_atualizada,
    despesas_empenhadas,
    despesas_liquidadas,
    despesas_pagas,
    restos_a_pagar_inscritos,
    restos_a_pagar_pagos,
    dt_ingest
from versionado
where nu_versao = 1
