{#
    Converte uma data no formato "MES/ANO" com abreviação de mês em português
    (ex.: "JAN/2024") para date — primeiro dia do mês. Formato usado pelo
    campo emissao_mes em relatórios do Tesouro Gerencial.

    Portado de data-application-mir (dags/dbt/mir/macros/udfs/f_parse_dates.sql),
    onde vivia como função Postgres (`{{ target.schema }}.parse_date(...)`,
    criada via hook `on-run-start`). Reescrita como macro dbt (expressão SQL
    inline, sem função armazenada no banco) — mesmo caminho já seguido por
    format_nc.sql. Vive em gov_bricks porque o formato "MES/ANO" abreviado em
    português é da fonte (Tesouro Gerencial), não de um sistema específico.

    Mesma aritmética do original: ao invés de montar "MES/ANO" diretamente
    (to_date não entende abreviação em português), soma meses a partir de
    dezembro do ano anterior — dezembro + 1 mês = janeiro do ano pedido,
    dezembro + 12 meses = dezembro do ano pedido.

    Quem chama precisa garantir o formato antes (ver uso em tg_emendas.sql:
    guarda com `~ '^[A-Z]{3}/[0-9]{4}$'`) — uma abreviação de mês fora das 12
    esperadas quebra o cast de intervalo, igual ao original.
#}
{% macro parse_date(expressao) %}
    (
        to_date((split_part({{ expressao }}, '/', 2)::numeric - 1) || '-12', 'YYYY-MM') + (
            case
                split_part({{ expressao }}, '/', 1)
                when 'JAN'
                then '01'
                when 'FEV'
                then '02'
                when 'MAR'
                then '03'
                when 'ABR'
                then '04'
                when 'MAI'
                then '05'
                when 'JUN'
                then '06'
                when 'JUL'
                then '07'
                when 'AGO'
                then '08'
                when 'SET'
                then '09'
                when 'OUT'
                then '10'
                when 'NOV'
                then '11'
                when 'DEZ'
                then '12'
                else split_part({{ expressao }}, '/', 1)
            end
            || ' months'
        )::interval
    )::date
{% endmacro %}
