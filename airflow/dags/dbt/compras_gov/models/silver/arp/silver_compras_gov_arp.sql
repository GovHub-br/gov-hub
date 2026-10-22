-- Schema, database e materialização herdados de dbt_project.yml (ADR-0022).
-- Silver inicial: valida o percurso Bronze → Silver, ainda sem limpeza.
-- Mantém todas as linhas, valores e tipos; somente os nomes seguem snake_case.
-- ref garante a ordem no mesmo fluxo dbt, sem uma nova DAG.
select
    "numeroAtaRegistroPreco" as numero_ata_registro_preco,
    "codigoUnidadeGerenciadora" as codigo_unidade_gerenciadora,
    "nomeUnidadeGerenciadora" as nome_unidade_gerenciadora,
    "codigoOrgao" as codigo_orgao,
    "nomeOrgao" as nome_orgao,
    "linkAtaPNCP" as link_ata_pncp,
    "linkCompraPNCP" as link_compra_pncp,
    "numeroCompra" as numero_compra,
    "anoCompra" as ano_compra,
    "codigoModalidadeCompra" as codigo_modalidade_compra,
    "nomeModalidadeCompra" as nome_modalidade_compra,
    "dataAssinatura" as data_assinatura,
    "dataVigenciaInicial" as data_vigencia_inicial,
    "dataVigenciaFinal" as data_vigencia_final,
    "valorTotal" as valor_total,
    "statusAta" as status_ata,
    "objeto",
    "quantidadeItens" as quantidade_itens,
    "dataHoraAtualizacao" as data_hora_atualizacao,
    "dataHoraInclusao" as data_hora_inclusao,
    "dataHoraExclusao" as data_hora_exclusao,
    "ataExcluido" as ata_excluido,
    "numeroControlePncpAta" as numero_controle_pncp_ata,
    "numeroControlePncpCompra" as numero_controle_pncp_compra,
    "idCompra" as id_compra,
    dt_ingest
from {{ ref("arp") }}
