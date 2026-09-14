-- Falha se a ponte num_transf_n_plano_acao mapear uma mesma transferência (canônica)
-- para mais de um plano_acao. ted_resumo_orcamentario assume essa relação 1:1 ao
-- resolver plano_acao como atributo da transferência; se deixar de valer, o join da
-- ponte reintroduziria fan-out.
--
-- Portado de data-application-mir (dags/dbt/mir/tests/
-- test_num_transf_n_plano_acao_cardinalidade.sql).
select ltrim(trim(cast(num_transf as text)), '0') as num_transf_canon, count(distinct plano_acao) as n_planos
from {{ ref("num_transf_n_plano_acao") }}
where num_transf is not null and ltrim(trim(cast(num_transf as text)), '0') <> ''
group by ltrim(trim(cast(num_transf as text)), '0')
having count(distinct plano_acao) > 1
