{{ config(materialized="table") }}

-- Silver do MIR: notas de crédito unificadas associadas a um plano de ação
-- de TED (via num_transf_n_plano_acao), excluindo a nota de crédito "-8"
-- (que não representa transferência real).
--
-- Refs simples — nc_unificado e num_transf_n_plano_acao já vivem neste
-- mesmo projeto (dbt/mir/models/silver/transferencias/).
--
-- Portado de data-application-mir (dags/dbt/mir/models/empenhos_ted_dbt/
-- silver/nc_plano_acao.sql).
with
    raw_data as (select * from {{ ref("nc_unificado") }} where nc_transferencia != '-8'),

    planos_de_acao as (select distinct * from {{ ref("num_transf_n_plano_acao") }} where plano_acao is not null),

    result_table as (
        select rd.*, pda.plano_acao::integer as id_plano_acao
        from raw_data rd
        left join planos_de_acao pda on rd.nc_transferencia = pda.num_transf
    )

select *
from result_table
