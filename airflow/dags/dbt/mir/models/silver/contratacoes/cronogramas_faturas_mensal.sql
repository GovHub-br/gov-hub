{{ config(materialized="table") }}

-- Silver do MIR: reconciliação mensal entre cronograma contratual e faturas
-- pagas/pendentes, com saldo contratual disponível.
--
-- Este modelo, isoladamente, só usa entidades de contratos_gov (cronograma,
-- faturas, contratos). Vive no projeto do órgão (não no pacote contratos_gov)
-- porque faz parte da mesma família de modelos de contratações do MIR
-- (estagios_mensal/contratos_estagios, que cruzam contratos_gov +
-- tesouro_gerencial) e é consumido diretamente por preenchimento_meses, que
-- é órgão-específico por filtrar pelas UGs do MIR (230002/810008) — mantê-lo
-- junto de seus consumidores no mesmo pacote evita um ref cruzado
-- desnecessário de volta para contratos_gov (ADR-0004/0009).
--
-- Portado de data-application-mir (contratos_dbt/silver/cronogramas_faturas_mensal.sql).
-- Granularidade: uma linha por (contrato_id, anoref, mesref).
with

    cronograma_mensal as (
        select
            cast(contrato_id as text) as contrato_id,
            anoref,
            mesref,
            make_date(anoref, mesref, 1) as mes_referencia,
            sum(coalesce(valor, 0)) as valor_cronograma
        from {{ ref("contratos_gov", "cronograma") }}
        group by 1, 2, 3, 4
    ),

    faturas_pagas_mensal as (
        select
            cast(contrato_id as text) as contrato_id,
            extract(year from emissao)::integer as anoref,
            extract(month from emissao)::integer as mesref,
            date_trunc('month', emissao)::date as mes_referencia,
            sum(coalesce(valor, 0)) as valor_faturas_pagas
        from {{ ref("contratos_gov", "faturas") }}
        where lower(trim(situacao)) = 'siafi apropriado' and emissao is not null
        group by 1, 2, 3, 4
    ),

    faturas_pendentes_mensal as (
        select
            cast(contrato_id as text) as contrato_id,
            extract(year from emissao)::integer as anoref,
            extract(month from emissao)::integer as mesref,
            date_trunc('month', emissao)::date as mes_referencia,
            sum(coalesce(valor, 0)) as valor_faturas_pendentes
        from {{ ref("contratos_gov", "faturas") }}
        where lower(trim(situacao)) = 'pendente' and emissao is not null
        group by 1, 2, 3, 4
    ),

    cronograma_faturas as (
        select
            c.contrato_id,
            c.anoref,
            c.mesref,
            c.mes_referencia,
            coalesce(c.valor_cronograma, 0) as valor_cronograma,
            coalesce(fp.valor_faturas_pagas, 0) as valor_faturas_pagas,
            coalesce(fpe.valor_faturas_pendentes, 0) as valor_faturas_pendentes,
            coalesce(c.valor_cronograma, 0)
            - coalesce(fp.valor_faturas_pagas, 0)
            - coalesce(fpe.valor_faturas_pendentes, 0) as saldo_contratual_disponivel
        from cronograma_mensal as c
        left join
            faturas_pagas_mensal as fp
            on c.contrato_id = fp.contrato_id
            and c.anoref = fp.anoref
            and c.mesref = fp.mesref
        left join
            faturas_pendentes_mensal as fpe
            on c.contrato_id = fpe.contrato_id
            and c.anoref = fpe.anoref
            and c.mesref = fpe.mesref
    ),

    final as (
        select
            cf.contrato_id,
            cf.anoref,
            cf.mesref,
            cf.mes_referencia,
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
        from cronograma_faturas as cf
        left join {{ ref("contratos_gov", "contratos") }} as ct on trim(cf.contrato_id) = trim(ct.id)
    )

select *
from final
