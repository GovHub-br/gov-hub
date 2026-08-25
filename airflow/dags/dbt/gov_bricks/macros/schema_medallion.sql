{#
    Nome do schema a partir da pasta de camada/domínio do modelo.

    Implementa o ADR-0010 sobre a estrutura de pastas do ADR-0009:

        ref/<escopo>/<entidade>          → 000_ref_<escopo>
        bronze/<entidade>                → 001_bnz_<pacote>
        bronze/<sistema>/<entidade>      → 001_bnz_<sistema>
        silver/<dominio>/<entidade>      → 002_slv_<dominio>
        gold/<produto>/<entidade>        → 003_gld_<produto>

    Quando a camada não tem subpasta de escopo, o escopo é o nome do pacote —
    que, em um pacote de sistema, é o próprio sistema de origem.
#}
{% macro schema_medallion(node) %}
    {%- set prefixos = {
        "ref": "000_ref",
        "bronze": "001_bnz",
        "silver": "002_slv",
        "gold": "003_gld",
    } -%}
    {%- set partes = node.path.replace("\\", "/").split("/") -%}
    {%- set camada = partes[0] -%}
    {%- if camada not in prefixos -%}
        {{
            exceptions.raise_compiler_error(
                "Modelo fora da estrutura de camadas do ADR-0009: "
                ~ node.package_name
                ~ "/"
                ~ node.path
                ~ ". Esperado ref/, bronze/, silver/ ou gold/ como pasta de topo."
            )
        }}
    {%- endif -%}
    {%- if partes | length > 2 -%} {%- set escopo = partes[-2] -%}
    {%- else -%} {%- set escopo = node.package_name -%}
    {%- endif -%}
    {{ return(prefixos[camada] ~ "_" ~ escopo) }}
{% endmacro %}
