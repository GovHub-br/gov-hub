# ADR-0019: Publicação de produtos de dados — dashboards versionadas e relatórios periódicos

- **Status**: Proposto
- **Data**: 2026-08-24
- **Autores**: -
- **Revisores**: -

## Introdução ao problema

O framework já sabe ingerir ([ADR-0007](./0007-nomenclatura-pastas-dags-ingestao.md)),
modelar ([ADR-0017](./0017-chaves-conformadas-cruzamento-sistemas-estruturantes.md))
e transformar ([ADR-0018](./0018-nomenclatura-execucao-dags-transformacao.md)) dado
de sistemas estruturantes. O que ele não sabe fazer é a última etapa: **entregar
o resultado a quem não abre o banco**. O ADR-0018 deixou isso registrado
explicitamente entre suas ações decorrentes — o padrão para DAGs de
*publicação* ficaria para quando houvesse o primeiro caso concreto. Ele
chegou: mais de um instituto precisa consumir os mesmos produtos de dados, cada
um enxergando o seu recorte.

Sem uma decisão, a publicação acontece do jeito que é mais fácil, e o jeito
mais fácil tem quatro problemas conhecidos:

- **A dashboard existe só dentro da ferramenta de BI.** Ela é construída
  clicando em produção, não passa por revisão, não tem histórico e não existe
  em nenhum outro ambiente. Quando alguém a altera, não há diff; quando o
  servidor é reconstruído, não há de onde restaurá-la. É o oposto do que o
  [ADR-0003](./0003-govhub-como-framework-compartilhado-de-dados.md) propõe ao
  tratar o framework como base compartilhada e herdável.
- **Cada instituto vira uma cópia.** Como não há mecanismo de recorte, atender
  um segundo órgão significa duplicar a dashboard e o relatório trocando o
  filtro — e a partir daí manter N cópias que divergem na primeira correção.
- **Relatório vira script pessoal.** A entrega periódica de um extrato por
  e-mail é a demanda mais comum dos órgãos e a que mais frequentemente nasce
  fora do repositório, em um script na máquina de alguém, com a lista de
  destinatários no meio do código.
- **Ninguém sabe o que está publicado.** Sem um lugar que declare o que é
  publicado e para quem, a pergunta "esta coluna está exposta em alguma
  dashboard?" só tem resposta abrindo a ferramenta e olhando — o que torna
  impossível verificar qualquer coisa no CI, inclusive sensibilidade de dado
  ([ADR-0013](./0013-padrao-documentacao-metadados-tabelas.md)).

A decisão precisa ser tomada agora porque a publicação é o ponto em que dado
pessoal efetivamente alcança pessoas. Enquanto o dado estava só no warehouse,
o controle de acesso era o do banco; a partir do momento em que existe uma
dashboard, o alcance passa a ser definido por quem montou a dashboard.

## Decisão

**Publicar é uma etapa versionada do pipeline, não um trabalho manual na
ferramenta de BI.** O Superset é a ferramenta de consumo; o que ele mostra é
importado do repositório por uma DAG, e o que pode ser publicado está declarado
em um catálogo verificado no CI.

### Pasta e nome das DAGs

Seguindo a simetria do ADR-0018 — a pasta diz a ação, a subpasta diz de quem é
o código:

```text
airflow/dags/data_publish/<orgao>/{orgao}_publish_dag.py           # ativos de BI do órgão
airflow/dags/data_publish/<orgao>/{escopo}_{orgao}_publish_dag.py  # um recorte deles
airflow/dags/data_report/<orgao>/{relatorio}_{orgao}_report_dag.py # um relatório periódico
```

- `data_publish/` publica **ativos de BI**: dashboards, datasets e conexões.
  `data_report/` entrega **arquivos** a pessoas. São ações diferentes, com
  falhas e cadências diferentes, e por isso pastas diferentes.
- A pasta imediata é sempre de órgão, como na transformação: quem publica é o
  órgão dono do produto de dados, ainda que os modelos sejam compartilhados
  ([ADR-0004](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)).
- Sufixos fixos `_publish_dag` e `_report_dag`, espelhando `_ingest_dag` e
  `_transform_dag`. `dag_id` replica o nome do arquivo.
- Tags conforme o [ADR-0008](./0008-padrao-uso-tags-nomenclatura.md).

### Dashboards: bundle exportado e versionado

Uma dashboard é construída na interface do Superset — é onde esse trabalho é
produtivo — e depois **exportada** como bundle de YAML e versionada em
`airflow/dags/superset/<orgao>/<bundle>/`. A DAG de publicação importa o bundle
pela API de ativos do Superset, de forma idempetente: rodar duas vezes leva ao
mesmo estado.

