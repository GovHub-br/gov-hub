{{ config(materialized="table") }}

-- Silver do MIR: cada linha de tg_emendas (grão de empenho) cruzada com o
-- autor da emenda em parlamentares_historico, respeitando a vigência de
-- filiação partidária na data do empenho. Também traz, junto de cada
-- empenho, a dotação agregada da mesma classificação orçamentária (mesmo
-- valor se repete entre empenhos da classificação — NÃO somar por empenho;
-- para totais corretos use emendas_orcamento_execucao).
--
-- Cruza dois sistemas (tesouro_gerencial + camara_deputados/senado_federal
-- via parlamentares_historico) — vive no projeto do órgão, não em nenhum
-- pacote de sistema (ADR-0004/0009). É a base de numero_transferencia.sql
-- (dbt/mir/models/silver/convenios/), que extrai o número do
-- convênio/TED/termo de fomento do texto da emenda.
--
-- Portado de data-application-mir (dags/dbt/mir/models/emendas_dbt/silver/
-- emendas_partidos.sql). emissao_dia já chega de tg_emendas como date (ver
-- aquele modelo, que aplica gov_bricks.parse_date/to_date) — emissao_dia_data
-- é só um alias para uso nas comparações de vigência de filiação abaixo. O
-- macro name_formater também não existe neste repositório — mesma situação
-- já resolvida em parlamentares_historico.sql — e foi embutido diretamente
-- aqui.
with
    tg_emendas as (select * from {{ ref("tesouro_gerencial", "tg_emendas") }}),

    parlamentares_hist as (select * from {{ ref("parlamentares_historico") }}),

    -- UG responsável pela NE, agregada do relatório PPA (que não filtra por
    -- UASG e traz a UG explicitamente) — tg_emendas não tem essa coluna.
    ug_por_ne_ccor as (
        select ne_ccor, ug_responsavel_codigo, ug_responsavel_nome
        from {{ ref("tesouro_gerencial", "ne_tesouro_ppa_mir") }}
        where ne_ccor <> '-9'
        group by ne_ccor, ug_responsavel_codigo, ug_responsavel_nome
    ),

    -- Dotação agregada no grão da classificação orçamentária.
    dotacao_por_classificacao as (
        select
            programa_governo,
            acao_governo,
            localizador_gasto,
            natureza_despesa,
            modalidade_aplicacao,
            fonte_recursos_detalhada,
            ptres,
            sum(dotacao_inicial) as dotacao_inicial,
            sum(dotacao_atualizada) as dotacao_atualizada
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

    tg_emendas_tratado as (
        select
            *,
            trim(
                translate(upper(autor_emendas_orcamento_nome), 'ÁÀÂÃÄÅÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ', 'AAAAAAEEEEIIIIOOOOOUUUUCN')
            ) as chave_join_nome,
            emissao_dia as emissao_dia_data,
            row_number() over () as emenda_id
        from tg_emendas
    ),

    cruzamento_bruto as (
        select
            e.emissao_mes,
            e.emissao_dia,
            e.programa_governo as codigo_programa,
            e.programa_governo_descricao as programa,
            e.acao_governo as codigo_acao_ajustada,
            e.acao_governo_descricao as acao_ajustada,
            e.autor_emendas_orcamento_descricao,
            e.localizador_gasto,
            e.localizador_gasto_descricao,
            e.regiao_pt,
            e.uf_pt as uf,
            e.uf_pt_descricao as uf_descricao,
            e.municipio_pt as municipio,
            'Brasil' as pais,
            e.ne_ccor,
            e.ne_num_processo,
            e.ne_info_complementar,
            e.ne_ccor_descricao,
            e.doc_observacao,
            e.grupo_despesa as codigo_gnd,
            e.grupo_despesa_descricao as gnd,
            e.natureza_despesa,
            e.natureza_despesa_descricao,
            e.modalidade_aplicacao as codigo_modalidade,
            e.modalidade_aplicacao_descricao as modalidade,
            e.ne_ccor_favorecido,
            e.ne_ccor_favorecido_descricao,
            e.ne_ccor_ano_emissao,
            e.ptres,
            e.fonte_recursos_detalhada,
            e.fonte_recursos_detalhada_descricao,
            dot.dotacao_inicial,
            dot.dotacao_atualizada,
            e.despesas_empenhadas,
            e.despesas_liquidadas,
            e.despesas_pagas,
            e.restos_a_pagar_inscritos,
            e.restos_a_pagar_pagos,
            e.autor_emendas_orcamento_nome,
            e.autor_emendas_orcamento,
            e.emenda_id,

            ug.ug_responsavel_codigo,
            ug.ug_responsavel_nome,

            p.id_parlamentar as id_autor,
            p.cargo_parlamentar as cargo_autor,
            p.nome_parlamentar as autor,
            p.sigla_partido as partido,
            p.uf_parlamentar as uf_autor,
            p.url_foto as url_foto_autor,
            p.email as email_autor,
            p.url_logo_partido as url_foto_partido,

            e.dt_ingest,

            -- Prioridade de cruzamento
            case
                when
                    e.emissao_dia_data >= p.data_filiacao::date
                    and e.emissao_dia_data <= coalesce(p.data_desfiliacao::date, current_date)
                then 1
                -- Se achou nome, mas a data não bateu
                when p.id_parlamentar is not null
                then 2
                -- Nomes que nem existem
                else 3
            end as prioridade_match,

            -- Distância de fallback para quando não tivermos batido o range
            least(
                abs(extract(epoch from (e.emissao_dia_data::timestamptz - p.data_filiacao))),
                abs(
                    extract(
                        epoch from (e.emissao_dia_data::timestamptz - coalesce(p.data_desfiliacao, current_timestamp))
                    )
                )
            ) as distancia_tempo

        from tg_emendas_tratado e
        left join parlamentares_hist p on e.chave_join_nome = p.chave_join_nome
        left join ug_por_ne_ccor ug on e.ne_ccor = ug.ne_ccor
        left join
            dotacao_por_classificacao dot
            on e.programa_governo = dot.programa_governo
            and e.acao_governo = dot.acao_governo
            and e.localizador_gasto = dot.localizador_gasto
            and e.natureza_despesa = dot.natureza_despesa
            and e.modalidade_aplicacao = dot.modalidade_aplicacao
            and e.fonte_recursos_detalhada = dot.fonte_recursos_detalhada
            and e.ptres = dot.ptres
    ),

    deduplicado as (
        select *
        from
            (
                select
                    *,
                    row_number() over (partition by emenda_id order by prioridade_match asc, distancia_tempo asc) as rn
                from cruzamento_bruto
            ) sub
        where rn = 1
    )

select
    emissao_mes,
    emissao_dia,
    codigo_programa,
    programa,
    codigo_acao_ajustada,
    acao_ajustada,
    autor_emendas_orcamento_descricao,
    autor_emendas_orcamento_nome,

    ug_responsavel_codigo,
    ug_responsavel_nome,

    localizador_gasto,
    localizador_gasto_descricao,
    regiao_pt,
    uf,
    uf_descricao,
    municipio,
    pais,
    ne_ccor,
    ne_num_processo,
    ne_info_complementar,
    ne_ccor_descricao,
    doc_observacao,
    codigo_gnd,
    gnd,
    natureza_despesa,
    natureza_despesa_descricao,
    codigo_modalidade,
    modalidade,
    ne_ccor_favorecido,
    ne_ccor_favorecido_descricao,
    ne_ccor_ano_emissao,
    ptres,
    fonte_recursos_detalhada,
    fonte_recursos_detalhada_descricao,
    dotacao_inicial,
    dotacao_atualizada,
    despesas_empenhadas,
    despesas_liquidadas,
    despesas_pagas,
    restos_a_pagar_inscritos,
    restos_a_pagar_pagos,
    autor_emendas_orcamento,
    id_autor,
    cargo_autor,
    autor,
    partido,
    uf_autor,
    url_foto_autor,
    email_autor,
    url_foto_partido,
    dt_ingest
from deduplicado
