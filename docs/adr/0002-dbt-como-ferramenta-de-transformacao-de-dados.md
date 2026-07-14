# ADR-0002: dbt como ferramenta de transformação de dados

- **Status**: Proposto
- **Data**: 2026-07-14
- **Autores**: João Egewarth
- **Revisores**: -

## Introdução ao problema

Uma vez que dados brutos são ingeridos (e orquestrados via
[ADR-0001](./0001-airflow-como-orquestrador-de-fluxos-de-dados.md)), o
`data-framework` precisa de uma forma padronizada de transformá-los —
limpeza, modelagem, agregação e disponibilização de camadas analíticas
(bronze/silver/gold) — antes de publicá-los. Hoje essa etapa, quando existe,
é resolvida por scripts SQL soltos ou lógica de transformação embutida em
tarefas de orquestração, sem versionamento, teste ou documentação
padronizados. Isso gera problemas semelhantes aos já identificados no
[ADR-0003](./0003-govhub-como-framework-compartilhado-de-dados.md):

- **Falta de testabilidade**: transformações em SQL solto não têm testes de
  qualidade de dados associados (ex.: unicidade, not-null, integridade
  referencial), então erros de modelagem só são percebidos depois de
  publicados.
- **Falta de versionamento e revisão**: sem uma ferramenta dedicada, lógica
  de transformação frequentemente vive fora do controle de versão do
  projeto, ou não segue um padrão de revisão de código.
- **Falta de documentação e linhagem**: não há um jeito padronizado de
  documentar o que cada transformação faz nem de visualizar a linhagem entre
  modelos (de onde vem cada tabela, o que depende dela).
- **Banco de dados predominante nos projetos consumidores**: a maioria dos
  projetos de dados públicos herdados por este framework usa PostgreSQL como
  banco analítico/operacional, seja por já ser amplamente adotado em órgãos
  públicos, seja por restrição de infraestrutura disponível.
- **Restrição orçamentária e de licenciamento**: assim como no caso do
  orquestrador, contratos públicos não podem depender de ferramentas
  proprietárias que gerem custo de licença recorrente ou risco de
  aprisionamento a fornecedor.
- **Continuidade entre equipes**: pela mesma razão do ADR-0001, uma
  ferramenta com adoção ampla e comunidade estável reduz o risco de a
  camada de transformação ficar sem manutenção quando há troca de equipe.

Essa decisão precisa ser tomada agora porque a camada de transformação é
consumida diretamente por qualquer projeto que herdar o `data-framework`, e
molda como modelos de dados são escritos, testados e documentados em todos
os projetos consumidores.

## Decisão

O `data-framework` adota o **dbt (data build tool)** como ferramenta padrão
de transformação de dados, com foco em transformações executadas sobre
**PostgreSQL**.

Isso implica que:

- Toda lógica de transformação (bronze → silver → gold) definida pelo
  framework — e por projetos que o herdam — é expressa como modelos dbt
  (SQL versionado, testável e documentável), e não como scripts soltos.
- Convenções de estrutura de projeto dbt (organização de modelos, testes
  genéricos, macros e documentação) são centralizadas no framework, para que
  projetos consumidores não precisem redefinir padrões básicos de
  transformação.
- A escolha prioriza explicitamente três fatores: adoção já existente no
  poder público brasileiro, natureza open source (dbt Core, sem custo de
  licença nem vendor lock-in) e boa aderência ao PostgreSQL, banco
  predominante nos projetos consumidores — em detrimento de ferramentas
  eventualmente mais robustas para outros bancos (ex.: warehouses colunares
  na nuvem) mas menos alinhadas à realidade de infraestrutura desses
  projetos.
- A integração entre dbt e Airflow (execução de `dbt run`/`dbt test` como
  tarefas de DAGs) é tratada como consequência natural das decisões dos
  ADR-0001 e ADR-0002, e detalhada em documentação técnica subsequente, não
  neste ADR.

## Alternativas consideradas

### Alternativa A: SQL solto orquestrado manualmente (status quo / não fazer nada)

- Descrição: manter transformações como scripts SQL avulsos, disparados por
  tarefas genéricas de orquestração, sem ferramenta dedicada de
  transformação.
- Prós: zero custo de adoção, zero dependência nova, funciona para casos
  triviais de transformação.
- Contras: não há testes de qualidade de dados, versionamento estruturado,
  documentação nem visualização de linhagem. Cada projeto reimplementaria (de
  forma inconsistente) convenções básicas de modelagem — reproduzindo o
  problema de duplicação e falta de padronização descrito no
  [ADR-0003](./0003-govhub-como-framework-compartilhado-de-dados.md).

### Alternativa B: Spark SQL / PySpark para transformação

- Descrição: usar Spark (via PySpark ou Spark SQL) como motor de
  transformação, processando dados fora do banco antes de carregá-los.