- O bundle fica sob `airflow/dags/` porque precisa estar ao alcance do worker
  que roda a DAG, pela mesma razão que os projetos dbt ficam lá (ADR-0018).
- A conexão do warehouse declarada no bundle é um **placeholder**: a DAG a
  substitui, em memória, pela URI do ambiente, e a senha viaja fora do bundle.
  Nenhuma credencial é versionada.
- O dataset publicado é **virtual**, com as colunas listadas uma a uma no SQL,
  em vez de `select *`. Uma coluna nova no modelo não chega à dashboard
  sozinha — e é essa lista explícita que a validação consegue conferir.

### Relatórios: uma consulta, uma entrega por consumidor

Um relatório é declarado no catálogo e implementado com a factory
`relatorio_dag_factory`. A consulta é escrita uma única vez, na DAG do órgão
publicador, e contém a marca `{recorte}`; a factory executa essa consulta uma
vez por órgão consumidor, substituindo a marca pelo filtro daquele órgão. A
ausência da marca é erro de construção da DAG, não um detalhe de estilo: sem
ela, todo instituto receberia as linhas de todos os outros.

Cada entrega é gerada como tarefa mapeada independente — o e-mail que falha
para um órgão não refaz o relatório dos demais — e vai para os destinos
declarados: a landing zone (`{bucket}/relatorios/{orgao}/{relatorio}/…`), o
e-mail, ou ambos. **A lista de destinatários não é versionada**: endereço de
pessoa é dado pessoal (ADR-0013) e vive em uma Variable do Airflow declarada no
catálogo.

### O catálogo de publicação

`catalogo/publicacao/<orgao>.yml` declara o que o órgão publica — datasets,
dashboards, relatórios — e quem consome cada coisa. Ele é a fonte de verdade do
que **pode** ser publicado; os bundles são o que **é** publicado. O
`make publicacao-validar` compara um com o outro e roda dentro do `make lint`:
bundle que expõe dataset não catalogado, dashboard que aponta para um bundle
inexistente, gráfico que lê dataset que não está no bundle e DAG de relatório
que ninguém declarou reprovam o build.

O nível de acesso de cada consumidor e o recorte de linhas aplicado a ele são
derivados desse mesmo catálogo, em um plano gerado (`make publicacao-sync`) que
a DAG de publicação executa. O critério que rege esses níveis é objeto de
decisão própria, registrada em ADR separado.

## Alternativas consideradas

### Alternativa A: dashboard vive só no Superset

- Descrição: cada órgão constrói suas dashboards na interface do ambiente de
  produção; nada é versionado.
- Prós: nenhum passo adicional entre construir e publicar; é o caminho natural
  de quem usa a ferramenta.
- Contras: a dashboard deixa de ser artefato revisável — sem PR, sem
  CODEOWNERS, sem histórico e sem como reproduzir o ambiente. Não há como
  verificar no CI o que está exposto, porque o que está exposto não está no
  repositório. E "atender o próximo instituto" vira copiar e colar.

### Alternativa B: dashboard gerada a partir do catálogo

- Descrição: declarar a dashboard em YAML próprio e gerar o JSON do Superset,
  no mesmo espírito do `make modelo` (ADR-0017).
- Prós: coerente com o resto do framework; a dashboard seria derivada de uma
  declaração revisável, e não haveria formato de terceiro no repositório.
- Contras: obriga a reimplementar, em um gerador, o vocabulário visual inteiro
  da ferramenta — tipos de gráfico, layout, filtros — e a acompanhar a evolução
  dele. Na prática limitaria o que dá para desenhar a um subconjunto pobre, e
  empurraria os times de volta para a interface. Modelagem é declarativa por
  natureza; layout de dashboard não é.

### Alternativa C: export/import manual, sem DAG

- Descrição: versionar o bundle exportado, mas importar à mão em cada ambiente.
- Prós: mantém o ganho de versionamento sem depender da API do Superset.
- Contras: publicar volta a ser um procedimento humano documentado — que é
  esquecido, feito parcialmente, ou feito por alguém que não tinha o contexto.
  E a aplicação dos níveis de acesso, que envolve dezenas de cliques por
  consumidor, é exatamente o tipo de tarefa que se degrada quando é manual.

### Não fazer nada / manter status quo

Manter a publicação fora do repositório significa que o único ponto do pipeline
onde dado pessoal chega a pessoas é também o único que não tem revisão,
histórico nem verificação automática. Não é aceitável para um framework que
trata dado sob LGPD.

## Tradeoffs

### Vantagens

- **[Alto impacto]** A dashboard passa a ser artefato de repositório: revisada
  em PR, atribuída no CODEOWNERS, reproduzível em qualquer ambiente e
  restaurável depois de uma perda.
