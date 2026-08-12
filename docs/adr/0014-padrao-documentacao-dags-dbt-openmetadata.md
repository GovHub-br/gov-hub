# ADR-0014: Padrão de documentação de DAGs/dbt para envio ao OpenMetadata

- **Status**: Proposto
- **Data**: 2026-08-07
- **Autores**: -
- **Revisores**: -

## Introdução ao problema

O [ADR-0013](./0013-padrao-documentacao-metadados-tabelas.md) definiu que a
documentação de uma tabela vive no `schema.yml` do modelo dbt. Isso resolve
o registro do metadado, mas não a sua **descoberta**: quem procura um dado
hoje precisa saber que ele existe, em qual dos projetos do monorepo
([ADR-0004](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md))
ele mora, e abrir o repositório para ler o YAML. Para analistas de outros
órgãos, gestores e cidadãos, isso é inviável na prática.

O OpenMetadata é a ferramenta de governança adotada para essa camada de
descoberta. Conectá-la, porém, levanta uma questão que precisa ser decidida
antes da primeira ingestão de metadados, e não depois:

- **Qual é a fonte de verdade.** O OpenMetadata permite editar descrições,
  owners e tags pela sua própria interface. Se essa edição for aceita como
  prática, passam a existir duas fontes de verdade para o mesmo metadado —
  o `schema.yml` e a interface — e a cada reingestão uma delas sobrescreve
  a outra, de forma que depende de detalhes de configuração do conector.
  O resultado típico é o pior possível: perda silenciosa de documentação
  escrita à mão, e desconfiança generalizada na ferramenta.
