{#
    Nome da tabela derivado do nome do modelo (ADR-0010). Silver leva o prefixo
    `slv_` no modelo (slv_orgao.sql), mas a tabela fica sem a sigla, porque o
    schema já a carrega (002_slv_<dominio>.orgao). dbt só reconhece a
    sobrescrita no projeto raiz; por isso o mgi tem uma cópia deste arquivo.

    `alias=` explícito continua valendo, mas foge da convenção.
#}
{% macro generate_alias_name(custom_alias_name=none, node=none) -%}
    {%- if custom_alias_name is not none -%} {{ return(custom_alias_name | trim) }} {%- endif -%}
    {%- if node.package_name == "compras_gov" and node.name.startswith("slv_") -%}
        {{ return(node.name[4:]) }}
    {%- endif -%}
    {{ return(node.name) }}
{%- endmacro %}
