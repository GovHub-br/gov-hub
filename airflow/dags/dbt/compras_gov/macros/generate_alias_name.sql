{#
    Nome da tabela a partir do nome do modelo (ADR-0009, ADR-0010).

    Silver e Gold levam a sigla da camada no nome do modelo (`slv_arp.sql`) para
    que a mesma entidade exista em camadas diferentes sem colidir: o dbt recusa
    dois modelos com o mesmo nome num pacote, e o Cosmos monta o id da task e o
    `--select` do teste só com o nome do modelo. A tabela continua com o nome da
    entidade, porque a camada já está no schema: silver/arp/slv_arp.sql →
    002_slv_arp.arp.

    `bnz_` não é removido: a Bronze não leva sigla, e o nome dela é a entidade da
    raw, de onde saem o caminho do Parquet (gov_bricks.bronze_parquet) e o Asset
    que agenda a DAG DuckDB. Modelo sem sigla mantém o próprio nome.

    Este macro vale para os modelos deste pacote também quando o projeto raiz é o
    de um órgão (o mgi, nas DAGs do Cosmos): o dbt usa o generate_alias_name de
    um pacote instalado nos modelos dele, com precedência sobre o da raiz
    (dbt-core, parser/base.py, RelationUpdate). Por isso o projeto do órgão não
    precisa de cópia.

    `alias` explícito na config tem precedência, como no padrão do dbt, mas foge
    da convenção: tests/unit/test_nomenclatura_modelos_dbt.py o reprova.
#}
{% macro generate_alias_name(custom_alias_name=none, node=none) -%}
    {%- if custom_alias_name -%} {{ return(custom_alias_name | trim) }} {%- endif -%}
    {%- for sigla in ["slv_", "gld_"] -%}
        {%- if node.name.startswith(sigla) -%} {{ return(node.name[sigla | length :]) }} {%- endif -%}
    {%- endfor -%}
    {{ return(node.name) }}
{%- endmacro %}
