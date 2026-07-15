# ADR-0004: Monorepo como estratégia de organização de código

- **Status**: Proposto
- **Data**: 2026-07-14
- **Autores**: João Egewarth
- **Revisores**: -

## Introdução ao problema

O `data-framework` (GovHub) é consumido por múltiplos projetos de dados
públicos — atualmente 5 — que compartilham extrações, transformações e a
mesma base de orquestração em Airflow (ver
[ADR-0003](./0003-govhub-como-framework-compartilhado-de-dados.md)). É
preciso decidir onde esse código vive: um repositório próprio por projeto
(polyrepo), ou um único repositório compartilhado (monorepo).

Manter um repositório por projeto — o cenário natural se nenhuma decisão for
tomada — gera problemas concretos à medida que o número de projetos
consumidores cresce:

- **Gestão de comunidade fragmentada**: contribuições e PRs se espalham por
  5 repositórios diferentes, cada um com seu próprio conjunto de
  mantenedores, regras de revisão e histórico. Isso dificulta ter uma visão
  única de quem contribui, o que está em revisão e qual é o padrão de
  qualidade esperado.
- **Duplicação de código de extração e transformação**: lógica de ingestão e
  transformação que é, em essência, a mesma entre projetos (ex.: extrair de
  uma mesma fonte pública, aplicar a mesma regra de qualidade) acaba
  copiada e colada entre repositórios, divergindo silenciosamente ao longo
  do tempo.
- **Atualização de dependências custosa**: subir a versão de uma
  biblioteca (Airflow, dbt, driver de banco) exige repetir o mesmo trabalho
  em 5 repositórios, cada um podendo ficar em uma versão diferente da
  mesma dependência.
- **Alteração de extrações compartilhadas é multiplicada por 5**: uma
  correção ou mudança de regra em uma extração usada por todos os projetos
  precisaria, no cenário de polyrepo, ser replicada, testada e revisada em
  5 códigos-fonte separados — com alto risco de a mudança ser aplicada de
  forma inconsistente entre eles.
- **Adoção de Airflow multi-team dificultada**: o
  [ADR-0001](./0001-airflow-como-orquestrador-de-fluxos-de-dados.md) pressupõe
  uma base única de DAGs, filtrada por deployment. Com código espalhado em
  múltiplos repositórios, montar ambientes compartilhados de
  desenvolvimento e homologação (onde vários times/projetos operam sobre a
  mesma instância de Airflow) exige sincronizar builds e artefatos de
  repositórios distintos, em vez de partir de uma única fonte de verdade.

Essa decisão precisa ser tomada agora porque a forma como o código é
distribuído entre repositórios é uma decisão estrutural difícil de reverter
depois que múltiplos times já construíram processos (CI, deploy, revisão)
em torno dela.

## Decisão

O `data-framework` adota um **monorepo**: um único repositório contendo o
framework compartilhado e o código dos projetos consumidores (DAGs,
extrações, transformações e configuração específica de cada projeto),
em vez de um repositório por projeto.

Isso implica que:

- Código compartilhado (extrações, transformações, operadores customizados,
  convenções de estrutura) vive em um único lugar, consumido diretamente
  pelos projetos dentro do mesmo repositório — sem publicação intermediária
  via pacote versionado nem cópia manual entre repositórios.
- Contribuições e PRs de qualquer projeto passam pelo mesmo processo de
  revisão, usando os mesmos padrões de CI, lint e teste definidos pelo
  framework.
- A seleção de DAGs por tags passa a ser o mecanismo natural para que
  múltiplos times/projetos operem sobre o mesmo ambiente de Airflow em
  dev/homolog a partir da mesma base de código, cada um habilitando apenas
  suas próprias DAGs.
- Atualizações de dependência (Airflow, dbt, bibliotecas Python) são feitas
  uma única vez e passam a valer para todos os projetos simultaneamente, via
  CI do próprio monorepo.

### Estrutura do repositório

