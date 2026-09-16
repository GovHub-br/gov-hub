-- Silver de contratos_gov.terceirizados — verdade única do dado (ADR-0006).
--
-- Granularidade: uma linha por terceirizado de um contrato.
--
-- Tipagem portada de data-application-mir (compras_gov_dbt/bronze/terceirizados.sql).
with
    bronze as (select * from {{ source("contratos_gov", "terceirizados") }}),

    tipado as (
        select
            nullif(cast(id as text), '')::integer as id,
            cast(contrato_id as text) as contrato_id,
            substring(usuario, '(.+) - ') as cpf,
            substring(usuario, '- (.+)') as nome,
            funcao_id,
            descricao_complementar,
            nullif(cast(jornada as text), '')::numeric as jornada,
            unidade,
            replace(replace(nullif(cast(salario as text), ''), '.', ''), ',', '.')::numeric(15, 2) as salario,
            replace(replace(nullif(cast(custo as text), ''), '.', ''), ',', '.')::numeric(15, 2) as custo,
            escolaridade_id,
            case
                when data_inicio is not null and cast(data_inicio as text) ~ '^\d{4}-\d{2}-\d{2}$'
                then to_date(cast(data_inicio as text), 'YYYY-MM-DD')
            end as data_inicio,
            case
                when data_fim is not null and cast(data_fim as text) ~ '^\d{4}-\d{2}-\d{2}$'
                then to_date(cast(data_fim as text), 'YYYY-MM-DD')
            end as data_fim,
            situacao,
            replace(replace(nullif(cast(aux_transporte as text), ''), '.', ''), ',', '.')::numeric(
                15, 2
            ) as aux_transporte,
            replace(replace(nullif(cast(vale_alimentacao as text), ''), '.', ''), ',', '.')::numeric(
                15, 2
            ) as vale_alimentacao,
            numero_contrato,
            unidade_gestora,
            unidade_gestora_nome,
            fornecedor_identificador,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from bronze
    ),

    versionado as (
        select tipado.*, row_number() over (partition by id, contrato_id order by dt_ingest desc) as nu_versao
        from tipado
    )

select
    id,
    contrato_id,
    cpf,
    nome,
    funcao_id,
    descricao_complementar,
    jornada,
    unidade,
    salario,
    custo,
    escolaridade_id,
    data_inicio,
    data_fim,
    situacao,
    aux_transporte,
    vale_alimentacao,
    numero_contrato,
    unidade_gestora,
    unidade_gestora_nome,
    fornecedor_identificador,
    dt_ingest
from versionado
where nu_versao = 1
