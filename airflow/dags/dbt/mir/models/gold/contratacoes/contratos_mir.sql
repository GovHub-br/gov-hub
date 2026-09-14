-- Gold: contratos_mir — produto de dados (ADR-0006).
--
-- MOCK de time para validar o escopo por pasta do dag_selector (ADR-0005) e o
-- roteamento por fila. Mantém a forma de um Gold real, sem a ambição de um.
with
    contratos as (select * from {{ ref("compras_gov", "contratos") }}),
    uasg as (select * from {{ ref("compras_gov", "uasg") }}),

    cruzado as (
        select contratos.*, uasg.co_orgao
        from contratos
        left join uasg on contratos.co_uasg = uasg.co_uasg
    )

select *
from cruzado
