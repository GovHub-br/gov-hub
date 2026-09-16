{{ config(materialized="table") }}

-- Silver de camara_deputados.deputados_historico — verdade única do dado
-- (ADR-0006).
--
-- Granularidade: uma linha por evento histórico de um deputado, com a
-- data_desfiliacao calculada por lead() sobre a sequência de eventos.
--
-- Portado de data-application-mir
-- (dados_abertos_dbt/bronze/deputados_historico.sql), com uma simplificação
-- deliberada: o original usava dados_abertos_dbt.legislaturas (a tabela de
-- legislaturas do Senado) para inferir a data_desfiliacao do último evento de
-- um deputado quando a legislatura dele já havia terminado. Isso criaria uma
-- dependência do pacote camara_deputados sobre o pacote senado_federal — o
-- tipo de acoplamento entre sistemas que o ADR-0004 resolve movendo o
-- cruzamento para o projeto do órgão (dbt/mir/), não para dentro de um
-- pacote de sistema. Como esse cálculo é só uma inferência de borda (a
-- legislatura de um deputado sem próximo evento e sem status de encerramento
-- explícito), aqui ele fica em aberto (null) em vez de inferido — a
-- Câmara não tem esse dado; o Senado, sim, mas por outro sistema.
with
    bronze as (select * from {{ source("camara_deputados", "deputados_historico") }}),

    tipado as (
        select
            id::integer as id,
            nome::text as nome,
            siglapartido::text as sigla_partido,
            uripartido::text as uri_partido,
            siglauf::text as sigla_uf,
            idlegislatura::integer as id_legislatura,
            datahora::timestamptz as data_evento,
            trim(situacao)::text as situacao,
            condicaoeleitoral::text as condicao_eleitoral,
            parlamentar_id::integer as parlamentar_id,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from bronze
        where situacao is not null and situacao != ''
    ),

    -- A zona raw é append-only (ADR-0012/ADR-0021) e a DAG reprocessa o
    -- histórico completo de um deputado a cada ciclo de elegibilidade, então o
    -- mesmo evento volta idêntico a cada reprocessamento. Deduplicar é
    -- responsabilidade desta camada (ver airflow/helpers/landing_zone.py).
    --
    -- A dedup vem antes do lead(): com evento repetido, a janela apontaria
    -- para a própria cópia e data_desfiliacao sairia igual a data_filiacao.
    versionado as (
        select
            tipado.*,
            row_number() over (
                partition by id, data_evento, situacao, sigla_partido, id_legislatura order by dt_ingest desc
            ) as nu_versao
        from tipado
    ),

    calculo_periodos as (
        select
            versionado.*,
            lead(versionado.data_evento) over (
                partition by versionado.id order by versionado.data_evento asc
            ) as proximo_evento_data
        from versionado
        where nu_versao = 1
    )

select
    id,
    nome,
    sigla_partido,
    id_legislatura,
    situacao,
    data_evento as data_filiacao,
    case
        -- Caso 1: existe um próximo evento — segue a cronologia normal.
        when proximo_evento_data is not null
        then proximo_evento_data
        -- Caso 2: último evento, com situação de encerramento explícito.
        when situacao in ('Vacância', 'Fim de Mandato', 'Falecimento')
        then data_evento
        -- Caso 3: último evento, situação em aberto — sem data de
        -- desfiliação conhecida (ver nota no cabeçalho deste modelo).
        else null
    end as data_desfiliacao,
    dt_ingest
from calculo_periodos