- Prós: escala melhor para volumes muito grandes de dados e processamento
  distribuído; útil quando a transformação não cabe confortavelmente em um
  banco relacional.
- Contras: exige infraestrutura de cluster (mesmo que local/single-node),
  elevando a complexidade operacional para projetos cujo volume de dados não
  justifica processamento distribuído. Menos aderente a um cenário onde o
  banco analítico já é PostgreSQL — introduz uma camada de processamento
  adicional em vez de aproveitar o motor SQL já disponível.

### Alternativa C: Ferramenta proprietária de ETL/transformação (ex.: plataformas low-code comerciais)

- Descrição: adotar uma ferramenta comercial de transformação de dados com
  interface visual e suporte pago.
- Prós: menor curva de aprendizado inicial para usuários não técnicos;
  suporte comercial disponível.
- Contras: custo de licença recorrente, incompatível com a realidade
  orçamentária de contratos públicos; risco de vendor lock-in; lógica de
  transformação frequentemente presa a um formato proprietário, dificultando
  versionamento em Git e revisão de código como qualquer outro artefato de
  software.

### dbt — decisão proposta

- Descrição: ferramenta open source de transformação de dados que aplica
  práticas de engenharia de software (versionamento, testes, documentação,
  modularização via `ref()`) a transformações SQL, executadas diretamente no
  banco de dados de destino.
- Por que foi escolhida: é a única alternativa que atende simultaneamente aos
  três critérios levantados na introdução — ampla adoção no poder público,
  natureza open source e boa aderência ao PostgreSQL — sem introduzir uma
  camada de infraestrutura adicional (como um cluster Spark) desnecessária
  para o volume de dados típico dos projetos consumidores.

## Tradeoffs

| Dimensão | Ganho | Custo/Risco |
|---|---|---|
| Adoção e mão de obra | Ferramenta já conhecida por servidores/contratados de outros projetos públicos e amplamente documentada, reduzindo custo de treinamento | Times sem experiência prévia em dbt precisam aprender convenções próprias (ex.: `ref()`, `source()`, camadas de modelos) |
| Custo e licenciamento | dbt Core é open source, sem custo de licença nem vendor lock-in — relevante para justificativa de contratação pública | dbt Cloud (versão gerenciada com UI, scheduler próprio) é paga; o framework assume o uso de dbt Core, deixando orquestração e CI por conta do próprio time |
| Aderência ao PostgreSQL | Transformações executam diretamente no banco já usado pelos projetos, sem infraestrutura adicional de processamento | Para volumes muito grandes de dados, transformação dentro do PostgreSQL pode não escalar tão bem quanto motores de processamento distribuído |
| Testabilidade e qualidade de dados | Testes genéricos e customizados (unicidade, not-null, relacionamentos) tornam-se parte do próprio pipeline de transformação | Exige disciplina do time para de fato escrever e manter testes — a ferramenta viabiliza, mas não garante qualidade sozinha |
| Documentação e linhagem | Documentação e grafo de linhagem gerados a partir do próprio projeto dbt, sem ferramenta externa | Documentação gerada (`dbt docs`) precisa de hospedagem/publicação própria para ser útil a times não técnicos |

## Consequências

- **Positivas**: o framework passa a oferecer uma camada de transformação
  testável, documentável e versionada como qualquer outro código, reduzindo o
  risco de lógica de negócio "escondida" em scripts soltos. Projetos
  consumidores ganham testes de qualidade de dados e documentação de
  linhagem sem precisar construir isso por conta própria.
- **Negativas**: projetos consumidores passam a depender de convenções
  próprias do dbt (estrutura de pastas, `ref()`/`source()`, materializações),
  exigindo curva de aprendizado para times sem experiência prévia. Para
  cenários de volume de dados muito acima do que o PostgreSQL suporta
  confortavelmente, a escolha por dbt Core sobre um motor de processamento
  distribuído pode precisar ser revisitada em ADR futuro.
- **Ações decorrentes**:
  - Definir, em ADR ou documento técnico subsequente, as convenções
    concretas de estrutura de projeto dbt (camadas bronze/silver/gold,
    nomenclatura de modelos, padrão de testes) do framework.
  - Documentar a integração entre dbt e Airflow (execução de modelos como
    tarefas de DAG), mencionada na seção de Decisão.
  - Avaliar, em decisão futura, critérios objetivos (ex.: volume de dados)
    que justifiquem a adoção de um motor de processamento distribuído para
    projetos consumidores específicos com necessidades atípicas.

## Referências

- [dbt — documentação oficial](https://docs.getdbt.com/)
- [ADR-0001 — Apache Airflow como orquestrador de fluxos de dados](./0001-airflow-como-orquestrador-de-fluxos-de-dados.md)
- [ADR-0003 — GovHub como framework compartilhado de dados](./0003-govhub-como-framework-compartilhado-de-dados.md)
- [Estrutura de ADRs do repositório](./README.md)
