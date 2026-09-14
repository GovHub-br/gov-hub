{{ config(materialized="table") }}

-- Silver do MIR: programas de TED tipados a partir da Bronze.
--
-- Sem cruzamento com nenhum outro sistema — mesmo racional de posicionamento
-- de planos_acao_ted.sql (ver cabeçalho daquele arquivo): dados 100% MIR na
-- prática (filtro real de sigla na DAG de ingestão), mas vive dentro do
-- pacote compartilhado transferegov_ted, na subpasta mir/.
--
-- Portado de data-application-mir (dags/dbt/mir/models/empenhos_ted_dbt/
-- bronze/programas_ted.sql). Consumido por ted_resumo_orcamentario.sql, em
-- dbt/mir/.
with
    programas_raw as (
        select
            id_programa::integer as id_programa,
            tx_codigo_programa::text as tx_codigo_programa,
            nullif(aa_ano_programa, '')::integer as aa_ano_programa,
            tx_situacao_programa::text as tx_situacao_programa,
            tx_nome_programa::text as tx_nome_programa,
            sigla_unidade_descentralizadora::text as sigla_unidade_descentralizadora,
            unidade_descentralizadora::text as unidade_descentralizadora,
            sigla_unidade_responsavel_acompanhamento::text as sigla_unidade_responsavel_acompanhamento,
            unidade_responsavel_acompanhamento::text as unidade_responsavel_acompanhamento,
            tx_nome_institucional_programa::text as tx_nome_institucional_programa,
            tx_objetivo_programa::text as tx_objetivo_programa,
            tx_descricao_programa::text as tx_descricao_programa,
            nullif(in_grupo_investimento_obra, '')::boolean as in_grupo_investimento_obra,
            nullif(in_grupo_investimento_servico, '')::boolean as in_grupo_investimento_servico,
            nullif(in_grupo_investimento_equipamento, '')::boolean as in_grupo_investimento_equipamento,
            in_autoriza_subdescentralizacao_outro::text as in_autoriza_subdescentralizacao_outro,
            in_autoriza_realizacao_despesas::text as in_autoriza_realizacao_despesas,
            in_autoriza_execucao_creditos_descentralizada::text as in_autoriza_execucao_creditos_descentralizada,
            nullif(in_beneficiario_especifico, '')::boolean as in_beneficiario_especifico,
            nullif(dt_recebimento_plano_beneficiario_inicio, '')::timestamp::date
            as dt_recebimento_plano_beneficiario_inicio,
            nullif(dt_recebimento_plano_beneficiario_fim, '')::timestamp::date as dt_recebimento_plano_beneficiario_fim,
            nullif(in_chamamento_publico, '')::boolean as in_chamamento_publico,
            nullif(dt_recebimento_plano_chamamento_inicio, '')::timestamp::date
            as dt_recebimento_plano_chamamento_inicio,
            nullif(dt_recebimento_plano_chamamento_fim, '')::timestamp::date as dt_recebimento_plano_chamamento_fim,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("transferegov_ted", "programas") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". A chave abaixo é a mesma
    -- `primary_key` que a DAG de ingestão declara, para que a definição de
    -- linha repetida seja única entre ingestão e transformação.
    versionado as (
        select programas_raw.*, row_number() over (partition by id_programa order by dt_ingest desc) as nu_versao
        from programas_raw
    )

select
    id_programa,
    tx_codigo_programa,
    aa_ano_programa,
    tx_situacao_programa,
    tx_nome_programa,
    sigla_unidade_descentralizadora,
    unidade_descentralizadora,
    sigla_unidade_responsavel_acompanhamento,
    unidade_responsavel_acompanhamento,
    tx_nome_institucional_programa,
    tx_objetivo_programa,
    tx_descricao_programa,
    in_grupo_investimento_obra,
    in_grupo_investimento_servico,
    in_grupo_investimento_equipamento,
    in_autoriza_subdescentralizacao_outro,
    in_autoriza_realizacao_despesas,
    in_autoriza_execucao_creditos_descentralizada,
    in_beneficiario_especifico,
    dt_recebimento_plano_beneficiario_inicio,
    dt_recebimento_plano_beneficiario_fim,
    in_chamamento_publico,
    dt_recebimento_plano_chamamento_inicio,
    dt_recebimento_plano_chamamento_fim,
    dt_ingest
from versionado
where nu_versao = 1
