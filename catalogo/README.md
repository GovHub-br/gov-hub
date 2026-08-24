# Catálogo de sistemas estruturantes

Este diretório é o **mapa de cruzamento** entre os sistemas estruturantes do
governo federal: quais entidades existem em cada sistema, e por quais chaves
elas podem ser cruzadas entre si.

Ele é a fonte de verdade que alimenta:

- o gerador de modelos dbt (`make modelo`), que escreve o SQL e o `schema.yml`
  já com as chaves conformadas e os metadados obrigatórios do
  [ADR-0013](../docs/adr/0013-padrao-documentacao-metadados-tabelas.md);
- o mapa de cruzamento (`make mapa`), que responde "o que dá para cruzar com o
  quê, e por qual chave";
- a validação de CI (`make catalogo-validar`), que reprova catálogo
  inconsistente antes do merge.

O racional está no
[ADR-0017](../docs/adr/0017-chaves-conformadas-cruzamento-sistemas-estruturantes.md).

## Estrutura

```
catalogo/
  chaves.yml            # vocabulário canônico de chaves conformadas e pontes
  sistemas/
    _template.yml       # esqueleto para catalogar um sistema novo
    compras_gov.yml     # um arquivo por sistema estruturante
```

## Os dois conceitos

**Chave conformada** (`chaves.yml`) é um identificador que significa a mesma
coisa em mais de um sistema — `co_orgao`, `co_uasg`, `nu_cnpj`,
`nu_matricula_siape`. Cada chave declara como é normalizada (`digitos` ou
`texto`, com `tamanho` opcional para completar com zeros à esquerda), qual
sistema é sua referência e sua classificação de sensibilidade.

**Ponte** (`pontes` em `chaves.yml`) é uma equivalência ou derivação conhecida
entre duas chaves — por exemplo, `co_uasg → co_ug_siafi`, ou `nu_ni → nu_cnpj`
quando o NI tem 14 dígitos. Cada ponte declara sua `confiabilidade`:

| Confiabilidade | Significado |
|---|---|
| `total` | Vale sempre; pode ser aplicada direto em Silver. |
| `parcial` | Vale na maioria dos casos; exige tratar a exceção e documentar no modelo. |
| `indicio` | Hipótese não verificada contra os dados; não use em Gold. |

## Como catalogar um sistema novo

1. `cp catalogo/sistemas/_template.yml catalogo/sistemas/<sistema>.yml`
2. Preencha as entidades e, em cada uma, as chaves conformadas que ela expõe.
   Use `verificado: false` enquanto o nome da coluna não tiver sido confirmado
   contra o dado realmente ingerido.
3. Se o sistema trouxer um identificador que ainda não existe em `chaves.yml`,
   adicione a chave lá — e só então referencie-a.
4. `make catalogo-validar && make mapa`

## Como gerar um modelo a partir do catálogo

```bash
make modelo ARGS="--sistema compras_gov --entidade contratos --camada silver"
```

O gerador cria o `.sql` e a entrada correspondente no `schema.yml`, na pasta
prevista pelo [ADR-0009](../docs/adr/0009-nomenclatura-pastas-arquivos-dbt.md),
com as chaves conformadas já normalizadas pelo macro `chave_conformada`. Ele
nunca sobrescreve arquivo existente sem `--forcar`.

## Honestidade do mapa

`verificado: false` não é um defeito do catálogo — é informação. Um mapeamento
não verificado aparece marcado no `make mapa` e gera aviso no CI, mas não
reprova o build: catalogar uma hipótese explícita é melhor que deixá-la
implícita no SQL de alguém. O que reprova o build é inconsistência —
chave inexistente, entidade sem descrição, sistema fora da nomenclatura.

`verificado` e `opcional` respondem perguntas diferentes, e confundi-las gera
teste errado:

| Campo | Pergunta | Efeito |
|---|---|---|
| `verificado` | A coluna de origem é mesmo essa? | `false` gera aviso no CI e marca o modelo gerado. |
| `opcional` | A chave se aplica a **todas** as linhas? | `true` suprime o teste `not_null` no modelo gerado. |

Um fornecedor pessoa jurídica não tem CPF: o mapeamento `nu_cpf → cpf` está
verificado *e* é opcional. Sem essa distinção, o gerador criaria um `not_null`
que reprova o build por um fato do domínio, não por um defeito no dado.
