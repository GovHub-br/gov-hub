-- Nesta primeira versão a Silver não pode filtrar nem multiplicar linhas.
select 1 as contagem_divergente
where (select count(*) from {{ ref("silver_compras_gov_arp") }}) != (select count(*) from {{ ref("arp") }})
