{{ config(materialized="table") }}

-- Gold do MIR: uma linha por emenda x instrumento de execução (convênio/
-- termo de fomento/TED), com identificação unificada do instrumento,
-- beneficiário/executor e valor firmado.
--
-- Apesar de portado da pasta emendas_dbt/ do repositório antigo, este modelo
-- é 100% SICONV+TED: refs apenas numero_transferencia, convenios_consolidados
-- + siconv.proposta e ted_resumo_orcamentario — nenhum ref para bronze de
-- transferegov_emendas. Por isso fica em dbt/mir/models/gold/convenios/, não
-- em uma pasta de emendas — ver observação de posicionamento na migração de
-- transferegov_emendas.
--
-- Portado de data-application-mir (dags/dbt/mir/models/emendas_dbt/gold/
-- emendas_instrumentos_execucao.sql). numero_transferencia e
-- convenios_consolidados já vivem neste mesmo projeto — refs simples;
-- proposta vem do pacote siconv.
--
-- O lado do convênio lê `convenios_consolidados` + `siconv.proposta`, e NÃO
-- `proposta_convenio`: aquele Silver faz `inner join proposta` e
-- `where p.modalidade in ('CONVENIO', 'TERMO DE FOMENTO')`, então instrumentos
-- de outras modalidades (contrato de repasse, termo de colaboração) deixariam
-- de casar, cairiam no fallback por regex ou viriam com tipo_instrumento nulo.
-- O `coalesce(conv.modalidade, 'CONVENIO')` abaixo só devolve a modalidade
-- real porque a fonte aqui traz todos os convênios, de qualquer modalidade.
--
-- `ted_resumo_orcamentario` também é ref simples: já vive neste mesmo
-- projeto (dbt/mir/models/gold/transferencias/), migrado junto de
-- transferegov_ted. Sem filtro por plano_acao: a regra `plano_acao is not
-- null` é do Silver de empenhos, não deste Gold — aplicá-la aqui descartaria
-- TEDs reais que ainda não tiveram o plano de ação resolvido, e a emenda
-- ficaria sem instrumento identificado.
--
-- O `select distinct` das CTEs conv/ted é a proteção do original contra
-- fan-out: os dois joins abaixo são por número normalizado, e uma chave
-- repetida do lado direito multiplicaria a linha da emenda.
--
-- numero_transferencia (numero_transferencia.sql) é integer; nr_convenio
-- (proposta_convenio, via siconv) e num_transf (ted_resumo_orcamentario) são
-- text, às vezes com zeros à esquerda que o número extraído do texto livre
-- da emenda não tem. Uma versão anterior deste modelo comparava os dois
-- lados sem normalizar ("e.numero_transferencia = conv.nr_convenio"), o que
-- quebrava com "operator does not exist: integer = text" — e mesmo com um
-- cast simples, ainda perderia casamentos por causa dos zeros à esquerda.
-- Restaurada aqui a normalização do original (cast para texto + remoção de
-- zeros à esquerda dos dois lados) e a extração por regex como último
-- recurso, quando a emenda não casa por convênio nem por TED mas o texto
-- livre (ne_info_complementar/ne_ccor_descricao/doc_observacao) menciona o
-- tipo e o número do instrumento.
with
    emendas as (
        select *, ltrim(trim(cast(numero_transferencia as text)), '0') as numero_transferencia_clean
        from {{ ref("numero_transferencia") }}
    ),
    conv as (
        select distinct
            ltrim(trim(cast(cc.nr_convenio as text)), '0') as nr_convenio_clean,
            p.modalidade,
            p.objeto_proposta,
            p.munic_proponente,
            p.uf_proponente,
            p.nm_proponente,
            cc.vl_global_conv
        from {{ ref("convenios_consolidados") }} cc
        left join {{ ref("siconv", "proposta") }} p on cc.id_proposta = p.id_proposta
    ),
    ted as (
        select distinct
            ltrim(trim(cast(num_transf as text)), '0') as num_transf_clean,
            sigla_unidade_descentralizada,
            tx_nome_institucional_programa,
            tx_objetivo_programa,
            programa_governo,
            programa_governo_descricao,
            valor_firmado
        from {{ ref("ted_resumo_orcamentario") }}
    )

