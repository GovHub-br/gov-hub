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
  acesso.yml            # níveis de acesso e regra de recorte (ADR-0020)
  publicacao/
    _template.yml       # esqueleto para catalogar a publicação de um órgão
    mgi.yml             # um arquivo por órgão publicador
```

Os dois primeiros governam a **modelagem** (o que existe e como se cruza); os
dois últimos governam a **publicação** (o que vai ao ar e quem enxerga).

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

## Publicação e níveis de acesso

`publicacao/<orgao>.yml` declara o que um órgão publica — datasets, dashboards e
relatórios — e quem consome cada coisa. `acesso.yml` declara os níveis de
acesso: cada nível é, literalmente, *a lista de classificações do
[ADR-0013](../docs/adr/0013-padrao-documentacao-metadados-tabelas.md) que ele
enxerga*.

```bash
make acesso                # quem enxerga o quê, e com que recorte de linhas
make publicacao-sync       # regera airflow/dags/superset/<orgao>/acesso.yml
make publicacao-validar    # roda dentro de make lint e no CI
```

Esse par responde duas perguntas que a ferramenta de BI, sozinha, deixaria a
critério de quem monta cada dashboard:

| Pergunta | Onde é decidida |
|---|---|
| Quais **colunas** cada um vê? | `nivel` do consumidor × `meta.classificacao` da coluna no `schema.yml` do modelo |
| Quais **linhas** cada um vê? | `abrangencia` do consumidor: `proprio` gera recorte por `co_orgao`, `total` dispensa |

A validação compara o catálogo com os **bundles** de dashboard versionados em
`airflow/dags/superset/<orgao>/`: coluna exposta acima do nível do dataset,
coluna sem classificação declarada, dataset no bundle que ninguém catalogou e
DAG de relatório não declarada reprovam o build. O racional está no
[ADR-0019](../docs/adr/0019-publicacao-dashboards-relatorios.md) e no
[ADR-0020](../docs/adr/0020-niveis-acesso-consumo-dados.md).

`codigo_orgao_verificado: false` tem aqui o mesmo papel que `verificado` tem no
catálogo de chaves: marca o que ainda não foi conferido contra o dado ingerido,
gera aviso no CI e não reprova o build.
