# ADR-0022: Indicadores como categoria própria de DAG, calculados em Python

- **Status**: Proposto
- **Data**: 2026-09-16
- **Autores**: -
- **Revisores**: -

## Introdução ao problema

O MIR entrega um conjunto de **indicadores de monitoramento** (I1 valor
executado, I2 concentração institucional dos executores, I3 público-alvo
racializado, I7 completude e qualidade dos dados, I9 municípios atendidos).
Eles não são um relatório nem uma dashboard: são tabelas derivadas, com
granularidade própria, que alimentam o consumo de BI — ou seja, produtos de
dados da camada Gold no vocabulário do
[ADR-0006](./0006-arquitetura-medallion.md).

O framework já tem um lugar para produzir Gold: a DAG de transformação do
órgão, que roda o projeto dbt via Cosmos
([ADR-0018](./0018-nomenclatura-execucao-dags-transformacao.md)). A regra
implícita até aqui era simples — **transformação é dbt**. Estes cinco
indicadores quebram essa premissa por um motivo concreto: a regra de negócio
deles não é expressável de forma razoável em SQL.

O que a lógica entregue pela equipe de BI faz, e que o SQL do warehouse atual
não faz bem:

- **normalização de texto Unicode** (remoção de diacríticos) seguida de
  classificação por palavra-chave, com categorias e subcategorias, para
  decidir se um instrumento tem público-alvo racializado (I3);
- **tabelas de referência que não vêm de fonte ingerida** — o total de
  municípios por UF (IBGE) usado para calcular cobertura territorial (I9), e
  o mapa de sigla institucional para UF da sede do executor (I2);
- **índices de concentração** (Herfindahl-Hirschman) calculados sobre
  participações relativas, com base de cálculo que muda conforme a fonte
  (I2);
- **varredura de completude coluna a coluna** sobre dezenas de tabelas
  heterogêneas, com o conjunto de tabelas como parâmetro (I7).

Some-se a isso uma restrição de confiança: essas regras vieram validadas pela
equipe de BI e estão cobertas por **testes de regressão contra os CSVs de
saída dos scripts originais**. Reescrevê-las em SQL significaria refazer essa
validação do zero, com o risco de divergir de números já homologados com a
área finalística.

A decisão precisa ser tomada agora porque os testes do CI validam pasta,
sufixo e tags **por categoria** de DAG
([ADR-0008](./0008-padrao-uso-tags-nomenclatura.md),
[ADR-0009](./0009-nomenclatura-pastas-arquivos-dbt.md)): sem uma categoria
que acolha esse tipo de DAG, ela só entra no repositório violando uma
convenção que o CI aplica, ou deformando o significado de uma categoria
existente. E o problema não é do MIR: qualquer órgão que precise de um
produto de dados cuja regra não cabe em SQL vai esbarrar no mesmo limite.

## Decisão

**Indicadores ganham uma categoria própria de DAG, `data_indicators/<orgao>/`,
que calcula em Python sobre modelos já materializados pelo dbt e grava o
resultado como produto de dados Gold.**

Elementos concretos:

- **Pasta e nome**: `airflow/dags/data_indicators/<orgao>/` com arquivos
  `{indicador}_{orgao}_indicator_dag.py`, e `dag_id` igual ao nome do arquivo
  sem `.py` — mesma regra das demais categorias (ADR-0008). O sufixo fixo é
  `_indicator_dag`.
- **Separação entre regra e I/O**: a regra de negócio vive em
  `airflow/helpers/indicadores/`, como funções puras (`list[dict] ->
  list[dict]`), sem tocar em banco. A DAG faz a leitura, chama a função e
  grava. É o que permite testar a metodologia por regressão, sem banco, e o
  que mantém a fronteira do
  [ADR-0011](./0011-arquitetura-agnostica-motor-processamento.md) visível:
  o conhecimento sobre motor fica na DAG, não na regra.
- **Entrada**: modelos **já materializados** pelo dbt (Silver/Gold), lidos
  pela connection do destino analítico (`postgres_dw`,
  [ADR-0021](./0021-zona-raw-com-backend-intercambiavel.md)). A DAG de
  indicador não lê a zona raw nem chama fonte externa: ela roda **depois** da
  DAG de transformação do órgão, que é quem garante o insumo. Um indicador
  pode também ler a saída de outro indicador (I2 e I9 leem o I1), para que os
  dois não divirjam sobre o universo considerado.
