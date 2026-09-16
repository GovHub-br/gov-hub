{#
    Normaliza um número de nota de crédito extraído de texto livre (ex.:
    "2024NC001234") para o formato "prefixo" + 5 dígitos com zero à esquerda
    dos últimos 4 caracteres — ex.: "2024NC" + "01234".

    Portado de data-application-mir (dags/dbt/mir/macros/udfs/f_format_nc.sql),
    onde vivia como função Postgres (`{{ target.schema }}.format_nc(...)`,
    criada via hook `on-run-start`). Reescrita como macro dbt (expressão SQL
    inline, sem função armazenada no banco) porque este monorepo não tem essa
    infraestrutura de UDFs e o único uso é local a empenhos_por_plano_acao.sql
    — não há motivo para introduzir um hook global por uma única chamada.
    Mesmo comportamento do original: entrada nula, ou cujos últimos 4
    caracteres não sejam 1 a 4 dígitos, retorna nulo.
#}
{% macro format_nc(expressao) %}
    case
        when right({{ expressao }}, 4) ~ '^[0-9]{1,4}$'
        then concat(left({{ expressao }}, 7), to_char(right({{ expressao }}, 4)::numeric, 'FM00000'))
        else null
    end
{% endmacro %}