select
    e.emissao_mes,
    e.emissao_dia,
    e.codigo_programa,
    e.programa,
    e.codigo_acao_ajustada,
    e.acao_ajustada,
    e.autor_emendas_orcamento_descricao,
    -- UG executora do empenho da emenda: vem de emendas_partidos e é o grão
    -- desta linha, não uma agregação (diferente de ted_resumo_orcamentario,
    -- que consolida as UGs por transferência).
    e.ug_responsavel_codigo,
    e.ug_responsavel_nome,
    e.localizador_gasto,
    e.localizador_gasto_descricao,
    e.regiao_pt,
    e.uf as uf,
    e.uf_descricao,
    e.municipio,
    'Brasil' as pais,
    e.ne_ccor,
    e.ne_num_processo,
    e.ne_info_complementar,
    e.ne_ccor_descricao,
    e.doc_observacao,
    e.codigo_gnd,
    e.gnd,
    e.natureza_despesa,
    e.natureza_despesa_descricao,
    e.codigo_modalidade,
    e.modalidade,
    e.ne_ccor_favorecido,
    e.ne_ccor_favorecido_descricao,
    e.ne_ccor_ano_emissao,
    e.ptres,
    e.fonte_recursos_detalhada,
    e.fonte_recursos_detalhada_descricao,
    e.dotacao_inicial,
    e.dotacao_atualizada,
    e.despesas_empenhadas,
    e.despesas_liquidadas,
    e.despesas_pagas,
    e.restos_a_pagar_inscritos,
    e.restos_a_pagar_pagos,
    e.autor_emendas_orcamento_nome,
    e.autor_emendas_orcamento,
    -- Identificação do parlamentar autor. O Gold antigo fazia `select e.*` e
    -- expunha estas colunas; a migração enumerou as colunas e as perdeu, o que
    -- quebra qualquer painel que agrupe instrumento por autor ou por partido.
    -- Enumeradas (e não `e.*`) por causa da regra do AGENTS.md seção 5.
    e.id_autor,
    e.cargo_autor,
    e.autor,
    e.partido,
    e.uf_autor,
    e.url_foto_autor,
    e.email_autor,
    e.url_foto_partido,
    -- Número do instrumento extraído do texto livre da emenda, antes da
    -- normalização — é a chave dos dois joins abaixo e o original a expunha.
    e.numero_transferencia,
    e.dt_ingest,

    -- Instrumento: identificação unificada (convênio > TED > extraído do texto)
    coalesce(conv.nr_convenio_clean, ted.num_transf_clean, et.numero_extraido) as numero_instrumento,
    case
        when conv.nr_convenio_clean is not null
        then coalesce(conv.modalidade, 'CONVENIO')
        when ted.num_transf_clean is not null
        then 'TED'
        when et.tipo_extraido ilike 'TERMO%'
        then 'TERMO DE FOMENTO'
        when et.tipo_extraido ilike 'CONV%'
        then 'CONVENIO'
        when et.tipo_extraido ilike 'TED'
        then 'TED'
        else null
    end as tipo_instrumento,
    (
        conv.nr_convenio_clean is null and ted.num_transf_clean is null and et.tipo_extraido is not null
    ) as instrumento_identificado_por_texto,
    coalesce(conv.objeto_proposta, ted.tx_objetivo_programa) as objeto_instrumento,

    -- Instrumento: localização/executor
    coalesce(
        concat(conv.munic_proponente, ' - ', conv.uf_proponente, ' : ', conv.nm_proponente),
        ted.sigla_unidade_descentralizada
    ) as beneficiario,

    -- Instrumento: programa (TED)
    ted.tx_nome_institucional_programa as nome_programa_ted,
    ted.programa_governo,
    ted.programa_governo_descricao,

    -- Valores: firmado
    coalesce(conv.vl_global_conv, ted.valor_firmado) as valor_firmado

from emendas e
left join conv on e.numero_transferencia_clean = conv.nr_convenio_clean
left join ted on e.numero_transferencia_clean = ted.num_transf_clean
left join
    lateral(
        select
            (
                regexp_match(
                    coalesce(e.ne_info_complementar, '')
                    || ' '
                    || coalesce(e.ne_ccor_descricao, '')
                    || ' '
                    || coalesce(e.doc_observacao, ''),
                    '(?i)(TERMO\s+DE\s+FOMENTO|CONVENIO|CONVÊNIO|TED)\s*(?:Nº|N°|N|º|°)?\s*(\d{4,7})'
                )
            )[1] as tipo_extraido,
            ltrim(
                (
                    regexp_match(
                        coalesce(e.ne_info_complementar, '')
                        || ' '
                        || coalesce(e.ne_ccor_descricao, '')
                        || ' '
                        || coalesce(e.doc_observacao, ''),
                        '(?i)(TERMO\s+DE\s+FOMENTO|CONVENIO|CONVÊNIO|TED)\s*(?:Nº|N°|N|º|°)?\s*(\d{4,7})'
                    )
                )[2],
                '0'
            ) as numero_extraido
    ) et
    on true
