-- Schema derivado da pasta (002_slv_organizacional, ADR-0010); database, materialização e a
-- tag `duckdb` vêm de dbt_project.yml. A tag leva este nó para a
-- duckdb_<orgao>_transform_dag, no target prod_duckdb, porque a Bronze lê Parquet.
-- Silver tratada: um registro por órgão. A Bronze acumula uma linha por ingestão,
-- então mantém-se a mais recente de cada código (dt_ingest).
with
    bronze as (select * from {{ ref("orgao") }}),

    conformado as (
        select
            {{ gov_bricks.chave_conformada("co_orgao", '"codigoOrgao"') }} as co_orgao,
            "codigoOrgao" as codigo_orgao,
            "nomeOrgao" as nome_orgao,
            dt_ingest
        from bronze
        where "codigoOrgao" is not null
    ),

    versionado as (
        select conformado.*, row_number() over (partition by co_orgao order by dt_ingest desc) as nu_versao
        from conformado
    )

select co_orgao, codigo_orgao, nome_orgao, dt_ingest
from versionado
where nu_versao = 1
