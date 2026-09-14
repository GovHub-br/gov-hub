{{ config(materialized="table") }}

-- Silver do MIR: planos de ação de TED tipados a partir da Bronze.
--
-- Sem cruzamento com nenhum outro sistema — só tipagem sobre o próprio
-- source de transferegov_ted. Ainda assim vive em transferegov_ted/mir/, não
-- na raiz do pacote: os dados desta fonte são, na prática, só do MIR (a DAG
-- de `programas` filtra pela sigla da unidade descentralizadora e as
-- demais DAGs iteram só sobre os id_programa/id_plano_acao já ingeridos —
-- ver catalogo/sistemas/transferegov_ted.yml). Mesmo padrão de
-- posicionamento de tesouro_gerencial/mir/empenhos_tesouro_mir.sql.
--
-- Portado de data-application-mir (dags/dbt/mir/models/empenhos_ted_dbt/
-- bronze/planos_acao_ted.sql). Consumido por vários modelos Silver/Gold de
-- transferências em dbt/mir/ (num_transf_n_plano_acao, pf_unificado_planos_
-- acao, ted_resumo_orcamentario) — por isso materializado uma única vez
-- aqui, em vez de repetir a tipagem em cada um deles.
with
    planos_acao_raw as (
        select
            id_plano_acao::integer as id_plano_acao,
            id_programa::integer as id_programa,
            sigla_unidade_descentralizada::text as sigla_unidade_descentralizada,
            unidade_descentralizada::text as unidade_descentralizada,
            sigla_unidade_responsavel_execucao::text as sigla_unidade_responsavel_execucao,
            unidade_responsavel_execucao::text as unidade_responsavel_execucao,
            nullif(vl_total_plano_acao, '')::numeric(15, 2) as vl_total_plano_acao,
            nullif(dt_inicio_vigencia, '')::timestamp::date as dt_inicio_vigencia,
            nullif(dt_fim_vigencia, '')::timestamp::date as dt_fim_vigencia,
            tx_objeto_plano_acao::text as tx_objeto_plano_acao,
            tx_justificativa_plano_acao::text as tx_justificativa_plano_acao,
            nullif(in_forma_execucao_direta, '')::boolean as in_forma_execucao_direta,
            nullif(in_forma_execucao_particulares, '')::boolean as in_forma_execucao_particulares,
            nullif(in_forma_execucao_descentralizada, '')::boolean as in_forma_execucao_descentralizada,
            tx_situacao_plano_acao::text as tx_situacao_plano_acao,
            nullif(aa_ano_plano_acao, '')::integer as aa_ano_plano_acao,
            nullif(vl_beneficiario_especifico, '')::numeric(15, 2) as vl_beneficiario_especifico,
            nullif(vl_chamamento_publico, '')::numeric(15, 2) as vl_chamamento_publico,
            sq_instrumento::text as sq_instrumento,
            nullif(aa_instrumento, '')::integer as aa_instrumento,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("transferegov_ted", "planos_acao") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". A chave abaixo é a mesma
    -- `primary_key` que a DAG de ingestão declara, para que a definição de
    -- linha repetida seja única entre ingestão e transformação.
    versionado as (
        select planos_acao_raw.*, row_number() over (partition by id_plano_acao order by dt_ingest desc) as nu_versao
        from planos_acao_raw
    )

select
    id_plano_acao,
    id_programa,
    sigla_unidade_descentralizada,
    unidade_descentralizada,
    sigla_unidade_responsavel_execucao,
    unidade_responsavel_execucao,
    vl_total_plano_acao,
    dt_inicio_vigencia,
    dt_fim_vigencia,
    tx_objeto_plano_acao,
    tx_justificativa_plano_acao,
    in_forma_execucao_direta,
    in_forma_execucao_particulares,
    in_forma_execucao_descentralizada,
    tx_situacao_plano_acao,
    aa_ano_plano_acao,
    vl_beneficiario_especifico,
    vl_chamamento_publico,
    sq_instrumento,
    aa_instrumento,
    dt_ingest
from versionado
where nu_versao = 1
