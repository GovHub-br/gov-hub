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
  (evitar rodar tudo a cada PR), convenções de estrutura de pastas e,
  potencialmente, `CODEOWNERS` por diretório para preservar alguma
  granularidade de revisão por projeto. A ausência de isolamento físico
  entre projetos exige mais disciplina de testes e revisão para que uma
  mudança em um projeto não quebre outro por acidente.
- **Ações decorrentes**:
  - Definir, em documento técnico subsequente, a estrutura de pastas do
    monorepo (separação entre framework compartilhado e código específico
    de cada um dos 5 projetos).
  - Configurar CI com seletividade por path, rodando apenas testes e builds
    relevantes às mudanças de cada PR.
  - Avaliar o uso de `CODEOWNERS` por diretório, para que cada projeto
    mantenha um nível de revisão dedicado sobre seu próprio código dentro do
    monorepo.
  - Documentar o processo de deploy/release por projeto a partir de um
    único repositório, evitando que uma mudança em um projeto force
    deploy desnecessário de outro.

## Referências

- [ADR-0001 — Apache Airflow como orquestrador de fluxos de dados](./0001-airflow-como-orquestrador-de-fluxos-de-dados.md)
- [ADR-0003 — GovHub como framework compartilhado de dados](./0003-govhub-como-framework-compartilhado-de-dados.md)
- [Estrutura de ADRs do repositório](./README.md)
