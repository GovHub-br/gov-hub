{{ config(materialized="table") }}

-- Gold do MIR: execução (empenhado/liquidado/pago) das emendas parlamentares
-- detalhada por Unidade Gestora executora. Complementa
-- resumo_emendas_orcamento_execucao (que é por parlamentar): aqui a mesma
-- execução aparece quebrada por UG, para responder "quanto cada UG executou
-- das emendas do autor".
--
-- NÃO traz dotação de propósito: a dotação é definida no grão da classificação
-- orçamentária (sem UG) e, se repetida por UG, somaria em dobro — para
-- orçamento (dotado x executado) use resumo_emendas_orcamento_execucao.
--
-- Grão: autor_emendas_orcamento_nome x UG executora. Linhas com UG nula são a
-- execução ainda não atribuída a uma UG (empenho sem ne_ccor correspondente em
-- ne_tesouro_ppa_mir — ver a CTE ug_por_ne_ccor de emendas_partidos).
--
-- Portado de data-application-mir (dags/dbt/mir/models/emendas_dbt/gold/
-- emendas_execucao_por_ug.sql). O ref emendas_partidos já está neste mesmo
-- projeto — ref simples.
with base as (select * from {{ ref("emendas_partidos") }})

select

    autor_emendas_orcamento_nome,
    ug_responsavel_codigo,
    ug_responsavel_nome,
    max(id_autor) as id_autor,
    max(autor) as autor,
    max(cargo_autor) as cargo_autor,
    max(partido) as partido,
    max(uf_autor) as uf_autor,
    max(url_foto_autor) as url_foto_autor,
    max(url_foto_partido) as url_foto_partido,

    count(*) as quantidade_empenhos,
    count(distinct localizador_gasto) as quantidade_localizadores,

    -- Execução (por UG)
    sum(despesas_empenhadas) as despesas_empenhadas,
    sum(despesas_liquidadas) as despesas_liquidadas,
    sum(despesas_pagas) as despesas_pagas,
    sum(restos_a_pagar_inscritos) as restos_a_pagar_inscritos,
    sum(restos_a_pagar_pagos) as restos_a_pagar_pagos,

    max(dt_ingest) as dt_ingest

from base
group by autor_emendas_orcamento_nome, ug_responsavel_codigo, ug_responsavel_nome
