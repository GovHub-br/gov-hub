{#
    Nome do schema derivado da pasta do modelo (ADR-0010). A lógica vive em
    gov_bricks.schema_medallion; este arquivo existe porque dbt só reconhece a
    sobrescrita de generate_schema_name no projeto raiz.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is not none -%} {{ return(custom_schema_name | trim) }} {%- endif -%}
    {{ return(gov_bricks.schema_medallion(node)) }}
{%- endmacro %}
