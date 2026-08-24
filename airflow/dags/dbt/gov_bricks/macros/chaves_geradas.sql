{#
    GERADO por `make catalogo-sync` a partir de catalogo/chaves.yml.
    Não edite à mão — a edição é desfeita na próxima geração e o CI
    reprova o build quando este arquivo diverge do catálogo.
#}
{% macro chaves_conformadas() %}
    {{
        return(
            {
                "co_natureza_despesa": {"normalizacao": "digitos", "tamanho": 8, "classificacao": "publico"},
                "co_orgao": {"normalizacao": "digitos", "tamanho": 5, "classificacao": "publico"},
                "co_uasg": {"normalizacao": "digitos", "tamanho": 6, "classificacao": "publico"},
                "co_ug_siafi": {"normalizacao": "digitos", "tamanho": 6, "classificacao": "publico"},
                "nu_cnpj": {"normalizacao": "digitos", "tamanho": 14, "classificacao": "publico"},
                "nu_cpf": {"normalizacao": "digitos", "tamanho": 11, "classificacao": "pessoal"},
                "nu_matricula_siape": {"normalizacao": "digitos", "tamanho": 7, "classificacao": "pessoal"},
                "nu_ni": {"normalizacao": "digitos", "tamanho": none, "classificacao": "publico"},
            }
        )
    }}
{% endmacro %}
