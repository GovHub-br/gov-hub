-- Silver do SICONV: meta física com o cronograma de desembolso da mesma
-- proposta. Junta duas entidades do próprio pacote, sem filtro de órgão e
-- sem cruzar nenhum outro sistema — granularidade nacional, por isso fica em
-- dbt/siconv/, não em dbt/mir/ (ADR-0004).
--
-- Portado de data-application-mir
-- (siconv_dbt/silver/meta_cronograma_desembolso.sql).
with
    meta_crono_fisico as (select * from {{ ref("meta_crono_fisico") }}),
    cronograma_desembolso as (select * from {{ ref("cronograma_desembolso") }})

select
    m.*,
    c.nr_parcela_crono_desembolso,
    c.mes_crono_desembolso,
    c.ano_crono_desembolso,
    c.tipo_resp_crono_desembolso,
    c.valor_parcela_crono_desembolso
from meta_crono_fisico m
left join cronograma_desembolso c on m.id_proposta = c.id_proposta
