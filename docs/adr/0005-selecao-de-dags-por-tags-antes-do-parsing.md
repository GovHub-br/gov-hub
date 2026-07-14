# ADR-0005: Seleção de DAGs por tags antes do parsing

- **Status**: Proposto
- **Data**: 2026-07-14
- **Autores**: Matheus Lacerda
- **Revisores**: -

## Introdução ao problema

O `data-framework` distribui um conjunto compartilhado de DAGs do Apache
Airflow para múltiplos projetos consumidores. Cada cliente ou projeto precisa
habilitar apenas os fluxos que fazem parte do seu escopo, sem manter um fork do
framework nem organizar as DAGs em pastas específicas por cliente.

Carregar todas as DAGs e apenas pausá-las depois não resolve completamente o
problema:

- Todos os arquivos continuam sendo importados pelo DAG Processor, consumindo
  CPU e memória mesmo quando suas DAGs não serão usadas naquele deployment.
- Dependências ausentes ou erros de importação de uma DAG não selecionada ainda
  podem afetar o parsing do ambiente do cliente.
- A interface do Airflow fica poluída com DAGs que não pertencem ao projeto.
- A composição do projeto fica implícita no estado do banco de metadados
  (pausado/despausado), em vez de declarada na configuração do deployment.

As tags nativas do objeto `DAG` são úteis para busca e organização na interface,
mas não podem, sozinhas, evitar o custo de importação. O Airflow precisa executar
o arquivo Python para construir o objeto e então conhecer `dag.tags`. Pela mesma
razão, uma `dag_policy` pode rejeitar ou pular uma DAG com base nas tags reais,
mas é aplicada somente depois que o arquivo e a DAG já foram carregados.

Desde o Airflow 2.6, a configuração
`AIRFLOW__CORE__MIGHT_CONTAIN_DAG_CALLABLE` permite substituir a heurística de
descoberta por um callable que decide se cada arquivo Python deve ser parseado.
Essa decisão precisa ser tomada agora para que a seleção de DAGs faça parte do
contrato do framework antes da criação de muitos projetos consumidores.

## Decisão

O `data-framework` adotará um **custom DAG discovery callable** que seleciona
arquivos de DAG por tags estáticas antes da importação, configurado por
`AIRFLOW__CORE__MIGHT_CONTAIN_DAG_CALLABLE`.

Cada arquivo de DAG selecionável declara, no nível superior do módulo, uma
constante literal chamada `DAG_TAGS`:

```python
DAG_TAGS = {"ipea", "bronze", "api"}

with DAG(
    dag_id="ipea_deputados_bronze",
    ...,
    tags=sorted(DAG_TAGS),
) as dag:
    ...
```

A mesma constante alimenta o filtro de descoberta e o atributo `tags` do
objeto `DAG`, evitando duas fontes de verdade.

O deployment informa as tags de projeto habilitadas por meio de uma variável
de ambiente própria do framework:

```text
AIRFLOW_ENABLED_DAG_TAGS=ipea,mir
```

O contrato de seleção será:

- As tags são normalizadas removendo espaços e convertendo para minúsculas.
- A correspondência usa semântica **OR**: o arquivo é selecionado quando pelo
  menos uma `DAG_TAGS` coincide com uma tag habilitada.
- O valor explícito `*` habilita todos os arquivos que passam pela heurística
  padrão do Airflow.
- Variável ausente ou vazia mantém o comportamento retrocompatível de carregar
  todos os arquivos, equivalente a `*`. Deployments de clientes devem definir
  uma allowlist explícita e ter essa condição validada no manifesto/Helm.
- `AIRFLOW_INCLUDE_UNTAGGED_DAGS=false` é o padrão para deployments de
  clientes. Com uma allowlist explícita e sem wildcard, arquivos sem
  `DAG_TAGS` só são incluídos quando essa opção for habilitada.
- Se o código tiver erro de sintaxe, o callable retorna `True`, permitindo que
  o Airflow importe o arquivo e registre o erro em vez de ocultá-lo.
- Uma declaração `DAG_TAGS` não literal é inválida, deve falhar nos testes do
  framework e não será considerada pelo filtro.

O callable primeiro executa
`might_contain_dag_via_default_heuristic`, preservando a otimização nativa que
busca os termos `airflow` e `dag`. Somente arquivos aprovados pela heurística
padrão têm seu código lido e analisado com `ast.parse` e `ast.literal_eval`.
Nenhum arquivo de DAG é importado ou executado pelo filtro.

A configuração de referência do componente responsável pelo parsing será:

```yaml
env:
  - name: AIRFLOW__CORE__MIGHT_CONTAIN_DAG_CALLABLE
    value: "dag_discovery.might_contain_selected_dag"
  - name: AIRFLOW_ENABLED_DAG_TAGS
    value: "ipea,mir"
  - name: AIRFLOW_INCLUDE_UNTAGGED_DAGS
    value: "false"
```

O módulo `dag_discovery` deve estar no `PYTHONPATH` de todo componente que faz
descoberta/parsing de DAGs. Em Airflow 3 isso inclui o DAG Processor; em
arquiteturas anteriores essa responsabilidade normalmente está associada ao
scheduler.

### Granularidade e convenções obrigatórias

O callable seleciona **arquivos Python**, não objetos `DAG`. Por isso:

- A convenção preferencial é uma DAG por arquivo.
- Se um arquivo gerar múltiplas DAGs, todas devem pertencer ao mesmo escopo de
  seleção e compartilhar `DAG_TAGS`.
- `DAG_TAGS` deve ser uma atribuição literal no nível superior, usando string,
  lista, tupla ou conjunto. Expressões dinâmicas, chamadas de função, leitura
  de variável de ambiente ou união de conjuntos não são permitidas nessa
  declaração.
- Toda DAG selecionável deve repassar `DAG_TAGS` para o parâmetro `tags` do
  objeto `DAG`.
- Cada DAG deve possuir ao menos uma tag de projeto/cliente. Tags descritivas
  como `bronze`, `gold` ou `api` podem coexistir, mas os deployments devem usar
  tags de projeto na allowlist para evitar seleções excessivamente amplas.

Essas regras serão verificadas em testes estáticos do framework.

### Limites operacionais e de segurança

A seleção por tags define a composição de um deployment e reduz trabalho de
parsing. Ela **não é uma fronteira de segurança ou isolamento multi-tenant**:
os arquivos não selecionados ainda podem estar presentes na imagem ou volume de
DAGs. Controle de acesso a código, conexões, credenciais, redes e dados continua
sendo responsabilidade da infraestrutura de cada projeto.

Alterar `AIRFLOW_ENABLED_DAG_TAGS` exige reiniciar ou fazer rollout do componente
de parsing. DAGs que deixam de ser descobertas são desativadas pelo Airflow e
seu histórico permanece no banco de metadados. A remoção de uma tag não cancela
execuções já iniciadas; mudanças de seleção devem ser precedidas por pausa e
drenagem quando houver runs ativos relevantes.

## Alternativas consideradas

### Alternativa A: Carregar todas as DAGs e usar pause/unpause

- Descrição: todas as DAGs são importadas; cada cliente pausa manualmente as
  que não deseja executar.
- Prós: usa apenas funcionalidades nativas da interface/API do Airflow; não
  exige convenção estática nem callable customizado.
- Contras: não reduz custo de parsing nem isola erros de importação; mantém
  DAGs irrelevantes na interface; a composição do deployment depende de estado
  mutável no banco de metadados.

### Alternativa B: Separar DAGs por pasta e usar `.airflowignore`

- Descrição: organizar DAGs em diretórios por cliente/projeto e ignorar paths
  não utilizados em cada deployment.
- Prós: evita parsing antes da importação usando uma funcionalidade nativa e
  simples; diretórios ignorados nem precisam ser percorridos.
- Contras: acopla seleção à estrutura física do repositório; dificulta DAGs
  compartilhadas por múltiplos clientes; pode exigir duplicação, links ou
  geração de arquivos de ignore diferentes por deployment. Não atende ao
  requisito de seleção independente do path.

### Alternativa C: Filtrar com `dag_policy` pelas tags nativas

- Descrição: carregar cada DAG e lançar `AirflowClusterPolicySkipDag` quando
  `dag.tags` não coincidir com a configuração do cliente.
- Prós: trabalha diretamente com o objeto DAG, permite granularidade por DAG
  mesmo quando há várias no mesmo arquivo e não exige leitura via AST.
- Contras: a policy roda após o carregamento completo da DAG; portanto não
  evita imports, código top-level, dependências ausentes nem o custo de parsing
  que motivam esta decisão.

### Alternativa D: Branches, imagens ou pacotes de DAGs por cliente

- Descrição: produzir um conjunto físico distinto de DAGs para cada projeto.
- Prós: apenas o código necessário chega ao ambiente; oferece isolamento mais
  forte dos artefatos implantados.