- **[Alto impacto]** Um relatório atende N institutos com uma única consulta, e
  o recorte de cada um vem do catálogo — não há cópia por órgão para manter em
  sincronia.
- **[Alto impacto]** O que está exposto passa a ser verificável no CI: as
  colunas do dataset publicado estão no repositório, e podem ser comparadas com
  a classificação declarada no modelo dbt (ADR-0013).
- **[Médio impacto]** Publicação idempotente: reexecutar a DAG converge para o
  mesmo estado, o que torna seguro republicar após qualquer incidente.
- **[Médio impacto]** Nome e `dag_id` de DAGs de publicação e de relatório
  tornam-se previsíveis, fechando a lacuna registrada no ADR-0018.

### Desvantagens

- **[Alto impacto]** O bundle é gerado por outra ferramenta: o diff é ruidoso,
  o merge conflita com facilidade e ninguém revisa a dashboard lendo YAML — a
  revisão real continua sendo abrir a dashboard e olhar.
- **[Médio impacto]** Toda alteração feita na interface precisa ser reexportada
  e commitada à mão. Quem esquecer terá a alteração desfeita na próxima
  publicação — comportamento correto, mas surpreendente na primeira vez.
- **[Médio impacto]** O framework passa a depender da API do Superset e do
  formato de export dele, que mudam entre versões maiores.
- **[Baixo impacto]** O SQL do dataset virtual precisa ser mantido coerente com
  o modelo dbt à mão; nada impede que uma coluna renomeada no modelo quebre a
  dashboard até a próxima execução.

### Avaliação

Os ganhos superam os custos. O custo maior — diff ruim de YAML exportado — é
real, mas incide sobre a *revisão* de uma mudança visual, que já não seria feita
lendo código em nenhum cenário; o ganho incide sobre reprodutibilidade,
histórico e verificação de exposição de dado, que não têm substituto. A
alternativa que evitaria o YAML de terceiro (gerar a dashboard) troca esse
custo por um muito maior: manter um gerador que persegue a evolução da
ferramenta.

Permanece como risco ativo a divergência silenciosa entre o que está na
interface e o que está versionado — mitigada apenas parcialmente pela
publicação idempotente, que desfaz a alteração não exportada, mas só na próxima
execução.

## Consequências

- **Positivas**: o pipeline passa a ter uma etapa final versionada; institutos
  são atendidos por recorte em vez de por cópia; e o que está exposto vira
  informação disponível ao CI.
- **Negativas**: o repositório passa a conter YAML de export de terceiro, e o
  fluxo de trabalho de quem constrói dashboards ganha um passo (exportar e
  commitar).
- **Ações decorrentes**:
  - Registrar `data_publish/<orgao>/` e `data_report/<orgao>/` no `dag_selector`
    de cada deployment que deva publicar
    ([ADR-0005](./0005-selecao-de-dags-por-dag-selector-antes-do-parsing.md)).
  - Atribuir as pastas `data_publish/<orgao>/`, `data_report/<orgao>/` e
    `superset/<orgao>/` ao time do órgão no `CODEOWNERS` (ADR-0004).
  - Criar, em cada deployment, as connections `superset_default` e `postgres_dw`
    (a Gold vive no warehouse, não no banco de apoio do Airflow) e as Variables
    de SMTP e de destinatários usadas pelos relatórios.
  - Manter uma imagem própria do Superset: a oficial não traz driver de banco
    algum, e sem ele o import do bundle falha na criação da conexão — com uma
    mensagem que não diz que o driver é a causa.
  - Ignorar `dags/dbt/` no `.airflowignore`: o `dbt deps` instala os pacotes
    locais do monorepo como symlink apontando de volta para dentro de `dags/`, e
    o processador aborta a varredura inteira ao reencontrar o mesmo diretório.
  - Estender a verificação estática de nomes de DAG — pendência do ADR-0007 e do
    ADR-0018 — para cobrir também `_publish_dag` e `_report_dag`.
  - Documentar o fluxo de reexportação do bundle no guia de contribuição, já que
    ele é o passo que depende de disciplina humana.

## Referências

- [Superset — Importing and Exporting Assets](https://superset.apache.org/docs/using-superset/importing-and-exporting-assets/)
- [ADR-0003 — GovHub como um framework compartilhado de dados](./0003-govhub-como-framework-compartilhado-de-dados.md)
- [ADR-0004 — Monorepo como estratégia de organização de código](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)
- [ADR-0006 — Arquitetura medallion (bronze/silver/gold)](./0006-arquitetura-medallion.md)
- [ADR-0013 — Padrão de documentação de metadados de tabelas](./0013-padrao-documentacao-metadados-tabelas.md)
- [ADR-0018 — Padrão de nomenclatura e execução das DAGs de transformação](./0018-nomenclatura-execucao-dags-transformacao.md)
