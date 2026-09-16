{{ config(materialized="table") }}

-- Silver do MIR: extrai o número do instrumento (convênio/termo de fomento/
-- TED) do texto livre de cada linha de emendas_partidos, quando o SIAFI não
-- traz o número em coluna própria — só em ne_info_complementar,
-- ne_ccor_descricao ou doc_observacao, como texto solto.
--
-- Cruza pacotes indiretamente via emendas_partidos (tesouro_gerencial +
-- camara_deputados/senado_federal) — vive no projeto do órgão (ADR-0004/
-- 0009). É a base de emendas_convenio.sql, do cruzamento com convênios do
-- SICONV.
--
-- Portado de data-application-mir (dags/dbt/mir/models/siconv_dbt/silver/
-- numero_transferencia.sql). Ref simples: emendas_partidos já vive neste
-- mesmo projeto.
with
    emendas as (
        select
            *,
            case
                when ne_info_complementar ~ '^\d+$'
                then ne_info_complementar::integer
                when ne_ccor_descricao ~* 'CONVENIO|FOMENTO|FOMENO'
                then
                    nullif(
                        regexp_replace(
                            ne_ccor_descricao, '.*(?:CONVENIO|FOMENTO|FOMENO)\s*(?:N[°º]?)?\s*(\d{6}).*', '\1'
                        ),
                        ne_ccor_descricao
                    )::integer
                when ne_ccor_descricao ~* 'TED\s*\d{6}'
                then nullif(regexp_replace(ne_ccor_descricao, '.*TED\s*(\d{6}).*', '\1'), ne_ccor_descricao)::integer
                when doc_observacao ~* 'CONVENIO|FOMENTO|FOMENO'
                then
                    nullif(
                        regexp_replace(doc_observacao, '.*(?:CONVENIO|FOMENTO|FOMENO)\s*(?:N[°º]?)?\s*(\d{6}).*', '\1'),
                        doc_observacao
                    )::integer
                when doc_observacao ~* 'TED\s*\d{6}'
                then nullif(regexp_replace(doc_observacao, '.*TED\s*(\d{6}).*', '\1'), doc_observacao)::integer
                else null
            end as numero_transferencia
        from {{ ref("emendas_partidos") }}
    )

select *
from emendas
