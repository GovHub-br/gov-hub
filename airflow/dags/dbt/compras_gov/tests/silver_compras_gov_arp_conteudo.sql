-- Nesta Silver inicial, somente os nomes das colunas mudam. Comparar nos dois
-- sentidos com EXCEPT ALL detecta valores alterados, nulos e duplicatas perdidas.
with
    bronze as (
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
    ),
    silver as (
        select
            numero_ata_registro_preco,
            codigo_unidade_gerenciadora,
            nome_unidade_gerenciadora,
            codigo_orgao,
            nome_orgao,
            link_ata_pncp,
            link_compra_pncp,
            numero_compra,
            ano_compra,
            codigo_modalidade_compra,
            nome_modalidade_compra,
            data_assinatura,
            data_vigencia_inicial,
            data_vigencia_final,
            valor_total,
            status_ata,
            objeto,
            quantidade_itens,
            data_hora_atualizacao,
            data_hora_inclusao,
            data_hora_exclusao,
            ata_excluido,
            numero_controle_pncp_ata,
            numero_controle_pncp_compra,
            id_compra,
            dt_ingest
        from {{ ref("silver_compras_gov_arp") }}
    ),
    somente_bronze as (
        select *
        from bronze
        except all
        select *
        from silver
    ),
    somente_silver as (
        select *
        from silver
        except all
        select *
        from bronze
    )
select *
from somente_bronze
union all
select *
from somente_silver
