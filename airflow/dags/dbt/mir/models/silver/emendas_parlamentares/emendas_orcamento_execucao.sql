{{ config(materialized="table") }}

-- Silver do MIR: junta orçamento (dotado) e execução (empenhado/liquidado/
-- pago) das emendas parlamentares no MESMO grão: a classificação
-- orçamentária (programa, ação, localizador, natureza, modalidade, fonte,
-- ptres).
--
-- Cruza dois sistemas (tesouro_gerencial + camara_deputados/senado_federal
-- via parlamentares_historico) — vive no projeto do órgão, não em nenhum
-- pacote de sistema (ADR-0004/0009).
--
-- Portado de data-application-mir (dags/dbt/mir/models/emendas_dbt/silver/
-- emendas_orcamento_execucao.sql). O macro name_formater (TRIM + UPPER +
-- TRANSLATE de acentos) não existe neste repositório — mesma situação já
-- resolvida em parlamentares_historico.sql — então a expressão foi embutida
-- diretamente aqui, com o mesmo comportamento.
--
-- Regra de negócio:
-- - A dotação (itens 9/13) é definida no grão da classificação, sem
-- empenho. Uma classificação mapeia para exatamente um autor de emenda.
-- - Vários empenhos executam contra a mesma classificação. Por isso a
-- execução é AGREGADA a esse grão antes de juntar — evita repetir a
-- dotação por empenho (dupla contagem ao somar).
-- - A base é a dotação (LEFT JOIN execução): linhas dotadas mas ainda não
-- empenhadas aparecem com execução = 0. O caminho inverso perderia essas
-- linhas.
-- - A UG executora NÃO faz parte do grão. Ela pertence ao empenho, não à
-- classificação: mantê-la no `group by` da execução devolvia uma linha por
-- (classificação × UG) e repetia a dotação em cada uma delas (dupla
-- contagem). As UGs viram atributo concatenado + qtd_ugs_responsaveis.
with
    dotacao as (
        select
            programa_governo,
            acao_governo,
            localizador_gasto,
            natureza_despesa,
            modalidade_aplicacao,
            fonte_recursos_detalhada,
            ptres,
            -- Atributos função da classificação (1:1) — max() é só para
            -- reduzir ao grão sem precisar agrupar por texto.
            max(programa_governo_descricao) as programa_governo_descricao,
            max(acao_governo_descricao) as acao_governo_descricao,
            max(autor_emendas_orcamento) as autor_emendas_orcamento,
            max(autor_emendas_orcamento_descricao) as autor_emendas_orcamento_descricao,
            max(autor_emendas_orcamento_nome) as autor_emendas_orcamento_nome,
            max(localizador_gasto_descricao) as localizador_gasto_descricao,
            max(regiao_pt) as regiao_pt,
            max(uf_pt) as uf_pt,
            max(uf_pt_descricao) as uf_pt_descricao,
            max(municipio_pt) as municipio_pt,
            max(grupo_despesa) as grupo_despesa,
            max(grupo_despesa_descricao) as grupo_despesa_descricao,
            max(natureza_despesa_descricao) as natureza_despesa_descricao,
            max(modalidade_aplicacao_descricao) as modalidade_aplicacao_descricao,
            max(fonte_recursos_detalhada_descricao) as fonte_recursos_detalhada_descricao,
            sum(dotacao_inicial) as dotacao_inicial,
            sum(dotacao_atualizada) as dotacao_atualizada,
            max(dt_ingest) as dt_ingest
        from {{ ref("tesouro_gerencial", "tg_emendas_dotacao") }}
        group by
            programa_governo,
            acao_governo,
            localizador_gasto,
            natureza_despesa,
            modalidade_aplicacao,
            fonte_recursos_detalhada,
            ptres
    ),

    execucao as (
        select
            codigo_programa as programa_governo,
            codigo_acao_ajustada as acao_governo,
            localizador_gasto,
            natureza_despesa,
            codigo_modalidade as modalidade_aplicacao,
            fonte_recursos_detalhada,
            ptres,
            -- UGs executoras da classificação concatenadas (atributo): a UG NÃO
            -- entra no grão para não repetir a dotação por UG no join abaixo —
            -- cada UG a mais duplicaria a linha dotada e inflaria as somas. O
            -- detalhe de quanto cada UG executou vive na Gold
            -- emendas_execucao_por_ug.
            string_agg(
                distinct cast(ug_responsavel_codigo as text), ', ' order by cast(ug_responsavel_codigo as text)
            ) as ug_responsavel_codigo,
            string_agg(distinct ug_responsavel_nome, ', ' order by ug_responsavel_nome) as ug_responsavel_nome,
            count(distinct ug_responsavel_codigo) as qtd_ugs_responsaveis,
            sum(despesas_empenhadas) as despesas_empenhadas,
            sum(despesas_liquidadas) as despesas_liquidadas,
            sum(despesas_pagas) as despesas_pagas,
            sum(restos_a_pagar_inscritos) as restos_a_pagar_inscritos,
            sum(restos_a_pagar_pagos) as restos_a_pagar_pagos,
            max(dt_ingest) as dt_ingest
        from {{ ref("emendas_partidos") }}
        group by
            codigo_programa,
            codigo_acao_ajustada,
            localizador_gasto,
            natureza_despesa,
            codigo_modalidade,
            fonte_recursos_detalhada,
            ptres
    ),

    -- Um registro por parlamentar (filiação mais recente), para atribuir a
    -- emenda ao autor via nome. Como o modelo é agregado no ano, não há data
    -- de emissão para priorizar por vigência — usamos a filiação mais
    -- recente.
    parlamentar as (
        select distinct
            on (chave_join_nome)
            chave_join_nome,
            id_parlamentar,
            cargo_parlamentar,
            nome_parlamentar,
            sigla_partido,
            uf_parlamentar,
            url_foto,
            email,
            url_logo_partido
        from {{ ref("parlamentares_historico") }}
        order by chave_join_nome, data_filiacao desc nulls last
    )