- **Saída**: schema `003_gld_indicadores`, na nomenclatura de produto Gold do
  [ADR-0010](./0010-nomenclatura-schemas-tabelas-bronze-silver-gold.md) —
  que já cita `003_gld_indicadores` como exemplo.
- **Estratégia de escrita**: o indicador é recalculado inteiro a cada
  execução e **substitui** a tabela (drop + insert), em vez de fazer upsert.
  Uma agregação que deixou de existir na fonte precisa desaparecer da saída,
  o que o upsert por chave não faria.
- **Fronteira de uso — a parte que evita o abuso desta categoria**: ela
  existe para a regra que **não cabe em SQL** pelos motivos da seção
  anterior. Transformação expressável em SQL continua sendo modelo dbt
  (ADR-0018); esta categoria não é uma porta de saída para quem prefere
  Python. Na dúvida, o padrão é dbt.

## Alternativas consideradas

### Alternativa A: reescrever os indicadores como modelos dbt na Gold

- Descrição: portar as regras para SQL em `gold/indicadores/`, dentro do
  projeto dbt do órgão, sem categoria nova de DAG.
- Prós: uma só forma de transformar no framework; linhagem completa no grafo
  do Cosmos; nenhuma convenção nova para aprender; o schema de saída sai de
  graça pelo macro de camada.
- Contras: joga fora a validação existente. Normalização Unicode,
  classificação por palavra-chave e as tabelas de referência (IBGE, siglas)
  viram, no melhor caso, SQL longo e difícil de revisar — no pior, `seeds` e
  expressões regulares que ninguém da área finalística consegue conferir. E
  os testes de regressão contra os CSVs da BI deixariam de valer, porque o
  artefato testado passa a ser outro. É a alternativa que entrega o mesmo
  número com a menor confiança de que ele continua o mesmo.

### Alternativa B: acomodar as DAGs em `data_transform/<orgao>/`

- Descrição: manter o cálculo em Python, mas colocar os arquivos na pasta de
  transformação já existente, afrouxando o teste que hoje exige o sufixo
  `{orgao}_transform_dag` ali.
- Prós: nenhuma categoria nova; mudança menor no repositório.
- Contras: `data_transform/` passa a significar duas coisas — "a DAG que roda
  o projeto dbt do órgão" e "qualquer DAG que transforma" —, e o teste que
  hoje protege esse significado teria que ser enfraquecido justamente para
  permitir a exceção. Perde-se a propriedade mais útil da convenção: saber o
  que uma DAG faz pela pasta em que ela está.

### Alternativa C: modelos Python do dbt

- Descrição: usar o recurso de *Python models* do dbt, mantendo a regra em
  Python mas dentro do projeto dbt.
- Prós: seria o melhor dos dois mundos — regra em Python, linhagem e
  materialização pelo dbt.
- Contras: **não é uma opção real no deployment atual**. Python models
  dependem de o adapter executar Python no motor (Snowflake, Databricks,
  BigQuery); o adapter Postgres não os suporta, e Postgres é o warehouse dos
  deployments on-premise que o ADR-0011 tomou como restrição. Adotar esta
  alternativa significaria trocar o motor, não a organização do código.

### Não fazer nada / manter status quo

O status quo é não ter onde colocar essas DAGs: elas entrariam no repositório
quebrando `make test` (pasta/sufixo/tags fora de qualquer categoria
conhecida) ou seriam mantidas fora do framework, no repositório antigo do
órgão — que é exatamente a fragmentação que o
[ADR-0003](./0003-govhub-como-framework-compartilhado-de-dados.md) e o
[ADR-0004](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md) se
propuseram a encerrar.

## Tradeoffs

### Vantagens

- **[Alto impacto]** Preserva a metodologia validada pela BI e os testes de
  regressão que a protegem: o número publicado continua sendo o número
  homologado, e qualquer mudança futura na regra falha um teste em vez de
  passar despercebida.
- **[Alto impacto]** Torna possível no framework uma classe inteira de
  produto de dados — o que depende de normalização de texto, dado de
  referência externo ou estatística não trivial — sem precisar trocar o motor
  de warehouse.
- **[Médio impacto]** A separação regra pura / I/O deixa a metodologia
  testável sem banco e legível por quem não é da engenharia de dados, que é
  quem valida o indicador.