- Contras: multiplica variantes de build e release, cria risco de divergência
  entre clientes e aumenta o custo de propagar correções do framework. Contraria
  o objetivo do ADR-0003 de manter uma base compartilhada e versionada.

### Callable de descoberta com tags estáticas — decisão proposta

- Descrição: ler `DAG_TAGS` via AST e comparar com uma allowlist do deployment
  antes de o Airflow importar o arquivo.
- Por que foi escolhida: combina uma única base de DAGs com seleção declarativa
  por ambiente, funciona independentemente do path e elimina o parsing dos
  arquivos não selecionados. O custo é um contrato mais rígido de autoria e a
  granularidade por arquivo, considerados aceitáveis para um framework
  opinativo.

## Tradeoffs

| Dimensão | Ganho | Custo/Risco |
|---|---|---|
| Performance do DAG Processor | Arquivos não selecionados deixam de ser importados, reduzindo CPU, memória e efeitos de código top-level | Todo candidato passa por leitura e análise AST; o ganho depende de haver número ou custo relevante de DAGs não selecionadas |
| Base compartilhada | Um mesmo pacote de DAGs atende vários projetos apenas mudando variáveis de ambiente | Erro na allowlist pode fazer DAGs esperadas desaparecerem ou selecionar DAGs em excesso |
| Independência de path | DAGs são selecionadas por significado, sem estrutura de pastas por cliente | O contrato depende de metadados literais dentro de cada arquivo |
| Fonte única de tags | `DAG_TAGS` alimenta descoberta e interface do Airflow | Autores devem seguir a convenção e não construir tags dinamicamente |
| Granularidade | Implementação simples e anterior à importação | Seleção ocorre por arquivo; múltiplas DAGs no mesmo módulo não podem ter escopos diferentes |
| Diagnóstico | Erros de sintaxe continuam sendo encaminhados ao parser do Airflow | Arquivos excluídos não revelam erros de dependência/importação naquele deployment; CI precisa validar o conjunto completo |
| Segurança | Reduz exposição operacional e poluição da interface | Não remove código do artefato nem substitui isolamento de credenciais, rede ou dados |
| Operação | Composição do cliente fica declarada no deployment e versionável em Helm/GitOps | Mudanças nas tags habilitadas exigem rollout do DAG Processor/scheduler e procedimento para runs em andamento |

## Consequências

- **Positivas**: cada cliente executa um deployment derivado da mesma base do
  framework, mas o Airflow só importa os arquivos associados às tags
  habilitadas. A seleção fica explícita em configuração versionável, a UI
  mostra apenas DAGs relevantes e problemas em imports de DAGs não selecionadas
  deixam de impactar aquele ambiente.
- **Negativas**: a autoria de DAGs passa a obedecer um formato estático e
  testável. Arquivos com múltiplas DAGs perdem seleção individual, e a equipe
  precisa manter uma taxonomia de tags para evitar colisões entre tags de
  projeto e tags meramente descritivas.
- **Ações decorrentes**:
  - Implementar `dag_discovery.might_contain_selected_dag` em módulo leve e
    importável pelos componentes de parsing.
  - Adicionar testes unitários para normalização, semântica OR, wildcard,
    arquivos sem tag, declaração não literal, erro de sintaxe e arquivos ZIP.
  - Adicionar teste de contrato que garanta `DAG_TAGS` literal, ao menos uma tag
    de projeto e repasse para `DAG(tags=...)`.
  - Validar nos manifests/Helm que deployments de cliente definem
    `AIRFLOW_ENABLED_DAG_TAGS` explicitamente; o wildcard deve ser reservado a
    desenvolvimento, validação global ou deployments deliberadamente completos.
  - Executar parsing/testes do conjunto completo em CI, pois DAGs filtradas em
    um cliente não serão validadas por aquele deployment.
  - Documentar o procedimento de alteração da allowlist, incluindo pausa,
    drenagem e rollout do componente de parsing.

## Referências

- [Apache Airflow — Loading DAGs e `might_contain_dag_callable`](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html#loading-dags)
- [Apache Airflow — configuração `might_contain_dag_callable`](https://airflow.apache.org/docs/apache-airflow/stable/configurations-ref.html#might-contain-dag-callable)
- [Apache Airflow — Cluster Policies](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/cluster-policies.html)
- [ADR-0001 — Apache Airflow como orquestrador](./0001-airflow-como-orquestrador-de-fluxos-de-dados.md)
- [ADR-0003 — GovHub como framework compartilhado](./0003-govhub-como-framework-compartilhado-de-dados.md)
- [Estrutura de ADRs do repositório](./README.md)
