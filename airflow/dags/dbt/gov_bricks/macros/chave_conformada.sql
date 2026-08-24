{#
    Normaliza uma coluna de origem para uma chave conformada (ADR-0017).

    Cruzar sistemas estruturantes falha, na prática, por diferença de formato:
    o mesmo código de órgão chega como inteiro em um sistema, como texto com
    zeros à esquerda em outro, e com máscara em um terceiro. Este macro aplica
    a normalização declarada em catalogo/chaves.yml, para que o join seja
    sempre entre valores comparáveis.

        {{ chave_conformada("co_uasg", "codigounidadegestora") }} as co_uasg
#}
{% macro chave_conformada(chave, coluna) %}
    {%- set definicoes = chaves_conformadas() -%}
    {%- if chave not in definicoes -%}
        {{
            exceptions.raise_compiler_error(
                "Chave conformada desconhecida: '"
                ~ chave
                ~ "'. Declare-a em catalogo/chaves.yml e rode `make catalogo-sync`. "
                ~ "Conhecidas: "
                ~ definicoes.keys()
                | join(", ") ~ "."
            )
        }}
    {%- endif -%}
    {%- set definicao = definicoes[chave] -%}
    {%- set texto = "cast(" ~ coluna ~ " as varchar)" -%}
    {%- if definicao["normalizacao"] == "digitos" -%}
        {%- set limpo = "nullif(regexp_replace(" ~ texto ~ ", '[^0-9]', '', 'g'), '')" -%}
        {%- if definicao["tamanho"] -%}
            {#-
                `tamanho` restaura zeros à esquerda perdidos quando a origem
                guarda o código como inteiro — nunca encurta a chave. lpad, por
                si só, TRUNCA valores mais longos que o alvo, o que produziria
                um join silenciosamente errado; greatest() garante que o alvo
                nunca seja menor que o próprio valor.
            -#}
            {%- set alvo = "greatest(length(" ~ limpo ~ "), " ~ definicao["tamanho"] ~ ")" -%}
            {{ return("lpad(" ~ limpo ~ ", " ~ alvo ~ ", '0')") }}
        {%- else -%} {{ return(limpo) }}
        {%- endif -%}
    {%- elif definicao["normalizacao"] == "texto" -%} {{ return("nullif(upper(trim(" ~ texto ~ ")), '')") }}
    {%- else -%}
        {{
            exceptions.raise_compiler_error(
                "Normalização desconhecida para a chave '" ~ chave ~ "': " ~ definicao["normalizacao"]
            )
        }}
    {%- endif -%}
{% endmacro %}
