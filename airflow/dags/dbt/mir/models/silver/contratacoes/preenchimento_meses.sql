{{ config(materialized="view") }}

-- Silver do MIR: calendário mensal completo por contrato das UGs do MIR
-- (230002/810008), preenchendo os meses sem cronograma/fatura via left join
-- de volta em cronogramas_faturas_mensal.
--
-- Órgão-específico por filtrar pelas UGs do MIR — vive no projeto do órgão,
-- não em nenhum pacote de sistema (ADR-0004/0009).
--
-- Portado de data-application-mir (contratos_dbt/views/preenchimento_meses.sql).
-- Granularidade: uma linha por (contrato_id, mes_referencia).
with

    limites as (
        select cf.contrato_id, min(cf.mes_referencia) as mes_inicial, max(cf.mes_referencia) as mes_final
        from {{ ref("cronogramas_faturas_mensal") }} as cf
        inner join
            {{ ref("contratos_gov", "contratos") }} as ct
            on trim(cf.contrato_id) = trim(cast(ct.id as text))
            and ct.contratante__orgao__unidade_gestora__codigo in ('230002', '810008')
        group by 1
    ),

    calendario as (
        select l.contrato_id, gs.mes_referencia::date as mes_referencia
        from limites as l
        cross join lateral generate_series(l.mes_inicial, l.mes_final, interval '1 month') as gs(mes_referencia)
    ),

    final as (
        select
            cal.contrato_id,
            cal.mes_referencia,
            cf.valor_cronograma,
            cf.valor_faturas_pagas,
            cf.valor_faturas_pendentes,
            cf.saldo_contratual_disponivel,
            ct.numero as numero_contrato,
            ct.situacao as situacao_contrato,
            ct.fornecedor_nome,
            ct.fornecedor_cnpj_cpf_idgener,
            ct.contratante__orgao__nome as orgao_contratante,
            ct.contratante__orgao__unidade_gestora__nome as unidade_gestora,
            ct.vigencia_inicio,
            ct.vigencia_fim
        from calendario as cal
        inner join
            {{ ref("contratos_gov", "contratos") }} as ct
            on trim(cal.contrato_id) = trim(cast(ct.id as text))
            and ct.contratante__orgao__unidade_gestora__codigo in ('230002', '810008')
        left join
            {{ ref("cronogramas_faturas_mensal") }} as cf
            on cal.contrato_id = cf.contrato_id
            and cal.mes_referencia = cf.mes_referencia
    )

select *
from final
