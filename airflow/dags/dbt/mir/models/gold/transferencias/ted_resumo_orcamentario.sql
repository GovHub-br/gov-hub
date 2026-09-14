{{ config(materialized="table") }}

-- Gold do MIR: resumo orçamentário e financeiro por número de transferência
-- de TED (com o plano de ação resolvido como atributo) — orçamento recebido/
-- devolvido (notas de crédito), execução (empenhos, com as UGs responsáveis
-- consolidadas em atributo), movimentação financeira (programação
-- financeira), com o programa de origem e a emenda parlamentar (quando
-- houver) que originou o recurso.
--
-- O modelo mais conectado desta migração: cruza transferegov_ted
-- (planos_acao_ted, programas_ted) e consome, do próprio dbt/mir/, nc_plano_
-- acao e empenhos_por_plano_acao (que por sua vez já cruzam tesouro_
-- gerencial + transferegov_ted), pf_unificado (idem) e numero_transferencia
-- (tesouro_gerencial + camara_deputados/senado_federal, migrado na fase de
-- transferegov_emendas/convenios). Cadeia completa de pacotes tocados,
-- transitivamente: transferegov_ted, tesouro_gerencial, camara_deputados,
-- senado_federal.
--
-- Portado de data-application-mir (dags/dbt/mir/models/empenhos_ted_dbt/
-- gold/ted_resumo_orcamentario.sql), reescrito pelo upstream (commits "fix:
-- remove fan-out de emendas" e "fix: consolida ted_resumo_orcamentario por
-- num_transf canonico e resolve plano via ponte") para corrigir dois
-- problemas que a versão anterior deste modelo (aqui e no repositório
-- antigo) tinha:
-- 1. `emendas` como `select * from numero_transferencia` direto: essa
-- fonte vem no grão NE x mês x movimento (várias linhas por
-- transferência) — um LEFT JOIN direto contra ela multiplicava linhas
-- do resumo por transferência (fan-out). Corrigido agregando `emendas`
-- ao grão de transferência canônica antes do join.
-- 2. Chave de junção `(plano_acao, num_transf)` via `full join ... using`
-- entre os 3 blocos de valores: cada bloco resolvia `plano_acao` de um
-- jeito ligeiramente diferente, então nem sempre batia — e como NULL
-- não casa com NULL em SQL, linhas com `plano_acao` não resolvido de
-- um lado se perdiam ou duplicavam. Corrigido trocando a chave para só
-- `num_transf_canon` (normalizado: cast para texto + remoção de zeros
-- à esquerda, mesmo padrão de `emendas_instrumentos_execucao.sql`) —
-- `plano_acao` vira atributo resolvido depois, via uma ponte dedicada
-- (`plano_por_transf`, com dedup 1:1 por `row_number`).
-- 3. UG responsável na chave de agregação dos empenhos: reintroduzia o
-- fan-out que o repositório antigo já havia corrigido. Ver o comentário
-- de `valores_empenhados_tb` abaixo.
--
-- planos_acao_ted e programas_ted viram ref("transferegov_ted", ...); os
-- demais já vivem neste mesmo projeto.
--
-- Consumido por dbt/mir/models/silver/convenios/instrumentos_emendas.sql e
-- dbt/mir/models/gold/convenios/emendas_instrumentos_execucao.sql, via ref
-- simples (mesmo projeto).
with
    planos_acao_deduplicado as (
        select
            id_plano_acao,
            id_programa,
            sq_instrumento as num_transf,
            sigla_unidade_descentralizada,
            vl_total_plano_acao,
            dt_ingest as dt_ingest_plano_acao
        from
            (
                select pa.*, row_number() over (partition by pa.id_plano_acao order by pa.dt_ingest desc) as rn
                from {{ ref("transferegov_ted", "planos_acao_ted") }} pa
            ) pa_filtrado
        where rn = 1
    ),

    programas_tb as (
        select
            pad.id_plano_acao,
            prog.sigla_unidade_responsavel_acompanhamento,
            prog.tx_nome_institucional_programa,
            prog.tx_objetivo_programa
        from planos_acao_deduplicado pad
        left join {{ ref("transferegov_ted", "programas_ted") }} prog using (id_programa)
    ),

    -- Ponte canônica num_transf -> plano_acao. num_transf_n_plano_acao já é
    -- 1:1 por transferência; deduplicamos defensivamente por num_transf_canon
    -- (row_number) para que o join de resolução do plano nunca reintroduza
    -- fan-out mesmo que a fonte venha a ter mais de um plano por transferência.
    plano_por_transf as (
        select num_transf_canon, plano_acao::integer as plano_acao
        from
            (
                select
                    ltrim(trim(cast(num_transf as text)), '0') as num_transf_canon,
                    plano_acao,
                    row_number() over (
                        partition by ltrim(trim(cast(num_transf as text)), '0') order by plano_acao
                    ) as rn
                from {{ ref("num_transf_n_plano_acao") }}
                where num_transf is not null
            ) t
        where rn = 1
    ),

    valor_firmado_tb as (
        select
            ltrim(trim(cast(num_transf as text)), '0') as num_transf_canon,
            max(vl_total_plano_acao) as valor_firmado,
            max(sigla_unidade_descentralizada) as sigla_unidade_descentralizada,
            max(dt_ingest_plano_acao) as dt_ingest_vf
        from planos_acao_deduplicado
        where num_transf is not null and ltrim(trim(cast(num_transf as text)), '0') <> ''
        group by ltrim(trim(cast(num_transf as text)), '0')
    ),

    valores_orcamentos_tb as (
        select
            ltrim(trim(cast(nc_transferencia as text)), '0') as num_transf_canon,
            sum(case when nc_evento in ('300301', '300307') then 0 else valor_celula end) as orcamento_recebido,
            sum(case when nc_evento in ('300301', '300307') then valor_celula else 0 end) as orcamento_devolvido,
            max(programa_governo) as programa_governo,
            max(programa_governo_descricao) as programa_governo_descricao,
            max(dt_ingest) as dt_ingest_vo
        from {{ ref("nc_plano_acao") }}
        where
            ptres not in ('-9')
            and nc_transferencia is not null
            and ltrim(trim(cast(nc_transferencia as text)), '0') <> ''
        group by ltrim(trim(cast(nc_transferencia as text)), '0')
    ),

    -- Agregado no grão da transferência canônica, igual aos demais blocos. A UG
    -- responsável NÃO entra no group by: quando estava na chave, a transferência
    -- com N UGs virava N linhas e os blocos de valor firmado, orçamento e
    -- financeiro — que só existem no grão da transferência — eram repetidos em
    -- cada linha, inflando qualquer soma sobre esta Gold (até +18% nos totais,
    -- número medido no repositório antigo quando o defeito foi corrigido lá).
    -- As UGs viram atributo consolidado (mesma convenção de string_agg +
    -- count(distinct) usada em convenios_consolidados e nas Golds de emendas);
    -- o detalhe por UG vive em ted_empenhos_plano_acao, que está no grão do
    -- empenho e traz ug_responsavel_codigo/ug_responsavel_nome por linha.
    -- ADR-0004/ADR-0009: métrica de Gold não pode depender de um grão que a
    -- fonte não tem.
    valores_empenhados_tb as (
        select
            ltrim(trim(cast(num_transf as text)), '0') as num_transf_canon,
            string_agg(
                distinct cast(ug_responsavel_codigo as text), ', ' order by cast(ug_responsavel_codigo as text)
            ) as ugs_responsaveis_codigos,
            string_agg(distinct ug_responsavel_nome, ', ' order by ug_responsavel_nome) as ugs_responsaveis_nomes,
            count(distinct ug_responsavel_codigo) as qtd_ugs_responsaveis,
            sum(case when despesas_empenhadas > 0 then despesas_empenhadas else 0 end) as empenhado,
            sum(case when despesas_empenhadas < 0 then - despesas_empenhadas else 0 end) as empenho_anulado,
            sum(despesas_pagas) as despesas_pagas_exercicio,
            sum(restos_a_pagar_pagos) as despesas_pagas_rap,
            sum(restos_a_pagar_inscritos) as restos_a_pagar,
            sum(despesas_liquidadas) as despesas_liquidada,
            max(dt_ingest) as dt_ingest_ve
        from {{ ref("empenhos_por_plano_acao") }}
        where num_transf is not null and ltrim(trim(cast(num_transf as text)), '0') <> ''
        group by ltrim(trim(cast(num_transf as text)), '0')
    ),

    valores_financeiro_tb as (
        select
            ltrim(trim(cast(pf_inscricao as text)), '0') as num_transf_canon,
            sum(
                case when substring(pf_acao_descricao, '(\w+) ') = 'TRANSFERENCIA' then pf_valor_linha else 0 end
            ) as financeiro_recebido,
            sum(
                case when substring(pf_acao_descricao, '(\w+) ') = 'DEVOLUCAO' then pf_valor_linha else 0 end
            ) as financeiro_devolvido,
            sum(
                case when substring(pf_acao_descricao, '(\w+) ') = 'CANCELAMENTO' then pf_valor_linha else 0 end
            ) as financeiro_cancelado,
            max(dt_ingest) as dt_ingest_vfin
        from {{ ref("pf_unificado") }}
        where pf_inscricao is not null and ltrim(trim(cast(pf_inscricao as text)), '0') <> ''
        group by ltrim(trim(cast(pf_inscricao as text)), '0')
    ),

    emendas as (
        -- numero_transferencia vem no grão NE x mês x movimento (várias
        -- linhas por transferência). Agregamos ao grão de transferência
        -- canônica para não introduzir fan-out no join final: o resumo só
        -- precisa saber se há emenda e quais autores, então consolidamos
        -- preservando os autores sem multiplicar linhas.
        select
            ltrim(trim(cast(numero_transferencia as text)), '0') as num_transf_canon,
            bool_or(id_autor is not null) as tem_autor,
            string_agg(distinct autor_emendas_orcamento::text, ', ' order by autor_emendas_orcamento::text) filter (
                where id_autor is not null
            ) as autor_emendas_orcamento
        from {{ ref("numero_transferencia") }}
        where numero_transferencia is not null
        group by ltrim(trim(cast(numero_transferencia as text)), '0')
    ),

    -- Consolidação dos quatro blocos por num_transf_canon (a transferência é
    -- a única chave de junção). plano_acao NÃO entra na chave: era a causa
    -- do join estrutural quebrado (NULL não casa com NULL) e é resolvido
    -- depois via a ponte plano_por_transf. Os quatro blocos estão todos no
    -- grão da transferência, então o join é 1:1 e nenhuma métrica é duplicada.
    join_parcial as (
        select
            num_transf_canon,
            ve.ugs_responsaveis_codigos,
            ve.ugs_responsaveis_nomes,
            ve.qtd_ugs_responsaveis,
            vf.valor_firmado,
            vf.sigla_unidade_descentralizada,
            vo.orcamento_recebido,
            vo.orcamento_devolvido,
            vo.programa_governo,
            vo.programa_governo_descricao,
            ve.empenhado,
            ve.empenho_anulado,
            ve.despesas_pagas_exercicio,
            ve.despesas_pagas_rap,
            ve.restos_a_pagar,
            ve.despesas_liquidada,
            vfin.financeiro_recebido,
            vfin.financeiro_devolvido,
            vfin.financeiro_cancelado,
            greatest(vf.dt_ingest_vf, vo.dt_ingest_vo, ve.dt_ingest_ve, vfin.dt_ingest_vfin) as dt_ingest_jp
        from valores_empenhados_tb ve
        full join valores_orcamentos_tb vo using (num_transf_canon)
        full join valores_financeiro_tb vfin using (num_transf_canon)
        full join valor_firmado_tb vf using (num_transf_canon)
    )

select
    ppt.plano_acao,
    jp.num_transf_canon as num_transf,
    jp.ugs_responsaveis_codigos,
    jp.ugs_responsaveis_nomes,
    jp.qtd_ugs_responsaveis,
    jp.sigla_unidade_descentralizada,
    jp.valor_firmado,
    jp.orcamento_recebido,
    jp.orcamento_devolvido,
    jp.empenhado,
    jp.empenho_anulado,
    jp.despesas_pagas_exercicio,
    jp.despesas_pagas_rap,
    jp.restos_a_pagar,
    jp.despesas_liquidada,
    jp.financeiro_recebido,
    jp.financeiro_devolvido,
    jp.financeiro_cancelado,
    jp.dt_ingest_jp as dt_ingest,
    prog.sigla_unidade_responsavel_acompanhamento,
    prog.tx_nome_institucional_programa,
    prog.tx_objetivo_programa,
    jp.programa_governo,
    jp.programa_governo_descricao,
    case when e.tem_autor then 'Emenda - ' || e.autor_emendas_orcamento else 'Recurso Próprio' end as origem
from join_parcial jp
left join plano_por_transf ppt using (num_transf_canon)
left join programas_tb prog on prog.id_plano_acao = ppt.plano_acao
left join emendas e using (num_transf_canon)
where jp.num_transf_canon is not null
