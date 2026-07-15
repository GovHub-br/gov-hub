# ADR-0007: Padrão de nomenclatura das pastas/arquivos de DAGs de ingestão

- **Status**: Proposto
- **Data**: 2026-07-15
- **Autores**: João Egewarth
- **Revisores**: -

## Introdução ao problema

O [ADR-0004](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)
define a estrutura de pastas do monorepo por sistema e órgão
(`data_ingest/<sistema>/[<orgao>/]` para sistemas compartilhados,
`data_ingest/<orgao>/` para sistemas internos de um único órgão), e o
[ADR-0005](./0005-selecao-de-dags-por-dag-selector-antes-do-parsing.md)
usa essa mesma estrutura como base para a seleção de DAGs por deployment.
Nenhum dos dois, no entanto, define como nomear os **arquivos** de DAG
dentro dessas pastas — hoje isso fica a critério de cada autor, o que já
gera inconsistência observável entre exemplos de projetos existentes (ex.:
`contratos_ingest_dag.py` vs. `dashboard_servidores_dag.py` vs.
`licitacoes_ingest.py`, cada um seguindo uma convenção distinta de sufixo).

Sem uma convenção única, dois problemas se repetem:

- **Dificuldade de localizar DAGs**: um engenheiro não consegue prever o
  nome de um arquivo apenas sabendo a entidade e a ação (ingestão,
  transformação, publicação) que ele representa.
- **Ambiguidade entre DAG compartilhada e DAG de órgão**: sem um padrão que
  reflita a posição na estrutura de pastas do ADR-0004, não fica claro, só
  pelo nome do arquivo, se uma DAG é compartilhada ou específica de um
  órgão.

Este ADR adapta, para arquivos de DAG do Airflow, as regras gerais de
nomenclatura e o padrão de nomenclatura de pipelines descritos no *Padrão
de Arquitetura de Dados — MGI/SEGES/CDATA* (v3.0) — documento que já
formaliza convenções equivalentes para jobs/pipelines de sua própria
plataforma (`{produto}_{dominio}_{acao}_job`, minúsculas, dígitos e
underscore apenas, sem espaços/hífens/acentos).

## Decisão

Todo arquivo de DAG de ingestão segue o padrão:

```text
{entidade}_ingest_dag.py                  # dentro de data_ingest/<sistema>/ (sistema compartilhado)
{entidade}_{orgao}_ingest_dag.py          # dentro de data_ingest/<sistema>/<orgao>/ (DAG específica de um órgão dentro de um sistema compartilhado)
{entidade}_{orgao}_ingest_dag.py          # dentro de data_ingest/<orgao>/ (sistema interno de um único órgão)
```

- `{entidade}`: nome da entidade/domínio de negócio ingerida (ex.:
  `contratos`, `licitacoes`, `almoxarifado`), em `snake_case`.
- `{orgao}`: sigla curta do órgão, em minúsculas, presente no nome do
  arquivo sempre que a pasta imediata do arquivo for uma pasta de órgão —
  seja uma subpasta `<orgao>/` aninhada dentro de um sistema compartilhado,
  seja uma pasta `<orgao>/` no nível raiz de `data_ingest/` para um sistema
  interno (redundante com o caminho, mas evita ambiguidade ao visualizar o
  arquivo isolado, ex.: em um diff de PR).
- `dag_id` (identificador da DAG no Airflow) replica o nome do arquivo sem a
  extensão `.py`, mantendo uma correspondência 1-para-1 entre nome de
  arquivo e `dag_id`.
- Sufixo de ação fixo `_ingest_dag` para DAGs de ingestão — outras ações
  (transformação, publicação) recebem sufixos próprios, fora do escopo
  deste ADR (que cobre apenas DAGs de ingestão).

### Regras gerais de nomenclatura

Aplicam-se a pastas e arquivos de DAG:

- Somente letras minúsculas (`a-z`), dígitos (`0-9`) e underscore (`_`).
- Proibido: espaços, hífens, acentos, cedilha ou outros caracteres
  especiais.
- Nome da pasta de sistema (`<sistema>/`) e de órgão (`<orgao>/`) seguem a
  mesma regra — sigla ou nome curto em minúsculas (ex.: `compras_gov`,
  `ibge`, `mir`, `ipea`).
- Nomes de arquivo e `dag_id` respeitam o limite de identificador do
  `dag_id` do Airflow (250 caracteres) — na prática, muito acima do
  necessário para os nomes deste padrão, mas o limite é citado para deixar
  explícito que não há motivo para abreviações agressivas.

## Alternativas consideradas

### Alternativa A: Sem convenção formal (status quo)

