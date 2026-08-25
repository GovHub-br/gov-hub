# ADR-0018: Padrão de nomenclatura e execução das DAGs de transformação

- **Status**: Proposto
- **Data**: 2026-08-24
- **Autores**: -
- **Revisores**: -

## Introdução ao problema

O [ADR-0007](./0007-nomenclatura-pastas-dags-ingestao.md) padronizou o nome
das DAGs de **ingestão** e deixou explícito, entre suas ações decorrentes,
que o padrão para DAGs de **transformação** ficaria para um ADR futuro.
Enquanto isso, o [ADR-0002](./0002-dbt-como-ferramenta-de-transformacao-de-dados.md)
adotou dbt como ferramenta de transformação e o
[ADR-0017](./0017-chaves-conformadas-cruzamento-sistemas-estruturantes.md)
passou a gerar modelos Silver e Gold a partir do catálogo.

O resultado é uma lacuna concreta: existem projetos dbt versionados no
monorepo, com modelos gerados e testados, e **nada os executa**. Nenhuma DAG
roda `dbt build`. A Bronze é atualizada diariamente pelas DAGs de ingestão e
as camadas seguintes nunca são materializadas.

Fechar essa lacuna exige decidir duas coisas que, hoje, estão em aberto:

- **Como nomear e onde colocar** a DAG que executa um projeto dbt — sem
  convenção, DAGs de transformação reproduzem exatamente a inconsistência
  que o ADR-0007 resolveu para ingestão.
- **Com que granularidade executar** o dbt no Airflow. A escolha não é
  cosmética: ela determina se um modelo que falha derruba o projeto inteiro,
  se o retry reprocessa tudo, e se dá para saber qual modelo quebrou sem
  abrir o log da task.

## Decisão

### Pasta e nome do arquivo

Toda DAG de transformação segue o padrão:

```text
airflow/dags/data_transform/<orgao>/{orgao}_transform_dag.py            # projeto dbt inteiro do órgão
airflow/dags/data_transform/<orgao>/{escopo}_{orgao}_transform_dag.py   # um recorte do projeto
```

- `data_transform/` fica no mesmo nível de `data_ingest/`, preservando a
  simetria da estrutura do [ADR-0004](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md):
  a pasta diz a ação, a subpasta diz de quem é o código.
- A pasta imediata é **sempre** de órgão. Diferente da ingestão, não existe
  DAG de transformação compartilhada: pelo ADR-0004, cada órgão tem seu
  próprio banco e seu próprio projeto dbt, e é o projeto do órgão que importa
  os pacotes dos sistemas estruturantes que ele consome. O que é
  compartilhado são os **modelos** (o pacote `dbt/<sistema>/`), não a
  execução deles.
- `{escopo}`: o recorte do projeto que a DAG executa, expresso como seletor
  dbt — um produto de dados (Gold) ou um domínio (Silver), no vocabulário já
  definido pelo [ADR-0010](./0010-nomenclatura-schemas-tabelas-bronze-silver-gold.md).
  É **omitido** quando a DAG executa o projeto inteiro, caso em que o nome do
  órgão sozinho já descreve o escopo.
- Sufixo de ação fixo `_transform_dag`, espelhando o `_ingest_dag` do
  ADR-0007.
- `dag_id` replica o nome do arquivo sem a extensão `.py`, mantendo a
  correspondência 1-para-1 do ADR-0007.
- Valem as mesmas regras gerais de nomenclatura do ADR-0007: apenas
  minúsculas, dígitos e underscore.

### Execução: Cosmos, uma task do Airflow por nó do dbt

