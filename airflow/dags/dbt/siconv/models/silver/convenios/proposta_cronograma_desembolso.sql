-- Silver do SICONV: proposta com seu cronograma de desembolso. Junta duas
-- entidades do próprio pacote, sem filtro de órgão e sem cruzar nenhum outro
-- sistema — granularidade nacional, por isso fica em dbt/siconv/, não em
-- dbt/mir/ (ADR-0004: só sobe para o projeto do órgão quando cruza pacote).
--
-- Portado de data-application-mir
-- (siconv_dbt/silver/proposta_cronograma_desembolso.sql).
with
    proposta as (select * from {{ ref("proposta") }}),
    cronograma_desembolso as (select * from {{ ref("cronograma_desembolso") }})

select
    p.*,
    c.nr_convenio as nr_convenio_cronograma,
    c.nr_parcela_crono_desembolso,
    c.mes_crono_desembolso,
    c.ano_crono_desembolso,
    c.tipo_resp_crono_desembolso,
    c.valor_parcela_crono_desembolso
from proposta p
left join cronograma_desembolso c on p.id_proposta = c.id_proposta