select
    -- Classificação orçamentária (grão)
    d.programa_governo as codigo_programa,
    d.programa_governo_descricao as programa,
    d.acao_governo as codigo_acao,
    d.acao_governo_descricao as acao,
    d.localizador_gasto,
    d.localizador_gasto_descricao,
    d.regiao_pt,
    d.uf_pt as uf,
    d.uf_pt_descricao as uf_descricao,
    d.municipio_pt as municipio,
    d.grupo_despesa as codigo_gnd,
    d.grupo_despesa_descricao as gnd,
    d.natureza_despesa,
    d.natureza_despesa_descricao,
    d.modalidade_aplicacao as codigo_modalidade,
    d.modalidade_aplicacao_descricao as modalidade,
    d.ptres,
    d.fonte_recursos_detalhada,
    d.fonte_recursos_detalhada_descricao,

    -- Unidade(s) Gestora(s) executora(s) da classificação (concatenadas)
    e.ug_responsavel_codigo,
    e.ug_responsavel_nome,
    coalesce(e.qtd_ugs_responsaveis, 0) as qtd_ugs_responsaveis,

    -- Autor da emenda
    d.autor_emendas_orcamento,
    d.autor_emendas_orcamento_descricao,
    d.autor_emendas_orcamento_nome,

    -- Orçamento (dotado)
    d.dotacao_inicial,
    d.dotacao_atualizada,

    -- Execução (0 quando dotado mas ainda não empenhado)
    coalesce(e.despesas_empenhadas, 0)::numeric(15, 2) as despesas_empenhadas,
    coalesce(e.despesas_liquidadas, 0)::numeric(15, 2) as despesas_liquidadas,
    coalesce(e.despesas_pagas, 0)::numeric(15, 2) as despesas_pagas,
    coalesce(e.restos_a_pagar_inscritos, 0)::numeric(15, 2) as restos_a_pagar_inscritos,
    coalesce(e.restos_a_pagar_pagos, 0)::numeric(15, 2) as restos_a_pagar_pagos,

    -- Indicadores orçamento x execução
    (d.dotacao_atualizada - coalesce(e.despesas_empenhadas, 0))::numeric(15, 2) as saldo_a_empenhar,
    round(coalesce(e.despesas_empenhadas, 0) / nullif(d.dotacao_atualizada, 0), 4) as percentual_empenhado,
    round(coalesce(e.despesas_pagas, 0) / nullif(d.dotacao_atualizada, 0), 4) as percentual_pago,

    -- Parlamentar
    p.id_parlamentar as id_autor,
    p.cargo_parlamentar as cargo_autor,
    p.nome_parlamentar as autor,
    p.sigla_partido as partido,
    p.uf_parlamentar as uf_autor,
    p.url_foto as url_foto_autor,
    p.email as email_autor,
    p.url_logo_partido as url_foto_partido,

    greatest(d.dt_ingest, coalesce(e.dt_ingest, d.dt_ingest)) as dt_ingest

from dotacao d
left join
    execucao e
    on d.programa_governo = e.programa_governo
    and d.acao_governo = e.acao_governo
    and d.localizador_gasto = e.localizador_gasto
    and d.natureza_despesa = e.natureza_despesa
    and d.modalidade_aplicacao = e.modalidade_aplicacao
    and d.fonte_recursos_detalhada = e.fonte_recursos_detalhada
    and d.ptres = e.ptres
left join
    parlamentar p
    on trim(translate(upper(d.autor_emendas_orcamento_nome), 'ÁÀÂÃÄÅÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ', 'AAAAAAEEEEIIIIOOOOOUUUUCN'))
    = p.chave_join_nome