A DAG é construída com `DbtDag`, do
[Astronomer Cosmos](https://astronomer.github.io/astronomer-cosmos/), que lê
o grafo do projeto dbt e o converte em tasks do Airflow:

- **Uma task por nó dbt** (modelo, teste, seed, snapshot), com as
  dependências entre elas herdadas do próprio `ref()` — o grafo que o dbt já
  conhece não é reescrito à mão no Airflow.
- O profile é o compartilhado do monorepo (`airflow/dags/dbt/profiles.yml`,
  ADR-0017), referenciado por caminho e com credenciais vindas de variáveis
  de ambiente — nada de credencial versionada.
- Tags conforme o [ADR-0008](./0008-padrao-uso-tags-nomenclatura.md):
  `orgao:{orgao}` sempre; `sistema:{sistema}` para cada sistema estruturante
  cujo pacote o projeto consome; `camada:{camada}` para cada camada que a DAG
  materializa.

## Alternativas consideradas

### Alternativa A: `BashOperator` com `dbt build` (uma task por projeto)

- Descrição: uma única task executando `dbt build` no projeto inteiro.
- Prós: trivial de escrever, sem dependência adicional, e é o caminho que a
  maioria dos times toma primeiro.
- Contras: o projeto inteiro é uma caixa preta para o Airflow. Um modelo
  Gold que falha marca a task inteira como falha, e o retry reprocessa todos
  os modelos Silver que já tinham passado; descobrir qual modelo quebrou
  exige ler o log da task; e a interface do Airflow não mostra nada do grafo
  de dependências que o dbt conhece.

### Alternativa B: uma DAG do Airflow por modelo dbt

- Descrição: cada modelo vira sua própria DAG, encadeadas por
  `Dataset`/sensores.
- Prós: granularidade máxima de retry e agendamento independente por modelo.
- Contras: multiplica o número de DAGs pelo número de modelos e obriga a
  reimplementar à mão, em objetos do Airflow, o grafo de dependências que o
  dbt já resolve sozinho — duas fontes de verdade para a mesma informação,
  que divergem no primeiro `ref()` novo que alguém escrever.

### Cosmos, uma task por nó dbt — decisão proposta

- Descrição: `DbtDag` do Cosmos converte o grafo dbt em tasks do Airflow
  automaticamente.
- Por que foi escolhida: entrega a granularidade da Alternativa B — retry e
  log por modelo, grafo visível na interface — sem o custo dela, porque o
  grafo é **derivado** do projeto dbt em vez de mantido em paralelo. É a
  única das três em que acrescentar um `ref()` a um modelo não exige nenhuma
  mudança correspondente no Airflow.

## Tradeoffs

### Vantagens

- **[Alto impacto]** Falha e retry passam a ser por modelo: um erro em um
  modelo Gold não obriga a reprocessar a Silver inteira que já tinha rodado.
- **[Alto impacto]** O grafo de dependências vive só no dbt e é derivado
  para o Airflow — não há um segundo grafo para manter em sincronia.
- **[Médio impacto]** Nome e `dag_id` de DAGs de transformação tornam-se
  previsíveis a partir de órgão e escopo, fechando a lacuna que o ADR-0007
  deixou registrada.
- **[Médio impacto]** Qual modelo falhou fica visível na interface do
  Airflow, sem abrir log.

### Desvantagens

- **[Médio impacto]** O Cosmos precisa inspecionar o projeto dbt para montar
  o grafo, o que acontece no ciclo do DAG processor e custa mais que parsear
  um arquivo Python comum. O custo é mitigado por cache, mas não é zero, e
  cresce com o número de modelos.
- **[Médio impacto]** Acopla a execução da transformação a uma dependência
  de terceiro, que passa a ter que acompanhar as versões de Airflow e dbt do
  monorepo.
- **[Baixo impacto]** O `{escopo}` do nome do arquivo e o seletor dbt da DAG
  precisam ser mantidos coerentes à mão — nada impede alguém de nomear o
  arquivo por um produto e selecionar outro.

### Avaliação

Os ganhos superam os custos. O problema central da Alternativa A — retry de
projeto inteiro — é operacional e recorrente: ele se paga em toda execução
que falha, e a frequência disso cresce junto com o número de modelos. O
custo do Cosmos, ao contrário, é de parsing, é amortizado por cache e é
pago uma vez por ciclo do DAG processor, independentemente de haver falha
ou não. A dependência de terceiro é real, mas o Cosmos é a ferramenta de
integração Airflow/dbt com adoção mais ampla, e a alternativa a ela seria
manter código equivalente dentro do próprio framework.

## Consequências

- **Positivas**: os projetos dbt do monorepo passam a ser efetivamente
  executados, com observabilidade por modelo, e DAGs de transformação ganham
  nome previsível como as de ingestão já têm.
- **Negativas**: o tempo de parsing das DAGs cresce com o tamanho dos
  projetos dbt, e o framework passa a depender do Cosmos acompanhar as
  versões de Airflow e dbt adotadas.
- **Ações decorrentes**:
  - Registrar `data_transform/<orgao>/` no `dag_selector` de cada deployment
    que deva executar a transformação daquele órgão
    ([ADR-0005](./0005-selecao-de-dags-por-dag-selector-antes-do-parsing.md)).
  - Atribuir as pastas `data_transform/<orgao>/` ao time do órgão no
    `CODEOWNERS`, na mesma lógica já aplicada a `data_ingest/<orgao>/`
    (ADR-0004).
  - Estender a verificação estática de nomes de DAG — ação já pendente do
    ADR-0007 — para cobrir também o sufixo `_transform_dag`.
  - Definir, quando houver o primeiro caso concreto, o padrão para DAGs de
    **publicação**, que continua fora do escopo tanto do ADR-0007 quanto
    deste.

## Referências

- [Astronomer Cosmos — documentação](https://astronomer.github.io/astronomer-cosmos/)
- [ADR-0002 — dbt como ferramenta de transformação de dados](./0002-dbt-como-ferramenta-de-transformacao-de-dados.md)
- [ADR-0004 — Monorepo como estratégia de organização de código](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)
- [ADR-0005 — Seleção de DAGs por arquivo `dag_selector` antes do parsing](./0005-selecao-de-dags-por-dag-selector-antes-do-parsing.md)
- [ADR-0007 — Padrão de nomenclatura das pastas/arquivos de DAGs de ingestão](./0007-nomenclatura-pastas-dags-ingestao.md)
- [ADR-0008 — Padrão de uso de tags/nomenclatura no Airflow](./0008-padrao-uso-tags-nomenclatura.md)
- [ADR-0010 — Padrão de nomenclatura de schemas e tabelas bronze/silver/gold](./0010-nomenclatura-schemas-tabelas-bronze-silver-gold.md)
- [ADR-0017 — Chaves conformadas e catálogo de cruzamento entre sistemas estruturantes](./0017-chaves-conformadas-cruzamento-sistemas-estruturantes.md)
- [Estrutura de ADRs do repositório](./README.md)
