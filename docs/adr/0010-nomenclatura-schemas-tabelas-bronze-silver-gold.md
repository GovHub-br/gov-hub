# ADR-0010: Padrão de nomenclatura de schemas e tabelas bronze/silver/gold

- **Status**: Proposto
- **Data**: 2026-07-15
- **Autores**: João Egewarth
- **Revisores**: -

## Introdução ao problema

O [ADR-0006](./0006-arquitetura-medallion.md) define as camadas Bronze,
Silver e Gold, e o [ADR-0009](./0009-nomenclatura-pastas-arquivos-dbt.md)
organiza os modelos dbt que as materializam. Nenhum dos dois define, porém,
o nome do **schema e da tabela** efetivamente criados no banco de dados
([ADR-0002](./0002-dbt-como-ferramenta-de-transformacao-de-dados.md) já
estabelece PostgreSQL como banco alvo) — decisão que afeta diretamente
quem consulta o banco fora do dbt (ex.: via `psql`, ferramentas de BI ou
outras aplicações).

Sem uma convenção única:

- **Camada de um objeto não é visível pelo nome**: sem um identificador de
  camada no nome do schema, alguém consultando o banco diretamente não
  consegue distinguir uma tabela Bronze de uma Gold sem conhecimento prévio
  do domínio.
- **Ordenação alfabética não reflete o fluxo de dados**: schemas nomeados
  apenas `bronze_x`, `gold_y`, `silver_z` aparecem em ferramentas que listam
  schemas em ordem alfabética (`psql \dn`, clientes de banco genéricos) em
  ordem alfabética pura — `bronze` < `gold` < `silver` — que não corresponde
  à ordem real do fluxo (bronze → silver → gold).

Este ADR adota diretamente o padrão de nomenclatura de schemas e tabelas do
*[Padrão de Arquitetura de Dados — MGI/SEGES/CDATA](./arquitetura_dados_mgi.pdf)*
(v3.0), adaptando-o de
Databricks Unity Catalog (catálogo por produto + schema por camada) para
PostgreSQL (schema por camada e domínio, dentro do banco de cada órgão).

## Decisão

Cada schema segue o padrão `{prefixo_camada}_{escopo}`, com prefixo
numérico fixo por camada — o mesmo mecanismo usado pelo documento de
referência para garantir que a ordenação alfabética de schemas reflita o
fluxo real de dados:

| Prefixo | Camada | Padrão do schema | Exemplo |
|---|---|---|---|
| `000` | Referências | `000_ref_{escopo}` | `000_ref_global` |
| `001` | Bronze | `001_bnz_{sistema_origem}` | `001_bnz_siafem` |
| `002` | Silver | `002_slv_{dominio}` | `002_slv_material_consumo` |
| `003` | Gold | `003_gld_{produto_dados}` | `003_gld_indicadores` |

- Schema de Bronze é nomeado por **sistema de origem** (a mesma fonte usada
  pelas DAGs de ingestão, [ADR-0007](./0007-nomenclatura-pastas-dags-ingestao.md)),
  preservando a ideia de fidelidade à fonte.
- Schemas de Silver e Gold são nomeados por **domínio temático** e
  **produto de dados**, respectivamente, na mesma lógica já adotada para
  pastas de modelos dbt no ADR-0009.
- Schema `000_ref_*` é reservado para entidades de referência
  compartilhadas dentro do banco de um mesmo órgão (ex.: tabelas mestras,
  taxonomias, classificações oficiais) — não confundir com código
  compartilhado entre órgãos, que é tratado pela estrutura de pastas do
  monorepo ([ADR-0004](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)),
  não por schema de banco.
- Tabelas seguem o padrão `{entidade}`, em `snake_case`, **sem prefixo de
  camada** — a camada já está identificada pelo schema, e repetir o
  prefixo no nome da tabela seria redundante (ex.: `siads.002_slv_material_consumo.itens`,
  não `siads.002_slv_material_consumo.slv_itens`).
- Views recebem o prefixo `vw_{entidade}_{escopo}`, reservado a objetos que
  expõem um subconjunto ou uma projeção específica de uma tabela.

### Regras gerais de nomenclatura

- Somente letras minúsculas (`a-z`), dígitos (`0-9`) e underscore (`_`).
- Proibido: espaços, hífens, acentos, cedilha ou outros caracteres
  especiais — mesma regra já aplicada a DAGs (ADR-0007) e modelos dbt
  (ADR-0009).
- Identificadores (schema, tabela, coluna) respeitam o limite de 63 bytes
  do PostgreSQL (`NAMEDATALEN`) — diferente do limite de 64 caracteres
  citado pelo documento de referência para objetos Databricks, por ser um
  limite físico do PostgreSQL, não uma convenção adotável.

## Alternativas consideradas

### Alternativa A: Sem convenção formal (status quo)

- Descrição: cada projeto nomeia schemas e tabelas livremente.
- Prós: nenhuma curva de aprendizado adicional.
- Contras: é o cenário que motiva esta decisão — camada de um objeto não é
  visível pelo nome, e a ordenação alfabética de schemas não reflete o
  fluxo de dados.

