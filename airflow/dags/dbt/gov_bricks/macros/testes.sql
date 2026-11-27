{#
    Unicidade de uma combinação de colunas — a chave primária composta que a
    maioria das entidades dos sistemas estruturantes tem. Evita depender de um
    pacote externo para o teste mais comum do framework.

        data_tests:
          - gov_bricks.unicidade_composta:
              colunas: [co_uasg, numerocontrato, nu_ni]
#}
{% test unicidade_composta(model, colunas) %}
    select {{ colunas | join(", ") }}, count(*) as qt_registros
    from {{ model }}
    group by {{ colunas | join(", ") }}
    having count(*) > 1
{% endtest %}
