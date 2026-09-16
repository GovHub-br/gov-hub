{{ config(materialized="table") }}

-- Gold do MIR: empenhos já associados a um plano de ação de TED (recorte de
-- empenhos_por_plano_acao.sql, que também traz empenhos sem vínculo
-- resolvido).
--
-- Único ref é empenhos_por_plano_acao, já migrado para este mesmo projeto
-- (dbt/mir/models/silver/transferencias/) — ref simples.
--
-- Portado de data-application-mir (dags/dbt/mir/models/empenhos_ted_dbt/
-- gold/ted_empenhos_plano_acao.sql), com as mesmas colunas do original.
--
-- ug_responsavel_codigo/nome e as cinco colunas plano_orcamentario_codigo_*
-- vêm do Silver: estão em `bronze_columns` e em `narrow_passthrough`
-- (empenhos_por_plano_acao.sql), e `result_table` é um `select distinct er.*`
-- sobre a cascata de métodos, então elas chegam até aqui. Um comentário
-- anterior deste arquivo afirmava o contrário e as omitia; a afirmação era
-- falsa — ted_resumo_orcamentario.sql já consome ug_responsavel_codigo/nome
-- do mesmo Silver.
--
-- Este é o modelo de detalhe por UG do domínio de TED: ted_resumo_orcamentario
-- consolida as UGs em atributo para não inflar suas somas, e quem precisa da
-- execução quebrada por UG lê aqui, que está no grão do empenho.
with
    empenhos_mir as (
        select
            emissao_mes,
            emissao_dia,
            ne_ccor,
            ug_responsavel_codigo,
            ug_responsavel_nome,
            plano_orcamentario_codigo_uo,
            plano_orcamentario_codigo_funcao,
            plano_orcamentario_codigo_subfuncao,
            plano_orcamentario_codigo_programa,
            plano_orcamentario_codigo_acao,
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
            ne,
            orgao_id,
            nc,
            num_transf,
            plano_acao,
            dt_ingest
        from {{ ref("empenhos_por_plano_acao") }}
        where plano_acao is not null
    )

select *
from empenhos_mir
