-- Silver de contratos_gov.faturas — verdade única do dado (ADR-0006).
--
-- Granularidade: uma linha por fatura de um contrato.
--
-- Tipagem portada de data-application-mir (compras_gov_dbt/bronze/faturas.sql).
with
    bronze as (select * from {{ source("contratos_gov", "faturas") }}),

    tipado as (
        select
            nullif(cast(id as text), '')::integer as id,
            cast(contrato_id as text) as contrato_id,
            tipolistafatura_id,
            tipo_instrumento_cobranca,
            justificativafatura_id,
            sfadrao_id,
            numero,
            numero_serie,
            fornecedor_contrato,
            fornecedor_ic,
            contratante,
            case
                when emissao is not null and cast(emissao as text) ~ '^\d{4}-\d{2}-\d{2}$' then cast(emissao as date)
            end as emissao,
            case
                when prazo is not null and cast(prazo as text) ~ '^\d{4}-\d{2}-\d{2}$' then cast(prazo as date)
            end as prazo,
            case
                when vencimento is not null and cast(vencimento as text) ~ '^\d{4}-\d{2}-\d{2}$'
                then cast(vencimento as date)
            end as vencimento,
            replace(replace(nullif(valor, ''), '.', ''), ',', '.')::numeric(15, 2) as valor,
            replace(replace(nullif(juros, ''), '.', ''), ',', '.')::numeric(15, 2) as juros,
            replace(replace(nullif(multa, ''), '.', ''), ',', '.')::numeric(15, 2) as multa,
            replace(replace(nullif(glosa, ''), '.', ''), ',', '.')::numeric(15, 2) as glosa,
            replace(replace(nullif(valorliquido, ''), '.', ''), ',', '.')::numeric(15, 2) as valorliquido,
            base_calculo_inss,
            aliquota_inss,
            optante_cprb,
            optante_simples,
            valor_inss,
            case
                when data_liquidacao is not null and cast(data_liquidacao as text) ~ '^\d{4}-\d{2}-\d{2}$'
                then to_date(cast(data_liquidacao as text), 'YYYY-MM-DD')
            end as data_liquidacao,
            nota_cancelada,
            processo,
            case
                when protocolo is not null and cast(protocolo as text) ~ '^\d{4}-\d{2}-\d{2}$'
                then cast(protocolo as date)
            end as protocolo,
            case
                when ateste is not null and cast(ateste as text) ~ '^\d{4}-\d{2}-\d{2}$' then cast(ateste as date)
            end as ateste,
            repactuacao,
            infcomplementar,
            nullif(mesref, '')::integer as mesref,
            nullif(anoref, '')::integer as anoref,
            situacao,
            chave_nfe,
            dados_referencia,
            dados_item_faturado,
            dados_empenho,
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
    tipolistafatura_id,
    tipo_instrumento_cobranca,
    justificativafatura_id,
    sfadrao_id,
    numero,
    numero_serie,
    fornecedor_contrato,
    fornecedor_ic,
    contratante,
    emissao,
    prazo,
    vencimento,
    valor,
    juros,
    multa,
    glosa,
    valorliquido,
    base_calculo_inss,
    aliquota_inss,
    optante_cprb,
    optante_simples,
    valor_inss,
    data_liquidacao,
    nota_cancelada,
    processo,
    protocolo,
    ateste,
    repactuacao,
    infcomplementar,
    mesref,
    anoref,
    situacao,
    chave_nfe,
    dados_referencia,
    dados_item_faturado,
    dados_empenho,
    dt_ingest
from versionado
where nu_versao = 1
