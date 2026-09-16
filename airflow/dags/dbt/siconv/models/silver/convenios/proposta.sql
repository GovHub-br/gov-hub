-- Silver do SICONV: proposta tipada a partir do source (papel que, antes do
-- ADR-0017, era da camada Bronze modelada — a Bronze de propostas nunca
-- filtra por órgão, então este modelo vive no pacote compartilhado, não em
-- dbt/siconv/mir/, ADR-0004).
--
-- Portado de data-application-mir (siconv_dbt/bronze/proposta.sql).
-- Granularidade: uma linha por proposta.
with
    proposta_raw as (
        select
            id_proposta::integer as id_proposta,
            uf_proponente::text as uf_proponente,
            munic_proponente::text as munic_proponente,
            cod_munic_ibge::integer as cod_munic_ibge,
            cod_orgao_sup::integer as cod_orgao_sup,
            desc_orgao_sup::text as desc_orgao_sup,
            natureza_juridica::text as natureza_juridica,
            nr_proposta::text as nr_proposta,
            dia_prop::integer as dia_prop,
            mes_prop::integer as mes_prop,
            ano_prop::integer as ano_prop,
            to_date(nullif(dia_proposta, ''), 'DD/MM/YYYY') as dia_proposta,
            cod_orgao::integer as cod_orgao,
            desc_orgao::text as desc_orgao,
            modalidade::text as modalidade,
            identif_proponente::text as identif_proponente,
            nm_proponente::text as nm_proponente,
            cep_proponente::text as cep_proponente,
            endereco_proponente::text as endereco_proponente,
            bairro_proponente::text as bairro_proponente,
            nm_banco::text as nm_banco,
            situacao_conta::text as situacao_conta,
            situacao_projeto_basico::text as situacao_projeto_basico,
            sit_proposta::text as sit_proposta,
            to_date(nullif(dia_inic_vigencia_proposta, ''), 'DD/MM/YYYY') as dia_inic_vigencia_proposta,
            to_date(nullif(dia_fim_vigencia_proposta, ''), 'DD/MM/YYYY') as dia_fim_vigencia_proposta,
            objeto_proposta::text as objeto_proposta,
            item_investimento::text as item_investimento,
            enviada_mandataria::text as enviada_mandataria,
            nome_subtipo_proposta::text as nome_subtipo_proposta,
            descricao_subtipo_proposta::text as descricao_subtipo_proposta,
            replace(nullif(vl_global_prop, ''), ',', '.')::numeric(15, 2) as vl_global_prop,
            replace(nullif(vl_repasse_prop, ''), ',', '.')::numeric(15, 2) as vl_repasse_prop,
            replace(nullif(vl_contrapartida_prop, ''), ',', '.')::numeric(15, 2) as vl_contrapartida_prop,
            cd_agencia::text as cd_agencia,
            cd_conta::text as cd_conta,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siconv", "proposta") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". Sem isto, a Gold soma a
    -- mesma linha uma vez por execução.
    versionado as (
        select proposta_raw.*, row_number() over (partition by id_proposta order by dt_ingest desc) as nu_versao
        from proposta_raw
    )

select
    id_proposta,
    uf_proponente,
    munic_proponente,
    cod_munic_ibge,
    cod_orgao_sup,
    desc_orgao_sup,
    natureza_juridica,
    nr_proposta,
    dia_prop,
    mes_prop,
    ano_prop,
    dia_proposta,
    cod_orgao,
    desc_orgao,
    modalidade,
    identif_proponente,
    nm_proponente,
    cep_proponente,
    endereco_proponente,
    bairro_proponente,
    nm_banco,
    situacao_conta,
    situacao_projeto_basico,
    sit_proposta,
    dia_inic_vigencia_proposta,
    dia_fim_vigencia_proposta,
    objeto_proposta,
    item_investimento,
    enviada_mandataria,
    nome_subtipo_proposta,
    descricao_subtipo_proposta,
    vl_global_prop,
    vl_repasse_prop,
    vl_contrapartida_prop,
    cd_agencia,
    cd_conta,
    dt_ingest
from versionado
where nu_versao = 1
