{#
    Converte um valor financeiro no formato textual brasileiro (separador de
    milhar '.', decimal ',', negativos entre parênteses — convenção comum em
    relatórios do SIAFI/Tesouro Gerencial) para numeric(15,2).

    Portado de data-application-mir (dags/dbt/mir/macros/parse_financial_value.sql).
    Vive em gov_bricks porque a mesma lógica se repete em qualquer sistema que
    consome relatórios do Tesouro — não é específica de um sistema.
#}
{% macro parse_financial_value(column_name) %}

    case
        when {{ column_name }} is null or trim({{ column_name }}) = ''
        then 0.00::numeric(15, 2)
        when {{ column_name }} like '%NaN%'
        then 0.00::numeric(15, 2)
        when {{ column_name }} like '(%'
        then
            regexp_replace(
                replace(coalesce({{ column_name }}, '0'), '.', ''), '(\()?(\d+),(\d+)(\))?', '-\2.\3'
            )::numeric(15, 2)
        else replace(replace(coalesce({{ column_name }}, '0'), '.', ''), ',', '.')::numeric(15, 2)
    end

{% endmacro %}
