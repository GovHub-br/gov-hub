-- Silver do SICONV: pagamento tipado a partir do source (papel que, antes do
-- ADR-0017, era da camada Bronze modelada). Sem filtro de órgão — vive no
-- pacote compartilhado (ADR-0004).
--
-- Portado de data-application-mir (siconv_dbt/bronze/pagamento.sql).
-- Granularidade: uma linha por movimento financeiro de pagamento.
with
    pagamento_raw as (
        select
            nullif(nr_mov_fin, '')::integer as nr_mov_fin,
            nullif(nr_convenio, '')::text as nr_convenio,
            identif_fornecedor::text as identif_fornecedor,
            nome_fornecedor::text as nome_fornecedor,
            tp_mov_financeira::text as tp_mov_financeira,
            case
                when nullif(data_pag, '') is null
                then null
                when data_pag ~ '^\d{2}/\d{2}/\d{4}$'
                then to_date(data_pag, 'DD/MM/YYYY')
                else to_date(data_pag, 'YYYY-MM-DD')
            end as data_pag,
            nr_dl::text as nr_dl,
            desc_dl::text as desc_dl,
            replace(nullif(vl_pago, ''), ',', '.')::numeric(15, 2) as vl_pago,
            nullif(id_dl, '')::integer as id_dl,
            case
                when nullif(data_emissao_dl, '') is null
                then null
                when data_emissao_dl ~ '^\d{2}/\d{2}/\d{4}$'
                then to_date(data_emissao_dl, 'DD/MM/YYYY')
                else to_date(data_emissao_dl, 'YYYY-MM-DD')
            end as data_emissao_dl,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siconv", "pagamento") }}
    ),
    -- A zona raw é append-only (ADR-0012/ADR-0021): cada execução da DAG
    -- acrescenta uma cópia da fonte, e o contrato do framework põe a
    -- deduplicação nesta camada — ver airflow/helpers/landing_zone.py, "a
    -- deduplicação é responsabilidade da Silver". Sem isto, a Gold soma a
    -- mesma linha uma vez por execução.
    versionado as (
        select pagamento_raw.*, row_number() over (partition by nr_mov_fin order by dt_ingest desc) as nu_versao
        from pagamento_raw
    )

select
    nr_mov_fin,
    nr_convenio,
    identif_fornecedor,
    nome_fornecedor,
    tp_mov_financeira,
    data_pag,
    nr_dl,
    desc_dl,
    vl_pago,
    id_dl,
    data_emissao_dl,
    dt_ingest
from versionado
where nu_versao = 1