### Alternativa B: Prefixo textual sem numeração (`bronze_`, `silver_`, `gold_`)

- Descrição: usar o nome da camada por extenso como prefixo do schema
  (`bronze_siafem`, `silver_material_consumo`, `gold_indicadores`), sem
  prefixo numérico.
- Prós: mais legível que um prefixo numérico — não exige memorizar que
  `001` significa Bronze.
- Contras: não resolve o problema de ordenação alfabética levantado na
  introdução — `bronze_x` < `gold_y` < `silver_z` em ordem alfabética,
  ainda fora de ordem em relação ao fluxo real bronze → silver → gold.

### Prefixo numérico de camada — decisão proposta

- Descrição: `{prefixo_numerico}_{sigla_camada}_{escopo}`, replicando o
  padrão do documento de referência.
- Por que foi escolhida: é a única alternativa avaliada que resolve
  simultaneamente os dois problemas da introdução — camada visível pelo
  nome (via sigla) e ordenação alfabética alinhada ao fluxo real de dados
  (via prefixo numérico), sem exigir suporte de ferramenta além de
  ordenação alfabética simples.

## Tradeoffs

### Vantagens

- **[Alto impacto]** Ordenação alfabética de schemas em qualquer ferramenta
  (`psql \dn`, clientes de banco genéricos) reflete o fluxo real de dados —
  referências, depois bronze, silver e gold, nessa ordem — sem depender de
  suporte específico de ferramenta.
- **[Alto impacto]** Camada de um objeto é identificável só pelo nome do
  schema, mesmo para quem consulta o banco fora do dbt e sem conhecimento
  prévio do domínio.
- **[Médio impacto]** Reaproveita, com adaptação mínima, um padrão já
  validado em contexto de dados públicos brasileiros (MGI/SEGES/CDATA).
- **[Baixo impacto]** Nome de tabela sem prefixo de camada evita
  redundância com o schema, mantendo nomes de tabela mais curtos e
  legíveis.

### Desvantagens

- **[Médio impacto]** Prefixo numérico exige memorizar a associação entre
  número e camada (`001` = Bronze, `002` = Silver, `003` = Gold) até que
  isso se torne familiar para o time.
- **[Baixo impacto]** Renomear schemas já existentes no banco para seguir
  este padrão é uma migração com custo não trivial (exige `ALTER SCHEMA` ou
  recriação, e atualização de qualquer consumidor externo que referencie o
  nome atual).
- **[Baixo impacto]** Este ADR não define regras de qualidade ou critérios
  de promoção entre camadas — apenas nomenclatura; a lógica de quando um
  dado "sobe" de camada continua dependente do que já foi definido no
  ADR-0006.

### Avaliação

Os ganhos superam os custos: o prefixo numérico resolve de forma direta e
sem dependência de ferramenta os dois problemas centrais da introdução
(camada visível, ordenação alinhada ao fluxo), e o custo de memorizar a
associação número-camada é pago uma única vez pelo time, com retorno
recorrente toda vez que alguém precisa localizar um objeto pelo nome. O
custo de migração de schemas já existentes é real, mas pontual e não se
repete para schemas criados já com o padrão.

## Consequências

- **Positivas**: schemas e tabelas tornam-se autoexplicativos quanto à
  camada a que pertencem, com ordenação alfabética alinhada ao fluxo real
  de dados, mesmo para consultas fora do dbt.
- **Negativas**: schemas já existentes precisam ser migrados para o novo
  padrão, com custo de coordenação para consumidores externos que já
  referenciam os nomes atuais.
- **Ações decorrentes**:
  - Migrar schemas dbt já existentes no monorepo para o padrão
    `{prefixo}_{sigla_camada}_{escopo}` definido neste ADR, coordenando a
    mudança com consumidores externos ao dbt (BI, outras aplicações).
  - Configurar a geração de nome de schema no dbt (`generate_schema_name`)
    para produzir automaticamente o padrão definido aqui a partir da pasta
    de camada/domínio do ADR-0009.
  - Adicionar teste de contrato no CI que valide o padrão de nomenclatura
    de schemas e tabelas geradas pelos modelos dbt.

## Referências

- [Padrão de Arquitetura de Dados — MGI/SEGES/CDATA, v3.0](./arquitetura_dados_mgi.pdf)
  (documento interno de referência, ambiente DEV).
- [ADR-0002 — dbt como ferramenta de transformação de dados](./0002-dbt-como-ferramenta-de-transformacao-de-dados.md)
- [ADR-0004 — Monorepo como estratégia de organização de código](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)
- [ADR-0006 — Arquitetura medallion (bronze/silver/gold)](./0006-arquitetura-medallion.md)
- [ADR-0007 — Padrão de nomenclatura das pastas/arquivos de DAGs de ingestão](./0007-nomenclatura-pastas-dags-ingestao.md)
- [ADR-0009 — Padrão de nomenclatura das pastas/arquivos de projetos dbt](./0009-nomenclatura-pastas-arquivos-dbt.md)
- [Estrutura de ADRs do repositório](./README.md)