- Descrição: cada autor escolhe o nome do arquivo e do `dag_id` livremente.
- Prós: nenhuma curva de aprendizado adicional.
- Contras: é o cenário atual, que já produz inconsistência observável entre
  arquivos existentes e dificulta localizar DAGs apenas pelo nome.

### Alternativa B: Nome da entidade sem sufixo de ação

- Descrição: nomear o arquivo apenas pela entidade (ex.: `contratos.py`),
  sem indicar a ação (ingestão, transformação, publicação).
- Prós: nome mais curto.
- Contras: um arquivo `contratos.py` não deixa claro, sem abri-lo, se é uma
  DAG de ingestão, transformação ou publicação — informação que o sufixo
  de ação comunica de forma imediata, inclusive em listagens de diretório.

### Padrão `{entidade}_[<orgao>_]ingest_dag.py` — decisão proposta

- Descrição: nome de arquivo e `dag_id` combinando entidade, órgão (quando
  aplicável) e ação, adaptando o padrão de nomenclatura de pipelines do
  documento de arquitetura do MGI/SEGES/CDATA à estrutura de pastas por
  sistema/órgão do ADR-0004.
- Por que foi escolhida: torna o nome do arquivo previsível a partir de
  três informações que qualquer engenheiro já conhece de antemão (entidade,
  órgão, ação), sem depender de abrir o arquivo para entender seu papel.

## Tradeoffs

### Vantagens

- **[Alto impacto]** Qualquer engenheiro consegue prever o nome de um
  arquivo de DAG apenas sabendo a entidade e o sistema/órgão a que ela
  pertence, sem precisar abrir o arquivo.
- **[Médio impacto]** O sufixo de ação (`_ingest_dag`) comunica o papel do
  arquivo (ingestão) já na listagem do diretório, sem exigir leitura do
  conteúdo.
- **[Médio impacto]** Reduz divergência de convenções entre arquivos hoje
  já existentes com sufixos distintos (`_ingest_dag`, `_ingest`, sem
  sufixo), unificando futuras contribuições.
- **[Baixo impacto]** `dag_id` previsível (idêntico ao nome do arquivo)
  facilita localizar o arquivo-fonte de uma DAG a partir da interface do
  Airflow.

### Desvantagens

- **[Médio impacto]** Renomear arquivos de DAG já existentes para seguir o
  padrão altera o `dag_id`, o que reseta o histórico de execuções exibido
  na interface do Airflow para aquela DAG (novo `dag_id` = nova entrada no
  banco de metadados).
- **[Baixo impacto]** Nomes ficam mais longos que alternativas mais
  enxutas (ex.: apenas `{entidade}.py`), especialmente em pastas de órgão
  onde o nome do órgão já está implícito no caminho.
- **[Baixo impacto]** O padrão cobre apenas DAGs de ingestão — DAGs de
  outras naturezas (transformação, publicação) exigem convenção própria,
  ainda não definida.

### Avaliação

Os ganhos superam os custos: a previsibilidade de nome e `dag_id` reduz
atrito de navegação no monorepo à medida que o número de sistemas e órgãos
cresce, e o custo de migração (reset de histórico de execução ao renomear
DAGs já existentes) é pago uma única vez, de forma controlada, e não se
repete para DAGs novas escritas já com o padrão.

## Consequências

- **Positivas**: arquivos e `dag_id`s de DAGs de ingestão tornam-se
  previsíveis a partir de entidade, sistema e órgão, reduzindo tempo de
  navegação e revisão de código no monorepo.
- **Negativas**: migrar DAGs já existentes para o novo padrão reseta o
  histórico de execução exibido no Airflow para essas DAGs específicas.
- **Ações decorrentes**:
  - Migrar arquivos de DAG de ingestão já existentes no monorepo para o
    padrão `{entidade}_[<orgao>_]ingest_dag.py`, coordenando a mudança de
    `dag_id` com os times consumidores afetados.
  - Adicionar verificação estática (lint/teste do framework) que rejeite
    nomes de arquivo de DAG de ingestão fora do padrão.
  - Definir, em ADR ou documento complementar futuro, o padrão de
    nomenclatura para DAGs de transformação e publicação.

## Referências

- *Padrão de Arquitetura de Dados — MGI/SEGES/CDATA*, v3.0 (documento
  interno de referência, ambiente DEV).
- [ADR-0004 — Monorepo como estratégia de organização de código](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)
- [ADR-0005 — Seleção de DAGs por arquivo `dag_selector` antes do parsing](./0005-selecao-de-dags-por-dag-selector-antes-do-parsing.md)
- [Estrutura de ADRs do repositório](./README.md)