O monorepo segue a estrutura de pastas já usada pelo projeto
[data-application-gov-hub](https://github.com/GovHub-br/data-application-gov-hub):
DAGs organizadas primeiro por **sistema/fonte de dados** (ex.: `compras_gov`,
`ibge`, `pncp`, `siorg`), e modelos de transformação (dbt) organizados por
projeto.

Além dessa separação por sistema, o monorepo distingue três situações,
conforme o quanto um sistema/fonte de dados é compartilhado entre órgãos —
e essa mesma lógica se aplica tanto às DAGs de ingestão quanto aos modelos
dbt de transformação:

1. **Sistema compartilhado, código compartilhado**: DAGs ou modelos dbt
   usados por mais de um órgão ficam diretamente na pasta do sistema
   (`data_ingest/<sistema>/`, `dbt/<sistema>/`).
2. **Sistema compartilhado, código específico de um órgão**: quando o mesmo
   sistema é compartilhado, mas parte das DAGs ou modelos só faz sentido
   para um órgão específico, esse código fica em uma subpasta de órgão
   **dentro** da pasta do sistema (`data_ingest/<sistema>/<orgao>/`,
   `dbt/<sistema>/<orgao>/`).
3. **Sistema interno de um único órgão**: quando o sistema/fonte de dados
   inteiro é específico de um único órgão, sem uso previsto por outros
   consumidores, o código fica direto em uma pasta de órgão no nível raiz
   (`data_ingest/<orgao>/`, `dbt/<orgao>/`) — sem uma pasta de sistema
   intermediária, já que não há nada a compartilhar.

Como cada órgão tem seu próprio banco de dados e, portanto, seu próprio
projeto dbt (com `dbt_project.yml` e `profiles.yml` próprios), o
compartilhamento de modelos dbt entre órgãos não significa um único projeto
executado por todos — cada `dbt/<sistema>/` é um **pacote dbt local**
(`dbt_project.yml` do tipo pacote, sem `profiles.yml` próprio), importado
via `packages.yml` pelo projeto de cada órgão que consome aquele sistema.
`dbt/<sistema>/<orgao>/`, dentro do pacote, contém modelos daquele pacote
que só fazem sentido para um órgão específico, mas que ainda são
distribuídos e versionados junto com o pacote compartilhado.

Estrutura de referência:

```
airflow/
  dags/
    data_ingest/
      <sistema>/                # sistema compartilhado — ex.: compras_gov, ibge, pncp, siorg
        *_ingest_dag.py         # DAGs compartilhadas por todos os órgãos que usam o sistema
        <orgao>/                # ex.: mir, ipea — apenas quando parte das DAGs do sistema for específica de um órgão
          *_ingest_dag.py
      <orgao>/                  # sistema interno, específico de um único órgão — sem pasta de sistema intermediária
        *_ingest_dag.py
    dbt/
      <sistema>/                # pacote dbt compartilhado por todos os órgãos que usam o sistema
        dbt_project.yml         # projeto do tipo pacote (sem profiles.yml próprio)
        models/
        <orgao>/                # modelos do pacote específicos de um órgão, mas distribuídos junto com ele
          ...
      <orgao>/                  # projeto dbt do órgão (dbt_project.yml + profiles.yml próprios)
        dbt_project.yml
        packages.yml            # importa os pacotes de <sistema>/ que esse órgão consome
        models/                 # modelos específicos deste órgão (incl. sistemas internos)
        ...
```

- Regra: uma DAG ou modelo dbt só entra em uma pasta/subpasta de `<orgao>`
  quando não for compartilhado por todos os órgãos que usam aquele sistema.
  Se mais de um órgão passar a depender de uma DAG ou modelo hoje
  específico, ele deve subir para a pasta do sistema (deixando de ser
  específico de um órgão). Da mesma forma, se um sistema hoje interno a um
  único órgão (`data_ingest/<orgao>/`, `dbt/<orgao>/`) passar a ser usado
  por outro órgão, ele deve ser promovido a sistema compartilhado
  (`data_ingest/<sistema>/`, `dbt/<sistema>/` como pacote), com o código
  hoje em `<orgao>/` migrando para uma subpasta `<sistema>/<orgao>/` apenas
  se ainda restar algo específico desse órgão.

### CODEOWNERS por pasta

O monorepo usa um arquivo `CODEOWNERS` (`.github/CODEOWNERS`) para atribuir
revisão obrigatória por pasta, reduzindo o risco de isolamento insuficiente
entre projetos apontado nos Tradeoffs:

- Pastas de sistema compartilhado (`data_ingest/<sistema>/*.py`,
  `dbt/<sistema>/`, fora de subpastas de órgão) são de propriedade dos
  mantenedores do `data-framework` — qualquer mudança em código ou pacote
  dbt compartilhado exige revisão do time do framework, já que ela afeta
  todos os órgãos consumidores.
- Subpastas de órgão dentro de um sistema compartilhado
  (`data_ingest/<sistema>/<orgao>/`, `dbt/<sistema>/<orgao>/`), pastas de
  sistema interno de um único órgão (`data_ingest/<orgao>/`) e projetos dbt
  de órgão (`dbt/<orgao>/`) são de propriedade do time responsável por
  aquele órgão/projeto — mudanças específicas de um órgão não exigem
  aprovação dos demais times, apenas do time dono da pasta.
- `CODEOWNERS` define quem **aprova** cada mudança, não quem **enxerga** o
  código — no monorepo, todo contribuidor continua tendo visibilidade de
  leitura sobre as pastas de todos os órgãos, o que é uma limitação já
  registrada nos Tradeoffs (dimensão "Visibilidade de código entre
  projetos") e não é resolvida por esta convenção.

## Alternativas consideradas

### Alternativa A: Um repositório por projeto (polyrepo / status quo)

- Descrição: cada um dos 5 projetos consumidores mantém seu próprio
  repositório, geralmente iniciado a partir de um fork ou cópia do
  `data-framework`.
- Prós: isolamento total entre projetos — mudanças em um repositório nunca
  afetam outro; controle de acesso granular é trivial (um repositório por
  time); cada projeto pode, em tese, evoluir em ritmo próprio.
- Contras: é exatamente o cenário que gera os cinco problemas descritos na
  introdução — duplicação de código, dependências divergentes, mudanças
  compartilhadas multiplicadas por 5, gestão de comunidade fragmentada e
  dificuldade de operar Airflow multi-team a partir de uma base comum.
  Contraria diretamente o objetivo de framework compartilhado do
  [ADR-0003](./0003-govhub-como-framework-compartilhado-de-dados.md).

### Alternativa B: Framework como pacote publicado, consumido por repositórios separados

- Descrição: o código compartilhado do `data-framework` é publicado como um
  pacote versionado (ex.: em um índice PyPI privado), e cada projeto mantém
  seu próprio repositório, importando o framework como dependência.
- Prós: mantém isolamento de repositório por projeto, como na Alternativa A,
  mas resolve parcialmente a duplicação de código ao centralizar a lógica
  compartilhada em um pacote versionado.
- Contras: introduz um passo de publicação/release intermediário para toda
  mudança no código compartilhado, adicionando latência entre "corrigir a
  extração" e "todos os projetos terem a correção". Ainda deixa a gestão de
  comunidade fragmentada entre 5 repositórios e não resolve a dificuldade de
  operar um ambiente de Airflow multi-team a partir de uma base única de
  DAGs, já que cada projeto continua com seu próprio repositório de DAGs.

### Monorepo — decisão proposta

- Descrição: um único repositório contendo o framework e o código de todos
  os projetos consumidores, com convenções e CI compartilhados.
- Por que foi escolhida: é a única alternativa que resolve diretamente todos
  os cinco problemas levantados na introdução ao mesmo tempo — sem exigir um
  passo de publicação intermediário (diferente da Alternativa B) e sem
  perpetuar a fragmentação de repositórios (diferente da Alternativa A).

## Tradeoffs

### Vantagens (ordenadas por impacto, do maior para o menor)

| Dimensão | Ganho | Impacto |
|---|---|---|
| Duplicação de código compartilhado | Extrações e transformações usadas pelos 5 projetos são escritas uma vez e reutilizadas diretamente, sem cópia entre repositórios | ★★★★★ |
| Alteração de extrações compartilhadas | Uma correção ou mudança de regra é feita em um único lugar, em vez de replicada e revisada em 5 códigos-fonte separados | ★★★★★ |
| Atualização de dependências | Versão de Airflow, dbt e bibliotecas Python é atualizada uma única vez, valendo para todos os projetos simultaneamente | ★★★★☆ |
| Adoção de Airflow multi-team em dev/homolog | Múltiplos times operam sobre o mesmo ambiente de Airflow a partir de uma única base de DAGs, selecionando por tags | ★★★★☆ |
| Gestão de comunidade e contribuições | PRs e revisões de todos os projetos passam pelo mesmo processo, com padrão único de qualidade e CI | ★★★☆☆ |

### Desvantagens (ordenadas por impacto, do maior para o menor)

| Dimensão | Custo/Risco | Impacto |
|---|---|---|
| Isolamento entre projetos | Um erro, quebra de build ou dependência mal atualizada pode afetar, ainda que indiretamente, outros projetos que compartilham o mesmo repositório e pipeline de CI | ★★★★☆ |
| Coordenação de release/deploy | Mudanças no monorepo podem exigir coordenação entre times mesmo quando a intenção é alterar apenas um projeto, se o versionamento e o deploy não forem bem segmentados | ★★★★☆ |
| Complexidade de CI | É preciso investir em seletividade (rodar apenas testes/builds afetados por um PR) para que o CI não fique lento à medida que o repositório cresce | ★★★☆☆ |
| Tamanho e navegação do repositório | Repositório maior exige convenções claras de estrutura de pastas para que contribuidores encontrem rapidamente o que pertence a cada projeto | ★★★☆☆ |
| Visibilidade de código entre projetos | Times de projetos diferentes enxergam o código uns dos outros por padrão, o que pode ser indesejável caso surjam requisitos de confidencialidade entre projetos | ★★☆☆☆ |

## Consequências

- **Positivas**: código compartilhado entre os 5 projetos passa a ter uma
  única fonte de verdade, eliminando a duplicação e o risco de divergência
  silenciosa entre extrações e transformações equivalentes. Atualizações de
  dependência e correções em lógica compartilhada deixam de ser
  multiplicadas por projeto, e a operação de um ambiente Airflow
  multi-team em dev/homolog passa a ser viável a partir de uma única base de
  DAGs.
- **Negativas**: o monorepo passa a exigir investimento em CI seletivo
  (evitar rodar tudo a cada PR) e disciplina para manter a estrutura de
  pastas por sistema/órgão e o `CODEOWNERS` atualizados à medida que novos
  órgãos e sistemas são adicionados. A ausência de isolamento físico entre
  projetos exige mais disciplina de testes e revisão para que uma mudança em
  um projeto não quebre outro por acidente.
- **Ações decorrentes**:
  - Migrar/organizar o código do monorepo segundo a estrutura por
    sistema/órgão descrita nesta decisão (`data_ingest/<sistema>/[<orgao>/]`,
    `data_ingest/<orgao>/`, `dbt/<sistema>/[<orgao>/]`, `dbt/<orgao>/`).
  - Criar o arquivo `.github/CODEOWNERS` mapeando pastas de sistema/pacote
    compartilhado aos mantenedores do `data-framework` e pastas/subpastas de
    órgão aos respectivos times.
  - Documentar, em complemento à nomenclatura de pastas dbt, como um
    projeto de órgão declara e importa os pacotes de `dbt/<sistema>/` de que
    depende (`packages.yml`).
  - Configurar CI com seletividade por path, rodando apenas testes e builds
    relevantes às mudanças de cada PR.
  - Documentar o processo de deploy/release por projeto a partir de um
    único repositório, evitando que uma mudança em um projeto force
    deploy desnecessário de outro.

## Referências

- [ADR-0001 — Apache Airflow como orquestrador de fluxos de dados](./0001-airflow-como-orquestrador-de-fluxos-de-dados.md)
- [ADR-0003 — GovHub como framework compartilhado de dados](./0003-govhub-como-framework-compartilhado-de-dados.md)
- [data-application-gov-hub — estrutura de referência do repositório](https://github.com/GovHub-br/data-application-gov-hub)
- [Estrutura de ADRs do repositório](./README.md)
