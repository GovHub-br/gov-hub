# ADR-0001: Apache Airflow como orquestrador de fluxos de dados

- **Status**: Proposto
- **Data**: 2026-07-14
- **Autores**: João Egewarth
- **Revisores**: -

## Introdução ao problema

O `data-framework` precisa de uma ferramenta de orquestração para coordenar
pipelines de dados — ingestão, transformação, qualidade e publicação — que
hoje ou não existem, ou são resolvidos de forma ad-hoc (scripts disparados
por cron, execuções manuais, jobs isolados sem visibilidade entre si).
Projetos de dados públicos apresentam características que tornam essa escolha
particularmente sensível:

- **Fluxos complexos e com dependências reais**: pipelines de dados públicos
  raramente são uma única tarefa. Envolvem múltiplas fontes, etapas
  sequenciais e paralelas, reprocessamento parcial e dependências entre
  tarefas que um cron simples não expressa nem observa.
- **Necessidade de alta customização via código**: cada projeto público tem
  particularidades de fonte de dados, formato, volume e regra de negócio. A
  ferramenta de orquestração precisa permitir lógica arbitrária em código
  (Python), não apenas configuração declarativa limitada.
- **Contexto de adoção no setor público**: o framework é herdado por
  múltiplos órgãos e equipes, muitas vezes com times pequenos, rotatividade
  de servidores/contratados e processos de contratação que dificultam a
  adoção de ferramentas proprietárias ou pouco conhecidas.
- **Restrição orçamentária e de licenciamento**: soluções proprietárias
  implicam custo de licença recorrente e, em muitos casos, risco de
  aprisionamento a fornecedor (vendor lock-in) — algo particularmente
  problemático para contratos públicos, que precisam justificar gasto e
  garantir continuidade caso um fornecedor deixe de ser contratado.
- **Necessidade de continuidade entre gestões e equipes**: sistemas públicos
  trocam de equipe de manutenção com frequência (mudança de gestão,
  fim de contrato, rotatividade). Uma ferramenta com comunidade grande e
  documentação abundante reduz o risco de a solução ficar "órfã" — sem
  ninguém que saiba operá-la — quando a equipe original sai.

Essa decisão precisa ser tomada agora porque a camada de orquestração é uma
das primeiras a ser consumida por qualquer projeto que herdar o
`data-framework`: pipelines de ingestão e transformação (ver contexto do
[ADR-0003](./0003-govhub-como-framework-compartilhado-de-dados.md)) dependem
diretamente de como tarefas são agendadas, encadeadas e monitoradas.

## Decisão

O `data-framework` adota o **Apache Airflow** como orquestrador padrão de
fluxos de dados (DAGs de ingestão, transformação, qualidade e publicação).

Isso implica que:

- Todo pipeline de dados definido pelo framework — e por projetos que o
  herdam — é expresso como uma DAG do Airflow, escrita em Python.
- Convenções de estrutura de DAGs, operadores customizados, sensores e
  conexões são centralizadas no framework, para que projetos consumidores não
  precisem redefinir padrões básicos de orquestração.
- A escolha prioriza explicitamente três fatores: adoção já existente no
  poder público brasileiro, natureza open source (sem custo de licença nem
  vendor lock-in) e maturidade/estabilidade da comunidade — em detrimento de
  ferramentas potencialmente mais modernas, porém menos testadas em contexto
  de governo.

## Alternativas consideradas

### Alternativa A: Scripts + cron (status quo / não fazer nada)

- Descrição: manter pipelines como scripts individuais disparados por cron
  ou execução manual, sem camada de orquestração dedicada.
- Prós: zero custo de adoção, zero dependência nova, funciona para casos
  triviais.
- Contras: não escala para fluxos com dependências reais entre tarefas; não
  há retry automático, alertas, backfill nem visibilidade centralizada de
  execuções. Cada projeto reimplementaria (mal) o que um orquestrador já
  resolve — reproduzindo exatamente o problema de duplicação descrito no
  [ADR-0003](./0003-govhub-como-framework-compartilhado-de-dados.md).

### Alternativa B: Prefect

- Descrição: orquestrador Python moderno, com API mais recente e foco em
  execução dinâmica de fluxos.
- Prós: API considerada mais ergonômica por parte da comunidade; bom suporte
  a fluxos dinâmicos gerados em tempo de execução.
- Contras: comunidade e adoção menores que o Airflow, especialmente no setor
  público brasileiro; o modelo de negócio da Prefect concentra funcionalidades
  relevantes (ex.: certas integrações de orquestração e observabilidade) na
  versão paga/cloud (Prefect Cloud), o que é uma restrição indesejável para
  contratos públicos que buscam evitar dependência de um fornecedor
  específico.

### Alternativa C: Dagster

- Descrição: orquestrador com forte ênfase em ativos de dados (data assets)
  e tipagem, pensado para observabilidade e qualidade de dados desde o
  design.
