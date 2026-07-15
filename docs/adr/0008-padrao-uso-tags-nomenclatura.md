# ADR-0008: Padrão de uso de tags/nomenclatura no Airflow

- **Status**: Proposto
- **Data**: 2026-07-15
- **Autores**: João Egewarth
- **Revisores**: -

## Introdução ao problema

O [ADR-0005](./0005-selecao-de-dags-por-dag-selector-antes-do-parsing.md)
removeu a dependência de tags estáticas (`DAG_TAGS`) para seleção de
deployment, substituindo-as pelo arquivo `dag_selector`. Isso deixa livre o
uso da tag nativa do objeto `DAG` (`tags=`) do Airflow, hoje sem nenhuma
convenção — o que arrisca reintroduzir, de forma menos visível, os mesmos
problemas que motivaram a remoção das tags como mecanismo de seleção:

- **Tags livres e inconsistentes**: sem convenção, cada autor usa tags
  diferentes para o mesmo conceito (ex.: `"compras_gov"` vs. `"comprasgov"`
  vs. `"compras-gov"`), quebrando a busca e o agrupamento por tag na
  interface do Airflow.
- **Perda da utilidade original das tags**: tags nativas do Airflow existem
  para busca e organização visual na interface — sem uma convenção mínima,
  esse valor se perde à medida que mais DAGs são adicionadas ao monorepo.

Este ADR adapta ao Airflow as regras gerais de nomenclatura do *Padrão de
Arquitetura de Dados — MGI/SEGES/CDATA* (v3.0) — minúsculas, dígitos e
underscore apenas — e o princípio de identificar objetos por dimensões
fixas (produto, camada, domínio) usado naquele documento para nomear
catálogos, schemas e pipelines.

## Decisão

Toda DAG do monorepo declara tags nativas (`tags=`) seguindo um vocabulário
fixo de dimensões, cada uma opcionalmente presente conforme a natureza da
DAG:

| Dimensão | Obrigatória? | Exemplo |
|---|---|---|
| `sistema:{sistema_origem}` | Sim | `sistema:compras_gov` |
| `orgao:{orgao}` | Sim quando a DAG for específica de um órgão (ver [ADR-0004](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)) | `orgao:mir` |
| `camada:{camada}` | Recomendada para DAGs de transformação/publicação | `camada:silver` (ver [ADR-0006](./0006-arquitetura-medallion.md)) |
| `dominio:{dominio}` | Recomendada | `dominio:almoxarifado` |

- Cada tag segue o formato `{dimensao}:{valor}`, com `{valor}` em
  `snake_case`, apenas minúsculas, dígitos e underscore — sem espaços,
  hífens ou acentos.
- O prefixo de dimensão (`sistema:`, `orgao:`, `camada:`, `dominio:`) é
  obrigatório mesmo quando o valor pareceria autoexplicativo, para permitir
  filtrar por dimensão na interface do Airflow sem ambiguidade entre, por
  exemplo, um valor de `sistema` e um de `dominio` que coincidam.
- Tags são exclusivamente para busca/organização — nenhum mecanismo do
  framework (seleção de deployment, CI, etc.) depende do valor de uma tag,
  conforme já estabelecido no ADR-0005.

## Alternativas consideradas

### Alternativa A: Sem convenção formal (status quo)

- Descrição: cada autor usa tags livres, sem vocabulário ou formato fixo.
- Prós: nenhuma curva de aprendizado adicional.
- Contras: é o cenário que motiva esta decisão — tags livres perdem
  utilidade de busca/organização à medida que o número de DAGs cresce.

### Alternativa B: Tag única de órgão (reaproveitar o padrão antigo do ADR-0005)

- Descrição: usar apenas uma tag por DAG, identificando o órgão/projeto —
  reaproveitando o espírito da abordagem por `DAG_TAGS` já rejeitada como
  mecanismo de seleção no ADR-0005, mas agora só para organização visual.
