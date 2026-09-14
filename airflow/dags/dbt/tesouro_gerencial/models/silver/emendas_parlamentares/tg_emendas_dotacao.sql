{{ config(materialized="table") }}

-- Silver de tesouro_gerencial.ne_tesouro_emendas — grão de DOTAÇÃO
-- orçamentária (programa/ação/localizador/natureza/modalidade/fonte/ptres,
-- sem empenho associado; ne_ccor = '-9' na tabela raw). Complementa
-- tg_emendas (grão de empenho). Sem cruzamento com nenhum outro sistema,
-- então fica no pacote (ADR-0004/0009), não no projeto do órgão.
--
-- Portado de data-application-mir (dags/dbt/mir/models/emendas_dbt/bronze/
-- tg_emendas_dotacao.sql) — ver tg_emendas.sql para o racional da conversão
-- de emissao_mes/emissao_dia.
with
    tg_emendas_dotacao_raw as (
        select
            case
                when emissao_mes ~ '^[A-Z]{3}/[0-9]{4}$' then {{ gov_bricks.parse_date("emissao_mes") }}
            end as emissao_mes,
            case
                when emissao_dia ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$' then to_date(emissao_dia, 'DD/MM/YYYY')
            end as emissao_dia,
            programa_governo::integer as programa_governo,
            programa_governo_descricao::text as programa_governo_descricao,
            acao_governo::text as acao_governo,
            acao_governo_descricao::text as acao_governo_descricao,
            autor_emendas_orcamento::text as autor_emendas_orcamento,
            autor_emendas_orcamento_descricao::text as autor_emendas_orcamento_descricao,
            initcap(
                trim(regexp_replace(split_part(autor_emendas_orcamento_descricao, '/', 1), '\s+', ' ', 'g'))
            ) as autor_emendas_orcamento_nome,
            localizador_gasto::text as localizador_gasto,
            localizador_gasto_descricao::text as localizador_gasto_descricao,
            regiao_pt::text as regiao_pt,
            case when uf_pt = '-8' then regiao_pt else uf_pt end as uf_pt,
            case when uf_pt_descricao = 'SEM INFORMACAO' then regiao_pt else uf_pt_descricao end::text
            as uf_pt_descricao,
            municipio_pt::text as municipio_pt,
            doc_observacao::text as doc_observacao,
            grupo_despesa::integer as grupo_despesa,
            grupo_despesa_descricao::text as grupo_despesa_descricao,
            natureza_despesa::text as natureza_despesa,
            natureza_despesa_descricao::text as natureza_despesa_descricao,
            modalidade_aplicacao::integer as modalidade_aplicacao,
            modalidade_aplicacao_descricao::text as modalidade_aplicacao_descricao,
            ptres::integer as ptres,
            fonte_recursos_detalhada::text as fonte_recursos_detalhada,
            fonte_recursos_detalhada_descricao::text as fonte_recursos_detalhada_descricao,
            {{ gov_bricks.parse_financial_value("dotacao_inicial") }} as dotacao_inicial,
            {{ gov_bricks.parse_financial_value("dotacao_atualizada") }} as dotacao_atualizada,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("tesouro_gerencial", "ne_tesouro_emendas") }}
        where ne_ccor = '-9'
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia do relatório, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". A chave é a mesma
    -- `UNIQUE_KEY` que a DAG de ingestão declara.
    -- `ne_ccor` sai da chave porque este modelo isola o grão de dotação
    -- (`ne_ccor = '-9'`), onde a coluna é constante e não é projetada.
    versionado as (
        select
            tg_emendas_dotacao_raw.*,
            row_number() over (
                partition by
                    emissao_mes,
                    emissao_dia,
                    doc_observacao,
                    ptres,
                    natureza_despesa,
                    modalidade_aplicacao,
                    localizador_gasto,
                    fonte_recursos_detalhada
                order by dt_ingest desc
            ) as nu_versao
        from tg_emendas_dotacao_raw
    )

select
    emissao_mes,
    emissao_dia,
    programa_governo,
    programa_governo_descricao,
    acao_governo,
    acao_governo_descricao,
    autor_emendas_orcamento,
    autor_emendas_orcamento_descricao,
    autor_emendas_orcamento_nome,
    localizador_gasto,
    localizador_gasto_descricao,
    regiao_pt,
    uf_pt,
    uf_pt_descricao,
    municipio_pt,
    doc_observacao,
    grupo_despesa,
    grupo_despesa_descricao,
    natureza_despesa,
    natureza_despesa_descricao,
    modalidade_aplicacao,
    modalidade_aplicacao_descricao,
    ptres,
    fonte_recursos_detalhada,
    fonte_recursos_detalhada_descricao,
    dotacao_inicial,
    dotacao_atualizada,
    dt_ingest
from versionado
where nu_versao = 1