- **Metadados de pipeline não têm dono definido.** O ADR-0013 cobre
  tabelas, mas não DAGs. Hoje uma DAG pode existir sem descrição, sem
  responsável e sem indicação do que produz — e é justamente esse metadado
  que responde à pergunta operacional mais comum sobre um dado ("por que
  essa tabela está desatualizada?").
- **Linhagem quebrada no meio.** dbt conhece a linhagem entre modelos e o
  Airflow conhece a execução das DAGs, mas nada liga a DAG de ingestão que
  produziu o insumo ao modelo que o consome. Sem essa ligação, a linhagem
  exibida começa na Bronze, escondendo a origem real do dado — a fonte
  governamental — que é a informação de maior valor para quem audita.
- **Documentação escrita para a ferramenta errada.** Se o padrão não for
  definido, cada time descobre por tentativa e erro quais campos o
  OpenMetadata aproveita, e escreve documentação que a ferramenta ignora.

Esta decisão precisa ser tomada agora porque a alternativa — deixar a
prática se formar sozinha — produz edições manuais na interface que serão
perdidas, e o custo disso não é técnico, é de confiança: uma vez que um time
perde documentação escrita à mão, ele para de documentar.

## Decisão

**Todo metadado exibido no OpenMetadata nasce no código.** O OpenMetadata é
um consumidor de metadados, nunca a sua fonte de verdade: sua interface é
tratada como somente-leitura para descrição, owner e classificação, e a
ingestão é livre para sobrescrever o que estiver lá.

### Metadados de modelos dbt

Nada novo é exigido além do ADR-0013. A ingestão do OpenMetadata consome os
artefatos gerados por `dbt docs generate` (`manifest.json` e
`catalog.json`), que já carregam `description`, `meta` e a linhagem entre
modelos. Isso implica que:

- A geração desses artefatos passa a ser etapa obrigatória do fluxo que
  precede a ingestão de metadados — um metadado só chega ao OpenMetadata
  se o projeto dbt compilar.
- `meta.classificacao` (ADR-0013) é mapeado para *tags* do OpenMetadata,
  tornando a sensibilidade um filtro de busca e um critério de política na
  ferramenta, e não apenas um campo documental.

### Metadados de DAGs

Toda DAG do monorepo declara, no próprio código:

| Campo | Obrigatório? | Conteúdo |
|---|---|---|
| `description` | Sim | O que a DAG faz, em uma frase: a fonte que lê e o que produz. |
| `tags` | Sim | Vocabulário fixo do [ADR-0008](./0008-padrao-uso-tags-nomenclatura.md) — `sistema:`, `orgao:`, `camada:`, `dominio:`. Nenhuma tag nova é criada para o OpenMetadata. |
| `owner` (em `default_args`) | Sim | Time responsável, no mesmo vocabulário de `meta.owner` do ADR-0013 e do `CODEOWNERS` (ADR-0004). Pessoa nomeada não é aceita. |
| `doc_md` | Recomendado | Detalhamento em Markdown: periodicidade esperada, dependências externas, o que fazer quando falha. Renderizado tanto no Airflow quanto no OpenMetadata. |

O `owner` de uma DAG e o `meta.owner` das tabelas que ela alimenta devem
coincidir: divergência entre os dois significa que a fronteira de
responsabilidade está mal definida, não que existem dois donos.

### Linhagem de ponta a ponta

A ligação entre a DAG de ingestão e os modelos dbt é declarada explicitamente
por meio dos *datasets* do Airflow: a DAG de ingestão declara como saída o
conjunto de dados que produz na landing zone
([ADR-0012](./0012-ingestao-object-storage-vs-database.md)), e a DAG de
promoção o declara como entrada. Assim a linhagem exibida vai da fonte
governamental até a camada Gold, sem lacuna entre ingestão e transformação.

### Enforcement

Como no ADR-0013, a exigência é verificada no CI: uma DAG sem `description`,
sem `owner` ou com tags fora do vocabulário do ADR-0008 reprova o build. A
verificação é feita por análise estática do arquivo, sem executar a DAG.

## Alternativas consideradas

### Alternativa A: OpenMetadata como fonte de verdade dos metadados

- Descrição: a documentação é escrita e mantida na interface do
  OpenMetadata, e o repositório carrega apenas o mínimo técnico.
- Prós: interface amigável para pessoas não técnicas, que são boa parte de
  quem conhece o significado de negócio do dado; não adiciona fricção a
  PRs; permite documentar ativos que não vêm de dbt.
- Contras: contradiz frontalmente o ADR-0013, cuja principal vantagem é que
  documentação e modelo não divergem porque vivem no mesmo PR. Também tira
  a classificação de sensibilidade do alcance do CI, onde ela precisa estar
  para bloquear publicação indevida. Por fim, cria dependência operacional:
  perder a instância do OpenMetadata passaria a significar perder a
  documentação.

### Alternativa B: Fonte de verdade dupla, com reconciliação

- Descrição: aceitar edição nos dois lados e reconciliar periodicamente,
  propagando as edições da interface de volta para o `schema.yml`.
- Prós: combina a ergonomia da interface com o versionamento do código;
  não bloqueia quem não escreve YAML.
- Contras: exige construir e manter a reconciliação — incluindo resolução
  de conflito quando os dois lados mudam entre execuções — para um problema
  que a Alternativa "somente código" simplesmente não tem. Enquanto a
  reconciliação não for perfeita, o comportamento observado pelos times é
  perda intermitente de edição, que é justamente o cenário de erosão de
  confiança que motiva esta decisão.

### Alternativa C: Sem catálogo — a documentação no repositório basta

- Descrição: manter o ADR-0013 e não adotar ferramenta de descoberta.
- Prós: nenhum componente novo a operar; fonte de verdade trivialmente
  única.
- Contras: mantém a descoberta restrita a quem sabe navegar no monorepo,
  excluindo exatamente o público que mais se beneficiaria — analistas de
  outros órgãos, gestores e sociedade civil. O metadado existe, mas não
  cumpre a função de tornar o dado encontrável.

### Não fazer nada / manter status quo

- Descrição: conectar o OpenMetadata sem definir fonte de verdade nem
  exigência de metadados em DAGs.
- Consequência: edições manuais na interface convivem com ingestões
  automáticas, e a documentação escrita à mão é perdida em algum momento
  imprevisível — com o efeito colateral, difícil de reverter, de os times
  deixarem de documentar.

## Tradeoffs

### Vantagens

- **[Alto impacto]** Fonte de verdade única e inequívoca: não existe cenário
  em que uma reingestão apague documentação legítima, porque toda
  documentação legítima veio do código.
- **[Alto impacto]** A linhagem passa a ir da fonte governamental até a
  camada Gold, tornando auditável a pergunta "de onde veio este número?" —
  valor central em contexto de dados públicos.
- **[Médio impacto]** DAGs ganham responsável e descrição obrigatórios,
  dando um destinatário determinístico para incidentes operacionais.
- **[Médio impacto]** A classificação de sensibilidade do ADR-0013 vira tag
  navegável e critério de política no catálogo, ampliando o alcance de uma
  informação que já era exigida.
- **[Médio impacto]** Reaproveita integralmente o vocabulário de tags do
  ADR-0008, sem criar um segundo esquema de marcação só para a ferramenta.
- **[Baixo impacto]** Perder a instância do OpenMetadata deixa de implicar
  perda de metadado: basta reingerir a partir do repositório.

### Desvantagens

- **[Alto impacto]** Exclui de fato quem não contribui via PR. Pessoas que
  conhecem o significado de negócio do dado, mas não escrevem YAML nem
  abrem pull request, ficam sem caminho direto para documentar — e o
  conhecimento delas depende de um intermediário técnico.
- **[Médio impacto]** Acopla a atualização do catálogo ao ciclo de
  release: corrigir um erro de descrição exige PR, revisão e reingestão, em
  vez de dois cliques na interface.
- **[Médio impacto]** Adiciona à cadeia de CI/CD uma etapa de geração de
  artefatos dbt e ingestão de metadados, com mais um ponto de falha entre
  o merge e o catálogo atualizado.
- **[Médio impacto]** Declarar linhagem por datasets exige disciplina nas
  duas DAGs de uma fonte; se a de promoção não declarar a entrada
  correspondente, a linhagem quebra silenciosamente — sem erro, apenas com
  um grafo incompleto.
- **[Baixo impacto]** Ativos que não vêm de dbt nem do Airflow ficam fora do
  padrão e precisam de tratamento próprio.

### Avaliação

Os ganhos superam os custos, mas a desvantagem principal é real e não deve
ser minimizada: exigir PR para documentar restringe quem pode documentar,
e o conhecimento de negócio sobre dados públicos frequentemente está com
quem não contribui via Git. A decisão aceita esse custo porque a
alternativa — permitir edição na interface — não resolve o problema de forma
estável: ela troca uma barreira de participação por perda silenciosa de
dados, que corrói a confiança na ferramenta de modo muito mais difícil de
reverter. A mitigação prevista é de processo, não de arquitetura: oferecer
um caminho de baixa fricção (issue com o texto proposto, convertida em PR
por quem mantém o domínio) para quem não escreve YAML.

Permanecem como **riscos ativos**: (i) a quebra silenciosa de linhagem
quando uma das DAGs do par não declara seu dataset, que só é perceptível
inspecionando o grafo; e (ii) a defasagem entre merge e catálogo, que faz o
OpenMetadata exibir estado antigo sem sinalizar que está defasado.

## Consequências

- **Positivas**: o catálogo passa a refletir exatamente o que está no
  repositório, sem ambiguidade de origem; a linhagem cobre da fonte
  governamental ao produto de dados; DAGs passam a ter responsável e
  descrição obrigatórios; a instância do OpenMetadata torna-se descartável e
  reconstruível.
- **Negativas**: documentar passa a exigir PR, excluindo contribuidores não
  técnicos do caminho direto; a atualização do catálogo fica acoplada ao
  ciclo de CI/CD; a cadeia de publicação de metadados ganha etapas e pontos
  de falha.
- **Ações decorrentes**:
  - Configurar a ingestão do OpenMetadata a partir de `manifest.json` e
    `catalog.json` do dbt e da API do Airflow, com a interface tratada como
    somente-leitura para descrição, owner e classificação.
  - Adicionar ao CI a verificação estática de `description`, `owner` e
    vocabulário de tags nas DAGs, com mensagem que aponte o arquivo e o
    campo faltante.
  - Definir e documentar a convenção de datasets que liga DAG de ingestão e
    DAG de promoção, e verificar no CI que toda saída declarada tem uma
    entrada correspondente.
  - Estabelecer o caminho de contribuição para quem não abre PR (issue com
    texto proposto, adotada por quem mantém o domínio), para que a barreira
    de participação não vire ausência de documentação.
  - Documentar explicitamente, na página inicial da instância, que edições
    feitas na interface serão sobrescritas — para que a regra seja
    descoberta antes do primeiro trabalho perdido, e não depois.

## Referências

- [ADR-0004 — Monorepo como estratégia de organização de código](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)
- [ADR-0008 — Padrão de uso de tags/nomenclatura no Airflow](./0008-padrao-uso-tags-nomenclatura.md)
- [ADR-0012 — Ingestão em object storage em vez de banco diretamente](./0012-ingestao-object-storage-vs-database.md)
- [ADR-0013 — Padrão de documentação de metadados de tabelas](./0013-padrao-documentacao-metadados-tabelas.md)
- [OpenMetadata — ingestão de metadados do dbt](https://docs.open-metadata.org/connectors/ingestion/workflows/dbt)
- [OpenMetadata — conector do Apache Airflow](https://docs.open-metadata.org/connectors/pipeline/airflow)
- [dbt — artefatos `manifest.json` e `catalog.json`](https://docs.getdbt.com/reference/artifacts/dbt-artifacts)
- [Apache Airflow — data-aware scheduling (datasets)](https://airflow.apache.org/docs/apache-airflow/2.8.1/authoring-and-scheduling/datasets.html)
- [Estrutura de ADRs do repositório](./README.md)
