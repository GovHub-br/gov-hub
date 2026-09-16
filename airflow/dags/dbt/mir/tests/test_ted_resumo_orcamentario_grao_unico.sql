-- Falha se o grão de ted_resumo_orcamentario não for uma linha por num_transf.
-- Protege contra fan-out (join com emendas, com a ponte de plano_acao ou com os
-- blocos de valor voltarem a multiplicar linhas) e contra quebra do grão.
--
-- A versão anterior deste teste afirmava o grão
-- (num_transf, ug_responsavel_codigo, ug_responsavel_nome) — descrevia o defeito,
-- não o contrato: com a UG na chave, uma transferência com N UGs virava N linhas
-- e repetia valor firmado, orçamento e financeiro (que só existem no grão da
-- transferência) em cada uma, inflando as somas. As UGs são atributo consolidado
-- (ugs_responsaveis_codigos / ugs_responsaveis_nomes / qtd_ugs_responsaveis); o
-- detalhe por UG vive em ted_empenhos_plano_acao.
--
-- Portado de data-application-mir (dags/dbt/mir/tests/
-- test_ted_resumo_orcamentario_grao_unico.sql).
select num_transf, count(*) as n_linhas
from {{ ref("ted_resumo_orcamentario") }}
group by num_transf
having count(*) > 1