- Prós: mais simples de aplicar — uma única tag por DAG.
- Contras: perde a capacidade de filtrar por sistema, camada ou domínio na
  interface do Airflow, que são dimensões de busca tão úteis quanto órgão,
  especialmente em um monorepo com múltiplos sistemas por órgão.

### Vocabulário fixo de dimensões — decisão proposta

- Descrição: tags no formato `{dimensao}:{valor}`, cobrindo sistema, órgão
  (quando aplicável), camada e domínio.
- Por que foi escolhida: preserva a utilidade original das tags nativas do
  Airflow (busca e organização) sem reintroduzir tags como mecanismo de
  seleção de deployment — papel que já pertence exclusivamente ao
  `dag_selector` do ADR-0005 — e cobre as dimensões de busca mais
  relevantes para um monorepo multi-sistema e multi-órgão.

## Tradeoffs

### Vantagens

- **[Alto impacto]** Restaura a utilidade original das tags nativas do
  Airflow (busca e organização na interface) sem acoplá-las de volta a
  nenhum mecanismo de seleção de deployment.
- **[Médio impacto]** Vocabulário fixo de dimensões (sistema, órgão,
  camada, domínio) permite filtrar DAGs na interface por qualquer uma
  dessas dimensões, cobrindo os casos de busca mais comuns.
- **[Médio impacto]** Formato `{dimensao}:{valor}` evita ambiguidade entre
  tags de dimensões diferentes que, por coincidência, teriam o mesmo texto.
- **[Baixo impacto]** Reaproveita regras de nomenclatura já estabelecidas
  (minúsculas, underscore), sem introduzir uma convenção nova e
  desconectada do resto do framework.

### Desvantagens

- **[Médio impacto]** Exige disciplina de autoria: nada impede, sem
  verificação automática, que uma DAG seja criada com tags fora do
  vocabulário ou do formato definido.
- **[Baixo impacto]** Tags com prefixo de dimensão (`sistema:`, `orgao:`)
  são mais verbosas que tags simples de uma palavra.
- **[Baixo impacto]** Não define o vocabulário de valores válidos por
  dimensão (ex.: lista de sistemas ou domínios conhecidos) — cada projeto
  ainda decide os valores concretos, dentro do formato.

### Avaliação

Os ganhos superam os custos: um vocabulário fixo de dimensões é uma
convenção de baixo custo de adoção (tags continuam sendo apenas texto no
parâmetro `tags=`) que devolve às tags nativas do Airflow a utilidade de
busca que a remoção do mecanismo de seleção por tags (ADR-0005) não afeta.
O principal risco ativo — ausência de verificação automática do formato —
é aceitável enquanto o volume de DAGs for pequeno, mas deve ser mitigado
com lint assim que o framework tiver mais contribuidores externos.

## Consequências

- **Positivas**: tags nativas do Airflow voltam a ser úteis para busca e
  organização na interface, com um vocabulário previsível de dimensões
  (sistema, órgão, camada, domínio).
- **Negativas**: exige disciplina de autoria sem garantia automática de
  conformidade até que uma verificação estática seja implementada.
- **Ações decorrentes**:
  - Adicionar verificação estática (lint/teste do framework) que valide o
    formato `{dimensao}:{valor}` e o vocabulário de dimensões permitido.
  - Documentar, em um guia de contribuição, exemplos de tags por tipo de
    DAG (ingestão, transformação, publicação).

## Referências

- *Padrão de Arquitetura de Dados — MGI/SEGES/CDATA*, v3.0 (documento
  interno de referência, ambiente DEV).
- [ADR-0004 — Monorepo como estratégia de organização de código](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)
- [ADR-0005 — Seleção de DAGs por arquivo `dag_selector` antes do parsing](./0005-selecao-de-dags-por-dag-selector-antes-do-parsing.md)
- [ADR-0006 — Arquitetura medallion (bronze/silver/gold)](./0006-arquitetura-medallion.md)
- [Estrutura de ADRs do repositório](./README.md)
