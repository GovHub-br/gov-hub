{{ config(materialized="table") }}

-- Silver de tesouro_gerencial: unifica notas de crédito pré-2026 e pós-2026
-- num único layout, casando semanticamente colunas equivalentes entre os
-- dois períodos (evento/tipo_nc, UG responsável/emitente, natureza/GND,
-- plano interno, favorecido) e preenchendo com nulo o que só existe em um
-- dos dois.
--
-- Sem cruzamento com nenhum outro sistema — só une duas entidades do próprio
-- tesouro_gerencial — por isso vive na raiz do pacote (ADR-0004/0009), não em
-- dbt/mir/. Consumido por dois modelos de dbt/mir/models/silver/
-- transferencias/ (nc_unificado.sql e num_transf_n_plano_acao.sql), que só
-- precisam de `nc`/`nc_transferencia`/`ptres` — materializado uma única vez
-- aqui para não duplicar esta lógica de união nos dois.
--
-- Portado de data-application-mir (dags/dbt/mir/models/empenhos_ted_dbt/
-- bronze/nc_tesouro_mir.sql). Corrige o nome do source pós-2026
-- (`nc_tesouro_pos__2026`, com underscore duplicado, no original) para o
-- nome real da entidade já migrada: `nc_tesouro_pos_2026`.
with
    notas_credito_pre as (
        select
            programa_governo,
            programa_governo_descricao,
            acao_governo,
            acao_governo_descricao,

            nc,
            nc_transferencia,
            nc_fonte_recursos,
            nc_fonte_recursos_descricao,
            ptres,
            nc_evento_descricao,
            nc_ug_responsavel,
            nc_ug_responsavel_descricao,
            nc_natureza_despesa,
            nc_natureza_despesa_descricao,
            nc_plano_interno,
            nc_plano_interno_descricao1,
            favorecido_doc,
            favorecido_doc_descricao,

            favorecido_municipio,
            favorecido_municipio_descricao,

            {{ gov_bricks.parse_financial_value("nc_valor_linha") }} as valor_celula,
            {{ gov_bricks.parse_financial_value("movimento_liquido_moeda_origem") }} as movimento_liquido_moeda_origem,

            (dt_ingest || '-03:00')::timestamptz as dt_ingest,

            cast(null as varchar) as descricao,
            nc_plano_interno_descricao2,
            nc_evento,
            cast(null as varchar) as nc_item_detalhamento,
            cast(null as date) as emissao_dia,
            cast(null as varchar) as emissao_mes,
            cast(null as varchar) as emissao_ano,
            cast(null as varchar) as ro,
            cast(null as varchar) as dc,
            cast(null as numeric) as total_lista,
            cast(null as varchar) as esfera_orcamentaria_codigo,
            cast(null as varchar) as esfera_orcamentaria_nome
        -- A zona raw é append-only (ADR-0012/ADR-0021) e a deduplicação é
        -- responsabilidade da Silver (ver airflow/helpers/landing_zone.py).
        -- Aqui ela acontece na subconsulta, sobre os nomes crus da fonte:
        -- a projeção unificada abaixo renomeia parte das colunas da chave
        -- (ex.: `nc_valor_linha` vira `valor_celula`) e omite outras, então
        -- deduplicar depois do union não teria a chave completa disponível.
        from
            (
                select
                    *,
                    row_number() over (
                        partition by
                            nc,
                            nc_transferencia,
                            nc_fonte_recursos,
                            ptres,
                            nc_evento,
                            nc_ug_responsavel,
                            nc_natureza_despesa,
                            nc_plano_interno,
                            favorecido_doc,
                            favorecido_municipio,
                            nc_valor_linha,
                            movimento_liquido_moeda_origem
                        order by (dt_ingest || '-03:00')::timestamptz desc
                    ) as nu_versao
                from {{ source("tesouro_gerencial", "nc_tesouro_pre_2026") }}
            ) as pre
        where nu_versao = 1
    ),

    notas_credito_pos as (
        select
            -- campos nulos:
            cast(null as varchar) as programa_governo,
            cast(null as varchar) as programa_governo_descricao,
            cast(null as varchar) as acao_governo,
            cast(null as varchar) as acao_governo_descricao,

            nc,
            nc_transferencia,
            fonte_codigo as nc_fonte_recursos,
            fonte_nome as nc_fonte_recursos_descricao,
            ptres,
            tipo_nc as nc_evento_descricao,
            emitente_codigo as nc_ug_responsavel,
            emitente_nome as nc_ug_responsavel_descricao,
            gnd_codigo as nc_natureza_despesa,
            gnd_nome as nc_natureza_despesa_descricao,
            pi_codigo as nc_plano_interno,
            pi_nome as nc_plano_interno_descricao1,
            favorecido_codigo as favorecido_doc,
            favorecido_nome as favorecido_doc_descricao,

            cast(null as varchar) as favorecido_municipio,
            cast(null as varchar) as favorecido_municipio_descricao,

            {{ gov_bricks.parse_financial_value("valor_celula") }} as valor_celula,
            {{ gov_bricks.parse_financial_value("total_lista") }} as movimento_liquido_moeda_origem,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest,

            descricao,
            cast(null as varchar) as nc_plano_interno_descricao2,
            cast(null as varchar) as nc_evento,
            nc_item_detalhamento,
            to_date(nullif(emissao_dia, ''), 'DD/MM/YYYY') as emissao_dia,
            emissao_mes,
            emissao_ano,
            ro,
            dc,
            {{ gov_bricks.parse_financial_value("total_lista") }} as total_lista,
            esfera_orcamentaria_codigo,
            esfera_orcamentaria_nome
        -- Mesmo racional da CTE pré-2026: a dedup vai na subconsulta porque
        -- `ugr_codigo` faz parte da chave da ingestão e não é projetado no
        -- layout unificado.
        from
            (
                select
                    *,
                    row_number() over (
                        partition by nc, emissao_dia, emissao_mes, emissao_ano, ptres, ugr_codigo, valor_celula, dc
                        order by (dt_ingest || '-03:00')::timestamptz desc
                    ) as nu_versao
                from {{ source("tesouro_gerencial", "nc_tesouro_pos_2026") }}
            ) as pos
        where nu_versao = 1
    )

select *
from notas_credito_pre
union all
select *
from notas_credito_pos