- **[Médio impacto]** A fronteira declarada ("o que cabe em SQL fica no dbt")
  transforma em regra escrita algo que hoje é só hábito, e dá um critério
  objetivo para revisar o próximo caso.

### Desvantagens

- **[Alto impacto]** A linhagem deixa de ser completa: o grafo do Cosmos
  termina na Gold do dbt, e a dependência "indicador lê o modelo X" só existe
  no código da DAG e no horário de agendamento. Quebrar o modelo X não
  aparece como falha no grafo — aparece como indicador errado no dia
  seguinte.
- **[Médio impacto]** O encadeamento entre DAGs é por horário, não por
  dependência declarada: a DAG de transformação roda às 06:00 e os
  indicadores depois. Um atraso na transformação produz indicador calculado
  sobre dado velho, silenciosamente.
- **[Médio impacto]** Uma categoria a mais é mais superfície de convenção:
  outro arquivo de teste, outra linha no `dag_selector`, outra entrada no
  CODEOWNERS, e mais um lugar onde alguém pode colocar código que deveria
  estar no dbt.
- **[Baixo impacto]** O cálculo acontece no worker do Airflow, com todo o
  conjunto lido para memória. Nos volumes atuais (dezenas de milhares de
  linhas) isso é irrelevante; deixa de ser se um indicador passar a varrer
  uma tabela grande.

### Avaliação

Os ganhos superam os custos, mas por uma margem que depende da fronteira ser
respeitada. O argumento decisivo é o da confiança: o indicador existe para
ser usado por uma área finalística que já homologou aqueles números, e a
Alternativa A — a mais "limpa" arquiteturalmente — é justamente a que
sacrifica essa confiança. A Alternativa C seria superior se o motor a
suportasse, e é o caminho natural caso o warehouse mude no futuro.

Permanecem como **riscos ativos**: (i) a linhagem incompleta, mitigável
depois com dependência declarada entre DAGs em vez de acoplamento por
horário; e (ii) a erosão da fronteira — cada novo indicador nesta categoria
deve justificar, na revisão, por que não é um modelo dbt.

## Consequências

- **Positivas**: os indicadores do MIR passam a viver no monorepo, sob as
  mesmas regras de nomenclatura, teste e revisão das demais DAGs; o framework
  ganha um lugar declarado para produto de dados calculado em Python.
- **Negativas**: cria-se uma segunda forma de produzir Gold, com linhagem
  mais fraca que a do dbt, e uma convenção a mais para manter.
- **Ações decorrentes**:
  - Registrar a categoria no `dag_selector` do deployment que a carrega
    ([ADR-0005](./0005-selecao-de-dags-por-dag-selector-antes-do-parsing.md))
    e no `.github/CODEOWNERS`.
  - Substituir o acoplamento por horário por dependência declarada entre a
    DAG de transformação do órgão e as de indicador, quando houver uma forma
    de expressá-la que não reintroduza acoplamento entre times.
  - Documentar cada indicador com a fonte e a fórmula no próprio módulo de
    regra, já que ele não aparece no catálogo de modelos do dbt.
  - Reavaliar esta decisão se o warehouse passar a suportar Python models
    (Alternativa C).

## Referências

- [ADR-0003 — GovHub como um framework compartilhado de dados](./0003-govhub-como-framework-compartilhado-de-dados.md)
- [ADR-0006 — Arquitetura medallion (bronze/silver/gold)](./0006-arquitetura-medallion.md)
- [ADR-0010 — Padrão de nomenclatura de schemas e tabelas bronze/silver/gold](./0010-nomenclatura-schemas-tabelas-bronze-silver-gold.md)
- [ADR-0011 — Arquitetura agnóstica a motor de processamento de dados](./0011-arquitetura-agnostica-motor-processamento.md)
- [ADR-0018 — Padrão de nomenclatura e execução das DAGs de transformação](./0018-nomenclatura-execucao-dags-transformacao.md)
- [ADR-0021 — Zona raw com backend intercambiável e Bronze lendo da raw](./0021-zona-raw-com-backend-intercambiavel.md)
- [dbt — Python models (suporte por adapter)](https://docs.getdbt.com/docs/build/python-models)
- [Estrutura de ADRs do repositório](./README.md)
