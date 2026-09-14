-- Silver do MIR: pivot de convênios do SICONV — cruza o pacote siconv com o
-- pacote tesouro_gerencial, por isso vive em dbt/mir/, não em dbt/siconv/
-- (ADR-0004: modelo que cruza pacote sobe para o projeto do órgão). Todos os
-- demais modelos de convenios/ desta pasta partem deste.
--
-- O cruzamento com o SIAFI é feito via ne_tesouro_ppa_mir (Silver do pacote
-- tesouro_gerencial, relatório PPA já escopado ao MIR na origem — ver
-- ne_tesouro_ppa_mir.sql), e não por um `source()` direto do pacote
-- tesouro_gerencial: mesmo padrão já usado por contratos_empenhos.sql para
-- acessar dados do SIAFI a partir de dbt/mir/. O `source("siafi",
-- "ne_tesouro")` do repositório antigo vira, portanto, o
-- `ref("tesouro_gerencial", "ne_tesouro_ppa_mir")` abaixo (upstream trocou
-- de empenhos_tesouro_ted/empenhos_tesouro_mir para ppa_tesouro/
-- ne_tesouro_ppa_mir no mesmo commit que unificou o relatório PPA) — que já
-- traz as colunas necessárias (ne_ccor, ne_info_complementar,
-- ug_responsavel_* etc.), excluindo o grão de dotação (ne_ccor = '-9',
-- sem NE real). programa_governo/acao_governo deixaram de ser carregados na
-- CTE convenios_ppa: nunca chegavam ao resultado final (o segundo braço do
-- `union` não os lista) e foram removidos junto com a correção de
-- duplicidade por UG.
--
-- Portado de data-application-mir (siconv_dbt/silver/convenios_consolidados.sql).
-- Granularidade: uma linha por convênio da UG 810008 do MIR (nativamente, via
-- convenio.ug_emitente) ou encontrado via NE do SIAFI com
-- ne_info_complementar = nr_convenio.
with
    convenio as (select * from {{ ref("siconv", "convenio") }}),
    ppa_tesouro as (select * from {{ ref("tesouro_gerencial", "ne_tesouro_ppa_mir") }} where ne_ccor <> '-9'),
    -- UGs responsáveis consolidadas em UM registro por convênio. ppa_tesouro
    -- está no grão do empenho: um mesmo convênio pode ter empenhos em várias
    -- UGs. Concatenamos as UGs (string_agg) em vez de deixá-las na chave do
    -- join para não multiplicar a linha do convênio — cada UG a mais repetiria
    -- todos os valores do convênio (vl_global_conv, vl_desembolsado_conv...) e
    -- inflaria as somas nos resumos Gold a jusante.
    ugs_por_convenio as (
        select
            ne_info_complementar as nr_convenio,
            string_agg(
                distinct cast(ug_responsavel_codigo as text), ', ' order by cast(ug_responsavel_codigo as text)
            ) as ug_responsavel_codigo,
            string_agg(distinct ug_responsavel_nome, ', ' order by ug_responsavel_nome) as ug_responsavel_nome,
            count(distinct ug_responsavel_codigo) as qtd_ugs_responsaveis
        from ppa_tesouro
        where left(ne_ccor, 6) = '810008' and ne_info_complementar is not null
        group by ne_info_complementar
    ),
    -- Convênios alcançados pelos empenhos do SIAFI. O `inner join` substitui o
    -- `right join` original: como ugs_por_convenio já está no grão do convênio
    -- e descarta ne_info_complementar nulo, o `right join` só produziria linhas
    -- órfãs que o `where cc.nr_convenio is not null` descartaria em seguida.
    convenios_ppa as (
        select cc.*, u.ug_responsavel_codigo, u.ug_responsavel_nome, u.qtd_ugs_responsaveis
        from convenio cc
        inner join ugs_por_convenio u on cc.nr_convenio = u.nr_convenio
    ),
    convenios_consolidado as (
        select
            *,
            round((vl_desembolsado_conv / nullif(vl_global_conv, 0) * 100)::numeric, 1) as percentual_executado,
            round(
                ((vl_global_conv - vl_desembolsado_conv) / nullif(vl_global_conv, 0) * 100)::numeric, 1
            ) as percentual_faltante,
            cast(null as text) as ug_responsavel_codigo,
            cast(null as text) as ug_responsavel_nome,
            0 as qtd_ugs_responsaveis
        from convenio
        where
            ug_emitente = 810008
            -- O `union distinct` sozinho não desduplica os dois braços: o mesmo
            -- convênio sai aqui com UG nula e no braço de baixo com as UGs
            -- preenchidas, e as duas linhas sobreviveriam. Excluir aqui o que o
            -- braço de baixo já traz garante uma linha por nr_convenio.
            and nr_convenio not in (select nr_convenio from convenios_ppa)
        union distinct
        select
            nr_convenio,
            id_proposta,
            dia,
            mes,
            ano,
            dia_assin_conv,
            sit_convenio,
            subsituacao_conv,
            situacao_publicacao,
            instrumento_ativo,
            ind_opera_obtv,
            nr_processo,
            ug_emitente,
            dia_publ_conv,
            dia_inic_vigenc_conv,
            dia_fim_vigenc_conv,
            dia_fim_vigenc_original_conv,
            dias_prest_contas,
            dia_limite_prest_contas,
            data_suspensiva,
            data_retirada_suspensiva,
            dias_clausula_suspensiva,
            situacao_contratacao,
            ind_assinado,
            motivo_suspensao,
            ind_foto,
            qtde_convenios,
            qtd_ta,
            qtd_prorroga,
            vl_global_conv,
            vl_repasse_conv,
            vl_contrapartida_conv,
            vl_empenhado_conv,
            vl_desembolsado_conv,
            vl_saldo_reman_tesouro,
            vl_saldo_reman_convenente,
            vl_rendimento_aplicacao,
            vl_ingresso_contrapartida,
            vl_saldo_conta,
            valor_global_original_conv,
            round((vl_desembolsado_conv / nullif(vl_global_conv, 0) * 100)::numeric, 1) as percentual_executado,
            round(
                ((vl_global_conv - vl_desembolsado_conv) / nullif(vl_global_conv, 0) * 100)::numeric, 1
            ) as percentual_faltante,
            ug_responsavel_codigo,
            ug_responsavel_nome,
            qtd_ugs_responsaveis
        from convenios_ppa
    )

select *
from convenios_consolidado
