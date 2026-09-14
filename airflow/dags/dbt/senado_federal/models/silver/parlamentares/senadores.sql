{{ config(materialized="table") }}

-- Silver de senado_federal.senadores — verdade única do dado (ADR-0006).
--
-- Granularidade: um registro por senador.
--
-- Tipagem portada de data-application-mir
-- (dados_abertos_dbt/bronze/senadores.sql). No repositório antigo essa
-- tipagem era um passo "bronze" à parte; aqui a Bronze é só o source
-- (ADR-0017), então a tipagem entra direto na Silver.
with
    bronze as (select * from {{ source("senado_federal", "senadores") }}),

    tipado as (
        select
            id::integer as id,
            nome_parlamentar::text as nome_parlamentar,
            sexo::text as sexo,
            forma_tratamento::text as forma_tratamento,
            url_foto::text as url_foto,
            url_pagina::text as url_pagina,
            email::text as email,
            sigla_partido::text as sigla_partido,
            uf::text as uf,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from bronze
    ),

    -- A zona raw é append-only (ADR-0012/ADR-0021): a DAG roda @daily e cada
    -- execução acrescenta uma cópia do cadastro, então manter só a versão mais
    -- recente de cada senador é responsabilidade desta camada — ver
    -- airflow/helpers/landing_zone.py, "a deduplicação é responsabilidade da
    -- Silver". A chave é a mesma `primary_key` da DAG de ingestão.
    versionado as (
        select tipado.*, row_number() over (partition by id order by dt_ingest desc) as nu_versao from tipado
    )

select id, nome_parlamentar, sexo, forma_tratamento, url_foto, url_pagina, email, sigla_partido, uf, dt_ingest
from versionado
where nu_versao = 1
