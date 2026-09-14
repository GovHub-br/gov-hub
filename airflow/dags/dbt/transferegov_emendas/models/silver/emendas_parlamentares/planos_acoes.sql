{{ config(materialized="table") }}

-- Silver de transferegov_emendas.planos_acao_especiais — verdade única do
-- dado (ADR-0006). Sem cruzamento com nenhum outro sistema, então fica no
-- pacote (ADR-0004/0009), não no projeto do órgão.
--
-- Granularidade: uma linha por plano de ação.
--
-- Portado de data-application-mir (dags/dbt/mir/models/emendas_dbt/bronze/
-- planos_acoes.sql) — a camada Bronze do repositório antigo (tipagem sobre a
-- fonte, sem regra de negócio) virou Silver aqui, já que este framework não
-- materializa Bronze em dbt (ADR-0017): a tipagem que antes vivia em Bronze é
-- feita na primeira camada que dbt materializa.
with
    planos_raw as (
        select
            id_plano_acao::integer as id_plano_acao,
            codigo_plano_acao::text as codigo_plano_acao,
            ano_plano_acao::integer as ano_plano_acao,
            modalidade_plano_acao::text as modalidade_plano_acao,
            situacao_plano_acao::text as situacao_plano_acao,
            cnpj_beneficiario_plano_acao::text as cnpj_beneficiario_plano_acao,
            nome_beneficiario_plano_acao::text as nome_beneficiario_plano_acao,
            uf_beneficiario_plano_acao::text as uf_beneficiario_plano_acao,
            codigo_banco_plano_acao::text as codigo_banco_plano_acao,
            nullif(codigo_situacao_dado_bancario_plano_acao::numeric, 'NaN'::numeric)::integer
            as codigo_situacao_dado_bancario_plano_acao,
            nome_banco_plano_acao::text as nome_banco_plano_acao,
            nullif(numero_agencia_plano_acao::numeric, 'NaN'::numeric)::integer as numero_agencia_plano_acao,
            dv_agencia_plano_acao::text as dv_agencia_plano_acao,
            nullif(numero_conta_plano_acao::numeric, 'NaN'::numeric)::integer as numero_conta_plano_acao,
            dv_conta_plano_acao::text as dv_conta_plano_acao,
            nome_parlamentar_emenda_plano_acao::text as nome_parlamentar_emenda_plano_acao,
            ano_emenda_parlamentar_plano_acao::text as ano_emenda_parlamentar_plano_acao,
            codigo_parlamentar_emenda_plano_acao::text as codigo_parlamentar_emenda_plano_acao,
            sequencial_emenda_parlamentar_plano_acao::integer as sequencial_emenda_parlamentar_plano_acao,
            numero_emenda_parlamentar_plano_acao::text as numero_emenda_parlamentar_plano_acao,
            codigo_emenda_parlamentar_formatado_plano_acao::text as codigo_emenda_parlamentar_formatado_plano_acao,
            codigo_descricao_areas_politicas_publicas_plano_acao::text
            as codigo_descricao_areas_politicas_publicas_plano_acao,
            descricao_programacao_orcamentaria_plano_acao::text as descricao_programacao_orcamentaria_plano_acao,
            motivo_impedimento_plano_acao::text as motivo_impedimento_plano_acao,
            valor_custeio_plano_acao::numeric(15, 2) as valor_custeio_plano_acao,
            valor_investimento_plano_acao::numeric(15, 2) as valor_investimento_plano_acao,
            id_programa::integer as id_programa,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("transferegov_emendas", "planos_acao_especiais") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". A chave abaixo é a mesma
    -- `primary_key` que a DAG de ingestão declara, para que a definição de
    -- linha repetida seja única entre ingestão e transformação.
    versionado as (
        select planos_raw.*, row_number() over (partition by id_plano_acao order by dt_ingest desc) as nu_versao
        from planos_raw
    )

select
    id_plano_acao,
    codigo_plano_acao,
    ano_plano_acao,
    modalidade_plano_acao,
    situacao_plano_acao,
    cnpj_beneficiario_plano_acao,
    nome_beneficiario_plano_acao,
    uf_beneficiario_plano_acao,
    codigo_banco_plano_acao,
    codigo_situacao_dado_bancario_plano_acao,
    nome_banco_plano_acao,
    numero_agencia_plano_acao,
    dv_agencia_plano_acao,
    numero_conta_plano_acao,
    dv_conta_plano_acao,
    nome_parlamentar_emenda_plano_acao,
    ano_emenda_parlamentar_plano_acao,
    codigo_parlamentar_emenda_plano_acao,
    sequencial_emenda_parlamentar_plano_acao,
    numero_emenda_parlamentar_plano_acao,
    codigo_emenda_parlamentar_formatado_plano_acao,
    codigo_descricao_areas_politicas_publicas_plano_acao,
    descricao_programacao_orcamentaria_plano_acao,
    motivo_impedimento_plano_acao,
    valor_custeio_plano_acao,
    valor_investimento_plano_acao,
    id_programa,
    dt_ingest
from versionado
where nu_versao = 1
