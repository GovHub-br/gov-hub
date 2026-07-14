# ADR-0005: Seleção de DAGs por arquivo `dag_selector` antes do parsing

- **Status**: Proposto
- **Data**: 2026-07-14
- **Autores**: [Arthrok](https://github.com/Arthrok)
- **Revisores**: [João Henrique Egewarth](https://github.com/egewarth)

## Introdução ao problema

O `data-framework` distribui um conjunto compartilhado de DAGs do Apache
Airflow para múltiplos projetos/órgãos consumidores, organizados em um
monorepo por sistema e órgão (ver
[ADR-0004](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)).
Cada órgão precisa habilitar apenas os fluxos que fazem parte do seu escopo,
sem manter um fork do framework nem duplicar código entre deployments.

Carregar todas as DAGs e apenas pausá-las depois não resolve completamente o
problema:

- Todos os arquivos continuam sendo importados pelo DAG Processor, consumindo
  CPU e memória mesmo quando suas DAGs não serão usadas naquele deployment.
- Dependências ausentes ou erros de importação de uma DAG não selecionada ainda
  podem afetar o parsing do ambiente do órgão.
- A interface do Airflow fica poluída com DAGs que não pertencem ao órgão.
- A composição do deployment fica implícita no estado do banco de metadados
  (pausado/despausado), em vez de declarada na configuração do deployment.

O `.airflowignore` nativo do Airflow resolve o custo de parsing ao evitar
que arquivos ignorados sejam sequer lidos, mas funciona como **blocklist**:
lista o que deve ser excluído. Isso se encaixa mal na estrutura do monorepo
definida no [ADR-0004](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md):
como cada deployment de órgão tipicamente usa apenas uma fração pequena das
pastas do repositório (poucos sistemas, uma única subpasta de órgão), listar
"tudo que eu não uso" cresce a cada novo sistema adicionado ao framework e é
fácil de esquecer de atualizar — o oposto do comportamento desejado, que é
um deployment seguro por padrão (nada é incluído a menos que declarado).

Esta decisão substitui uma abordagem baseada em tags estáticas (`DAG_TAGS`)
avaliada anteriormente para este mesmo problema, descrita e rejeitada na
seção de Alternativas. Essa decisão precisa ser tomada agora para que a
seleção de DAGs faça parte do contrato do framework antes da criação de
muitos deployments de órgãos consumidores.

## Decisão

O `data-framework` adotará um arquivo declarativo chamado `dag_selector`,
com a lógica **invertida** de um `.airflowignore`: em vez de listar o que
deve ser ignorado, `dag_selector` lista o que deve ser **incluído** —
arquivos ou pastas de DAGs que aquele deployment específico quer carregar.
Tudo que não constar no `dag_selector` é ignorado pelo parsing, do mesmo
jeito que um `.airflowignore` ignora o que está listado nele.

### Formato do arquivo `dag_selector`

Um arquivo de texto simples, um padrão por linha, na raiz da pasta de DAGs
(o mesmo diretório onde ficaria um `.airflowignore`):

```text
# dag_selector — pastas/arquivos de DAG incluídos neste deployment
data_ingest/compras_gov/
data_ingest/compras_gov/mir/
data_ingest/ibge/
dbt/mir/
```

- Cada linha é um caminho relativo à pasta de DAGs, apontando para um
  arquivo específico ou para uma pasta — nesse caso, tudo dentro da pasta é
  incluído recursivamente.
- Uma pasta de sistema (ex.: `data_ingest/compras_gov/`) inclui os arquivos
  soltos naquele nível, mas **não** inclui automaticamente subpastas de
  órgão dentro dela (ex.: `data_ingest/compras_gov/mir/`) — cada subpasta de
  órgão usada pelo deployment precisa da própria linha, mantendo explícito
  quais órgãos aquele ambiente carrega.
- A sintaxe de cada linha (regex por padrão, ou glob quando configurado)
  segue a mesma sintaxe aceita por `AIRFLOW__CORE__DAG_IGNORE_FILE_SYNTAX`,
  reaproveitando a implementação de casamento de padrões já validada pelo
  Airflow, só que com o resultado do match invertido.
- Linhas vazias e comentários (`#`) são ignorados, como em `.airflowignore`.
- O valor especial `*` (uma única linha contendo apenas `*`) inclui tudo —
  equivalente a não ter seleção nenhuma — reservado a desenvolvimento local,
  validação global em CI ou um deployment intencionalmente completo.
- Arquivo `dag_selector` ausente mantém o comportamento retrocompatível de
  carregar tudo, equivalente a `*`. Deployments de órgão devem definir uma
  allowlist explícita, com essa condição validada no manifesto/Helm.

### Mecanismo de aplicação

O contrato é resolvido por **caminho**, sem necessidade de ler o conteúdo
Python do arquivo nem executar `ast.parse` — diferente da abordagem por
tags avaliada anteriormente, que precisava abrir e analisar cada arquivo
candidato para extrair `DAG_TAGS`.

O `data-framework` implementa esse contrato via
`AIRFLOW__CORE__MIGHT_CONTAIN_DAG_CALLABLE`:

```python
def might_contain_selected_dag(file_path: str, zip_file_path: str | None = None) -> bool:
    if not might_contain_dag_via_default_heuristic(file_path, zip_file_path):
        return False
    return dag_selector.is_included(file_path)
```

O callable primeiro executa `might_contain_dag_via_default_heuristic`,
preservando a otimização nativa que busca os termos `airflow` e `dag`.
Somente arquivos aprovados pela heurística padrão têm o caminho comparado
contra os padrões do `dag_selector`. Nenhum arquivo de DAG é importado ou
executado pelo filtro, e nenhum arquivo fora da allowlist chega a ter seu
conteúdo lido.

A configuração de referência do componente responsável pelo parsing será:

```yaml
env:
  - name: AIRFLOW__CORE__MIGHT_CONTAIN_DAG_CALLABLE
    value: "dag_discovery.might_contain_selected_dag"
```

O `dag_selector` é lido a partir da raiz da pasta de DAGs, sem variável de
ambiente própria — o mesmo padrão de descoberta por convenção usado pelo
`.airflowignore` nativo. O módulo `dag_discovery` deve estar no
`PYTHONPATH` de todo componente que faz descoberta/parsing de DAGs. Em
Airflow 3 isso inclui o DAG Processor; em arquiteturas anteriores essa
responsabilidade normalmente está associada ao scheduler.

### Granularidade e convenções obrigatórias

O `dag_selector` seleciona **caminhos** (arquivos ou pastas), não objetos
`DAG`. Por isso:

- Uma pasta inteira pode ser incluída com uma única linha — ao contrário da
  abordagem por tags, um novo arquivo criado dentro de uma pasta já incluída
  é automaticamente selecionado, sem exigir nenhuma declaração adicional.
- Se um arquivo gerar múltiplas DAGs, todas seguem o mesmo escopo de
  seleção do arquivo em que estão — não há como incluir uma DAG e excluir
  outra dentro do mesmo arquivo.
- A tag nativa do objeto `DAG` (parâmetro `tags=`) continua existindo
  livremente para organização e busca na interface do Airflow, mas fica
  **desacoplada** da seleção de deployment: usar ou não `tags=` não afeta
  se o arquivo é carregado.

Essas regras serão verificadas em testes estáticos do framework.

### Limites operacionais e de segurança

A seleção por `dag_selector` define a composição de um deployment e reduz
trabalho de parsing. Ela **não é uma fronteira de segurança ou isolamento
multi-tenant**: os arquivos não selecionados ainda podem estar presentes na
imagem ou volume de DAGs. Controle de acesso a código, conexões,
credenciais, redes e dados continua sendo responsabilidade da
infraestrutura de cada órgão.

Alterar o `dag_selector` exige reiniciar ou fazer rollout do componente de
parsing. DAGs que deixam de ser descobertas são desativadas pelo Airflow e
seu histórico permanece no banco de metadados. A remoção de uma entrada não
cancela execuções já iniciadas; mudanças de seleção devem ser precedidas
por pausa e drenagem quando houver runs ativos relevantes.

## Alternativas consideradas

### Alternativa A: Carregar todas as DAGs e usar pause/unpause

- Descrição: todas as DAGs são importadas; cada órgão pausa manualmente as
  que não deseja executar.
- Prós: usa apenas funcionalidades nativas da interface/API do Airflow; não
  exige convenção estática nem callable customizado.
- Contras: não reduz custo de parsing nem isola erros de importação; mantém
  DAGs irrelevantes na interface; a composição do deployment depende de
  estado mutável no banco de metadados.

### Alternativa B: `.airflowignore` nativo (blocklist direta)

- Descrição: usar o `.airflowignore` do próprio Airflow para ignorar, em
  cada deployment, os arquivos/pastas não utilizados.
- Prós: 100% nativo, sem código customizado; evita parsing dos arquivos
  ignorados, igual à proposta deste ADR.
- Contras: é uma blocklist, não uma allowlist. Como cada deployment de
  órgão usa apenas uma fração pequena das pastas do monorepo, seria preciso
  listar todos os demais sistemas/órgãos a cada deployment — uma lista que
  cresce a cada novo sistema adicionado ao framework e que, se esquecida,
  falha de modo inseguro (carrega DAGs de mais, não de menos).

### Alternativa C: Filtrar com `dag_policy` pelas tags nativas

- Descrição: carregar cada DAG e lançar `AirflowClusterPolicySkipDag` quando
  `dag.tags` não coincidir com a configuração do órgão.
- Prós: trabalha diretamente com o objeto DAG, permite granularidade por DAG
  mesmo quando há várias no mesmo arquivo e não exige leitura via AST.
- Contras: a policy roda após o carregamento completo da DAG; portanto não
  evita imports, código top-level, dependências ausentes nem o custo de
  parsing que motivam esta decisão.

### Alternativa D: Branches, imagens ou pacotes de DAGs por órgão

- Descrição: produzir um conjunto físico distinto de DAGs para cada órgão.
- Prós: apenas o código necessário chega ao ambiente; oferece isolamento
  mais forte dos artefatos implantados.
- Contras: multiplica variantes de build e release, cria risco de
  divergência entre órgãos e aumenta o custo de propagar correções do
  framework. Contraria o objetivo do
  [ADR-0004](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md) de
  manter um monorepo compartilhado.

### Alternativa E: Seleção por tags estáticas (`DAG_TAGS`) via callable customizado

- Descrição: cada arquivo de DAG declara uma constante `DAG_TAGS` no nível
  superior do módulo; um callable customizado lê essa constante via AST e
  compara com uma allowlist de tags do deployment
  (`AIRFLOW_ENABLED_DAG_TAGS`), antes de o Airflow importar o arquivo.
- Prós: seleção independente da estrutura física de pastas; permite
  reorganizar arquivos sem alterar seu escopo de seleção.
- Contras: exige que todo arquivo de DAG declare e mantenha `DAG_TAGS`
  manualmente, como uma segunda fonte de verdade paralela à localização do
  arquivo — redundante agora que o
  [ADR-0004](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)
  já define uma convenção de pastas por sistema/órgão. Exige leitura e
  análise AST de cada arquivo candidato, um custo que a seleção por caminho
  evita por completo. Foi a decisão original deste ADR e é substituída pela
  Alternativa proposta abaixo.

### `dag_selector` — decisão proposta

- Descrição: um arquivo de allowlist por caminho, com semântica invertida
  ao `.airflowignore`, resolvido antes de o Airflow importar cada arquivo
  candidato.
- Por que foi escolhida: aproveita a convenção de pastas por sistema/órgão já
  estabelecida no [ADR-0004](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)
  como única fonte de verdade para seleção — sem exigir metadado redundante
  por arquivo (Alternativa E) — e evita o crescimento inseguro de uma
  blocklist (Alternativa B), sendo segura por padrão: nada é carregado a
  menos que explicitamente declarado.

## Tradeoffs

| Dimensão | Ganho | Custo/Risco |
|---|---|---|
| Performance do DAG Processor | Arquivos fora do `dag_selector` nem chegam a ter o conteúdo lido — a decisão é só de caminho, sem AST | O ganho depende de haver volume ou custo relevante de arquivos fora da allowlist |
| Base compartilhada | Um mesmo pacote de DAGs atende vários órgãos apenas trocando o arquivo `dag_selector` do deployment | Erro na allowlist pode fazer DAGs esperadas desaparecerem ou incluir DAGs em excesso |
| Fonte única de seleção | Reaproveita a estrutura de pastas por sistema/órgão do ADR-0004; não há metadado redundante para manter sincronizado com a localização do arquivo | Acopla a seleção à estrutura física do repositório — mover um arquivo de pasta muda seu escopo de seleção implicitamente |
| Simplicidade de autoria | Um arquivo novo dentro de uma pasta já incluída é selecionado automaticamente, sem exigir declaração por arquivo | Incluir um único arquivo dentro de uma pasta maior, sem incluir o restante dela, ainda é possível mas menos natural que incluir a pasta inteira |
| Granularidade | Suporta arquivo e pasta inteira na mesma sintaxe de linha | Seleção ocorre por arquivo/pasta; múltiplas DAGs no mesmo módulo não podem ter escopos diferentes |
| Diagnóstico | Arquivos fora da allowlist nunca são importados, então nunca geram erro de import naquele deployment | CI precisa validar o conjunto completo, já que erros em arquivos não selecionados não aparecem no deployment do órgão |
| Segurança | Reduz exposição operacional e poluição da interface | Não remove código do artefato nem substitui isolamento de credenciais, rede ou dados |
| Operação | Composição do órgão fica declarada em um único arquivo versionável em Helm/GitOps | Mudanças no `dag_selector` exigem rollout do DAG Processor/scheduler e procedimento para runs em andamento |

## Consequências

- **Positivas**: cada órgão executa um deployment derivado da mesma base do
  monorepo, mas o Airflow só importa os arquivos/pastas declarados no
  `dag_selector`. A seleção fica explícita em um único arquivo versionável,
  sem exigir metadado redundante por arquivo de DAG, a UI mostra apenas
  DAGs relevantes e problemas em imports de DAGs não selecionadas deixam de
  impactar aquele ambiente.
- **Negativas**: a seleção passa a depender diretamente da estrutura de
  pastas por sistema/órgão do monorepo — reorganizar uma pasta muda
  implicitamente o escopo de seleção de quem depende dela. Arquivos com
  múltiplas DAGs continuam sem seleção individual por DAG.
- **Ações decorrentes**:
  - Implementar `dag_discovery.might_contain_selected_dag` e o parser do
    `dag_selector` em módulo leve e importável pelos componentes de
    parsing.
  - Adicionar testes unitários para casamento de padrões (arquivo e pasta),
    wildcard `*`, arquivo ausente, comentários/linhas vazias e arquivos ZIP.
  - Validar nos manifests/Helm que deployments de órgão definem um
    `dag_selector` explícito; o wildcard deve ser reservado a
    desenvolvimento, validação global em CI ou deployments deliberadamente
    completos.
  - Executar parsing/testes do conjunto completo em CI, pois arquivos
    filtrados em um deployment de órgão não serão validados por aquele
    deployment.
  - Documentar o procedimento de alteração do `dag_selector`, incluindo
    pausa, drenagem e rollout do componente de parsing.

## Referências

- [Apache Airflow — `.airflowignore`](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html#airflowignore)
- [Apache Airflow — configuração `dag_ignore_file_syntax`](https://airflow.apache.org/docs/apache-airflow/stable/configurations-ref.html#dag-ignore-file-syntax)
- [Apache Airflow — Loading DAGs e `might_contain_dag_callable`](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/dags.html#loading-dags)
- [Apache Airflow — configuração `might_contain_dag_callable`](https://airflow.apache.org/docs/apache-airflow/stable/configurations-ref.html#might-contain-dag-callable)
- [ADR-0001 — Apache Airflow como orquestrador](./0001-airflow-como-orquestrador-de-fluxos-de-dados.md)
- [ADR-0003 — GovHub como framework compartilhado](./0003-govhub-como-framework-compartilhado-de-dados.md)
- [ADR-0004 — Monorepo como estratégia de organização de código](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)
- [Estrutura de ADRs do repositório](./README.md)