- Prós: modelo de "software-defined assets" é atraente para lineage e
  qualidade de dados; boa experiência de desenvolvimento local.
- Contras: comunidade e base de adoção significativamente menores que o
  Airflow; poucos ou nenhum caso de uso documentado em órgãos públicos
  brasileiros até o momento, o que eleva o risco de falta de mão de obra
  qualificada disponível no mercado de contratação pública.

### Apache Airflow — decisão proposta

- Descrição: orquestrador de workflows open source, mantido pela Apache
  Software Foundation, com definição de pipelines como DAGs em Python.
- Por que foi escolhida: é a única alternativa que atende simultaneamente aos
  quatro critérios levantados na introdução — ampla adoção no poder público,
  natureza open source, comunidade de scheduler estável e madura, e alta
  capacidade de customização via código Python para fluxos complexos. Nenhuma
  alternativa avaliada atende aos quatro critérios ao mesmo tempo.

## Tradeoffs

### Vantagens

- **[Alto impacto]** Ferramenta já conhecida por servidores/contratados de
  outros projetos públicos, reduzindo custo de treinamento e contratação.
- **[Alto impacto]** Open source, sem custo de licença nem vendor lock-in —
  relevante para justificativa de contratação pública.
- **[Médio impacto]** Projeto maduro, com grande volume de documentação,
  plugins e resposta a bugs críticos.
- **[Médio impacto]** Lógica arbitrária em Python permite atender
  particularidades de qualquer projeto público consumidor.
- **[Alto impacto]** Suporta fluxos complexos com dependências, retries,
  backfill e alertas nativamente, sem que cada projeto precise reimplementar.

### Desvantagens

- **[Alto impacto]** Curva de aprendizado íngreme para times sem experiência
  prévia em orquestração — especialmente crítico dado o perfil de times
  pequenos e rotativos do setor público citado na introdução.
- **[Alto impacto]** Operação e manutenção da infraestrutura (scheduler,
  workers, banco de metadados) ficam sob responsabilidade do próprio time,
  sem suporte comercial garantido.
- **[Médio impacto]** Ritmo de evolução mais conservador; alguns padrões
  (ex.: XComs, certos operadores) carregam débito histórico de design.
- **[Médio impacto]** Alta flexibilidade de código também permite DAGs mal
  escritas (ex.: lógica pesada no parsing) que degradam a performance do
  scheduler se não houver padronização.
- **[Alto impacto]** Exige infraestrutura própria mais pesada que uma solução
  simples de cron — múltiplos componentes (scheduler, webserver, workers,
  banco de metadados), aumentando o custo operacional mínimo de qualquer
  projeto consumidor.

### Avaliação

Os custos de adoção do Airflow são concentrados em complexidade operacional e
curva de aprendizado — ambos de alto impacto e mitigáveis com investimento
inicial (documentação, padronização de DAGs, escolha de deploy simplificado
para projetos pequenos). Os ganhos, por outro lado, endereçam diretamente os
critérios não negociáveis do contexto (custo, licenciamento, continuidade
entre equipes) descritos na introdução. Por isso a decisão é considerada
favorável apesar do custo operacional elevado — mas esse custo deve ser
tratado como um risco ativo a mitigar, não uma nota de rodapé.

## Consequências

- **Positivas**: o framework passa a oferecer uma camada de orquestração
  madura, testada e amplamente reconhecida no contexto do poder público,
  reduzindo o risco de a ferramenta ficar sem manutenção quando há troca de
  equipe. Pipelines de ingestão/transformação/publicação ganham retry,
  backfill, alertas e visibilidade centralizada de execução sem que cada
  projeto precise construir isso por conta própria.
- **Negativas**: projetos consumidores passam a depender da operação de uma
  infraestrutura de Airflow (scheduler, workers, banco de metadados),
  elevando o custo operacional mínimo em relação a uma solução baseada em
  cron. Times sem experiência prévia em Airflow enfrentam curva de
  aprendizado até internalizar boas práticas de escrita de DAGs.
- **Ações decorrentes**:
  - Definir, em ADR ou documento técnico subsequente, as convenções
    concretas de estrutura de DAGs, operadores e conexões padrão do
    framework.
  - Documentar boas práticas de escrita de DAGs (evitar lógica pesada em
    tempo de parsing, uso de connections/variables, padrão de nomenclatura)
    para mitigar o risco de DAGs mal escritas degradarem o scheduler.
  - Avaliar, em decisão futura, o modelo de deploy padrão do Airflow para
    projetos consumidores (ex.: Docker Compose para ambientes menores,
    Kubernetes/Helm para ambientes de maior escala).

## Referências

- [Apache Airflow — documentação oficial](https://airflow.apache.org/docs/)
- [ADR-0003 — GovHub como framework compartilhado de dados](./0003-govhub-como-framework-compartilhado-de-dados.md)
- [Estrutura de ADRs do repositório](./README.md)
