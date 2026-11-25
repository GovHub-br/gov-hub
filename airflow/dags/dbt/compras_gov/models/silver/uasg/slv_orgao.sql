-- Schema derivado da pasta (002_slv_uasg, ADR-0010); database, materialização e a
-- tag `duckdb` vêm de dbt_project.yml. A tag leva este nó para a
-- duckdb_<orgao>_transform_dag, no target prod_duckdb, porque a Bronze lê Parquet.
-- Silver tratada: um registro por órgão. A Bronze acumula uma linha por ingestão,
-- então mantém-se a mais recente de cada código (dt_ingest). As colunas da Bronze
-- seguem com os mesmos tipos, só renomeadas para snake_case, mais a chave
-- conformada co_orgao (ADR-0017), que é por onde os outros sistemas cruzam.
with
    bronze as (select * from {{ ref("orgao") }}),

    conformado as (
        select
            {{ gov_bricks.chave_conformada("co_orgao", '"codigoOrgao"') }} as co_orgao,
            "codigoOrgao" as codigo_orgao,
            "nomeOrgao" as nome_orgao,
            "nomeMnemonicoOrgao" as nome_mnemonico_orgao,
            "cnpjCpfOrgao" as cnpj_cpf_orgao,
            "codigoOrgaoVinculado" as codigo_orgao_vinculado,
            "cnpjCpfOrgaoVinculado" as cnpj_cpf_orgao_vinculado,
            "nomeOrgaoVinculado" as nome_orgao_vinculado,
            "codigoOrgaoSuperior" as codigo_orgao_superior,
            "cnpjCpfOrgaoSuperior" as cnpj_cpf_orgao_superior,
            "nomeOrgaoSuperior" as nome_orgao_superior,
            "codigoTipoAdministracao" as codigo_tipo_administracao,
            "nomeTipoAdministracao" as nome_tipo_administracao,
            "poder" as poder,
            "esfera" as esfera,
            "usoSisg" as uso_sisg,
            "statusOrgao" as status_orgao,
            "dataHoraMovimento" as data_hora_movimento,
            dt_ingest
        from bronze
    ),

    versionado as (
        select conformado.*, row_number() over (partition by co_orgao order by dt_ingest desc) as nu_versao
        from conformado
        -- Filtra a chave já normalizada, não a coluna crua: um código sem dígitos
        -- vira co_orgao nulo e quebraria o not_null.
        where co_orgao is not null
    )

select
    co_orgao,
    codigo_orgao,
    nome_orgao,
    nome_mnemonico_orgao,
    cnpj_cpf_orgao,
    codigo_orgao_vinculado,
    cnpj_cpf_orgao_vinculado,
    nome_orgao_vinculado,
    codigo_orgao_superior,
    cnpj_cpf_orgao_superior,
    nome_orgao_superior,
    codigo_tipo_administracao,
    nome_tipo_administracao,
    poder,
    esfera,
    uso_sisg,
    status_orgao,
    data_hora_movimento,
    dt_ingest
from versionado
where nu_versao = 1
