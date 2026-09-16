{{ config(materialized="view") }}

-- View do MIR: ponte entre número de transferência (nc/num_transf, como
-- aparece no SIAFI) e id_plano_acao (TED), resolvida por duas vias — via nota
-- de crédito SIAFI casada com nota de crédito do TED pela chave (nc, ug), ou
-- via sq_instrumento do plano de ação diretamente. Base de empenhos_por_
-- plano_acao.sql e nc_plano_acao.sql.
--
-- Cruza tesouro_gerencial (nc_tesouro_unificado) e transferegov_ted (source
-- notas_de_credito, ref planos_acao_ted) — por isso vive em dbt/mir/, não em
-- nenhum dos dois pacotes (ADR-0004/0009).
--
-- Portado de data-application-mir (dags/dbt/mir/models/empenhos_ted_dbt/
-- views/num_transf_n_plano_acao.sql). nc_tesouro_mir vira ref("tesouro_
-- gerencial", "nc_tesouro_unificado") (união pré/pós-2026 já migrada, ver
-- cabeçalho daquele arquivo); planos_acao_ted vira ref("transferegov_ted",
-- "planos_acao_ted").
with
    -- A raw é append-only (ADR-0012/ADR-0021) e a deduplicação é
    -- responsabilidade da Silver (ver airflow/helpers/landing_zone.py). O
    -- `select distinct` abaixo já colapsaria cópias idênticas, mas não uma
    -- *atualização* da nota na fonte: a versão antiga e a nova sobreviveriam
    -- como triplas distintas e criariam uma linha de ponte obsoleta. Por isso
    -- a dedup vem antes, por `id_nota` (a `primary_key` da DAG de ingestão),
    -- mantendo só a versão mais recente de cada nota.
    notas_credito_ted as (
        select *
        from
            (
                select
                    *,
                    row_number() over (
                        partition by id_nota order by (dt_ingest || '-03:00')::timestamptz desc
                    ) as nu_versao
                from {{ source("transferegov_ted", "notas_de_credito") }}
            ) as ndc_versionado
        where nu_versao = 1
    ),

    nc_transfere_gov as (
        select distinct id_plano_acao, tx_numero_nota as nc, ndc.cd_ug_emitente_nota as ug
        from notas_credito_ted ndc
        where ndc.tx_numero_nota is not null
    ),

    nc_siafi as (
        select distinct left(nc, 6) as ug, right(nc, 12) as nc, nt.nc_transferencia as num_transf
        from {{ ref("tesouro_gerencial", "nc_tesouro_unificado") }} nt
        where nc_transferencia != '-8'
    ),

    joined as (
        select distinct num_transf, id_plano_acao as plano_acao from nc_siafi left join nc_transfere_gov using (nc, ug)
    ),

    ranked as (
        select
            *,
            row_number() over (
                partition by num_transf order by case when plano_acao is not null then 1 else 2 end
            ) as rn
        from joined
    ),

    via_nc as (select num_transf, plano_acao from ranked where rn = 1),

    via_sq_instrumento as (
        select sq_instrumento as num_transf, id_plano_acao::text as plano_acao
        from {{ ref("transferegov_ted", "planos_acao_ted") }}
        where sq_instrumento is not null
    ),

    unificado as (
        select *
        from via_nc
        union
        select *
        from via_sq_instrumento
    ),

    final as (
        select
            *,
            row_number() over (
                partition by num_transf order by case when plano_acao is not null then 1 else 2 end
            ) as rn
        from unificado
    )

select num_transf, plano_acao
from final
where rn = 1
