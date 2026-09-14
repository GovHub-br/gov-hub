{{ config(materialized="table") }}

-- Silver de camara_deputados.deputados — verdade única do dado (ADR-0006).
--
-- Granularidade: um registro por deputado, sigla de partido e legislatura.
--
-- Tipagem portada de data-application-mir
-- (dados_abertos_dbt/bronze/deputados.sql). No repositório antigo essa
-- tipagem era um passo "bronze" à parte; aqui a Bronze é só o source
-- (ADR-0017), então a tipagem entra direto na Silver.
with
    bronze as (select * from {{ source("camara_deputados", "deputados") }}),

    tipado as (
        select
            id::integer as id,
            nome::text as nome,
            siglapartido::text as siglapartido,
            siglauf::text as siglauf,
            idlegislatura::integer as idlegislatura,
            urlfoto::text as urlfoto,
            email::text as email,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from bronze
    ),

    -- A zona raw é append-only (ADR-0012/ADR-0021): a DAG roda @daily e cada
    -- execução acrescenta uma cópia do cadastro, então manter só a versão mais
    -- recente de cada registro é responsabilidade desta camada — ver
    -- airflow/helpers/landing_zone.py, "a deduplicação é responsabilidade da
    -- Silver". A chave é a mesma `primary_key` da DAG de ingestão
    -- (id, siglaPartido, idLegislatura), aqui já em minúsculas.
    versionado as (
        select
            tipado.*,
            row_number() over (partition by id, siglapartido, idlegislatura order by dt_ingest desc) as nu_versao
        from tipado
    )

select id, nome, siglapartido, siglauf, idlegislatura, urlfoto, email, dt_ingest
from versionado
where nu_versao = 1
