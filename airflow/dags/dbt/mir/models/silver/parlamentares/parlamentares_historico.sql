{{ config(materialized="table") }}

-- Silver do MIR: histórico unificado de filiação partidária de deputados e
-- senadores, com partido canonicalizado e logo do partido.
--
-- Cruza dois sistemas (camara_deputados + senado_federal) — vive no projeto
-- do órgão, não em nenhum pacote de sistema (ADR-0004/0009), pelo mesmo
-- motivo de parlamentares.sql.
--
-- Portado de data-application-mir
-- (dados_abertos_dbt/silver/parlamentares_historico.sql), com uma mudança:
-- o macro name_formater (TRIM + UPPER + TRANSLATE de acentos) não existia
-- neste repositório e não fazia sentido criar um macro novo só para este
-- modelo, então a expressão foi embutida diretamente aqui, com o mesmo
-- comportamento.
with
    bronze_deputados_historico as (select * from {{ ref("camara_deputados", "deputados_historico") }}),

    bronze_deputados as (select * from {{ ref("camara_deputados", "deputados") }}),

    deputados_lookup as (
        select distinct on (id) id, nome, siglauf, urlfoto, email, dt_ingest
        from bronze_deputados
        order by id, dt_ingest desc
    ),

    bronze_senadores_historico as (select * from {{ ref("senado_federal", "senadores_historico") }}),

    bronze_senadores as (select * from {{ ref("senado_federal", "senadores") }}),

    senadores_lookup as (
        select distinct on (id) id, nome_parlamentar, uf, url_foto, email, dt_ingest
        from bronze_senadores
        order by id, dt_ingest desc
    ),

    sigla_map as (
        select trim(upper(sigla_origem)) as sigla_origem, max(trim(upper(sigla_canonica))) as sigla_canonica
        from {{ ref("partidos_map") }}
        group by 1
    ),

    parlamentares_unificados as (
        select
            dh.id as id_parlamentar,
            trim(
                translate(
                    upper(coalesce(nullif(dh.nome, ''), d.nome)),
                    'ÁÀÂÃÄÅÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ',
                    'AAAAAAEEEEIIIIOOOOOUUUUCN'
                )
            ) as chave_join_nome,
            coalesce(nullif(dh.nome, ''), d.nome) as nome_parlamentar,
            'Deputado' as cargo_parlamentar,
            dh.sigla_partido as sigla_partido,
            d.siglauf as uf_parlamentar,
            d.urlfoto as url_foto,
            d.email as email,
            dh.data_filiacao,
            dh.data_desfiliacao,
            dh.id_legislatura,
            dh.situacao,
            null::text as fonte,
            dh.dt_ingest
        from bronze_deputados_historico as dh
        left join deputados_lookup as d on dh.id = d.id

        union all

        select
            sh.parlamentar_id as id_parlamentar,
            trim(
                translate(upper(s.nome_parlamentar), 'ÁÀÂÃÄÅÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ', 'AAAAAAEEEEIIIIOOOOOUUUUCN')
            ) as chave_join_nome,
            s.nome_parlamentar as nome_parlamentar,
            'Senador' as cargo_parlamentar,
            sh.sigla_partido as sigla_partido,
            s.uf as uf_parlamentar,
            s.url_foto as url_foto,
            s.email as email,
            sh.data_filiacao,
            sh.data_desfiliacao as data_desfiliacao,
            null::integer as id_legislatura,
            null::text as situacao,
            sh.fonte,
            sh.dt_ingest
        from bronze_senadores_historico as sh
        left join senadores_lookup as s on sh.parlamentar_id = s.id
    ),

    parlamentares_padronizados as (
        select p.*, coalesce(m.sigla_canonica, p.sigla_partido) as sigla_partido_padronizada
        from parlamentares_unificados as p
        left join sigla_map as m on trim(upper(p.sigla_partido)) = m.sigla_origem
    ),

    partidos_logo as (
        select trim(upper(sigla)) as chave_join_sigla_partido, max(logo_url) as logo_url
        from {{ ref("partidos_logo") }}
        group by 1
    )

select
    p.id_parlamentar,
    p.chave_join_nome,
    p.nome_parlamentar,
    p.cargo_parlamentar,
    p.sigla_partido_padronizada as sigla_partido,
    p.uf_parlamentar,
    p.url_foto,
    p.email,
    p.data_filiacao,
    p.data_desfiliacao,
    p.id_legislatura,
    p.situacao,
    p.fonte,
    p.dt_ingest,
    pl.logo_url as url_logo_partido
from parlamentares_padronizados as p
left join partidos_logo as pl on trim(upper(p.sigla_partido_padronizada)) = pl.chave_join_sigla_partido
