-- Silver do SICONV: proposta com seu histórico de situação. Junta duas
-- entidades do próprio pacote, sem filtro de órgão e sem cruzar nenhum outro
-- sistema — granularidade nacional, por isso fica em dbt/siconv/, não em
-- dbt/mir/ (ADR-0004).
--
-- Portado de data-application-mir
-- (siconv_dbt/silver/proposta_historico_situacao.sql).
with
    proposta as (select * from {{ ref("proposta") }}),
    historico_situacao as (select * from {{ ref("historico_situacao") }})

select p.*, h.dia_historico_sit, h.historico_sit, h.dias_historico_sit, h.cod_historico_sit
from proposta p
left join historico_situacao h on p.id_proposta = h.id_proposta
