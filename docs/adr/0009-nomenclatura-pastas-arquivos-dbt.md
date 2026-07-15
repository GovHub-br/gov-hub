# ADR-0009: Padrão de nomenclatura das pastas/arquivos de projetos dbt

- **Status**: Proposto
- **Data**: 2026-07-15
- **Autores**: João Egewarth
- **Revisores**: -

## Introdução ao problema

O [ADR-0002](./0002-dbt-como-ferramenta-de-transformacao-de-dados.md) adota
dbt como ferramenta de transformação, e o
[ADR-0004](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)
define que os modelos dbt seguem a mesma lógica de sistema/órgão das DAGs de
ingestão: `dbt/<sistema>/` para modelos compartilhados entre órgãos (como
pacote dbt local), `dbt/<sistema>/<orgao>/` para modelos de um órgão
específico dentro de um pacote compartilhado, e `dbt/<orgao>/` para o
projeto dbt do próprio órgão (que importa os pacotes de que depende e
contém os modelos de sistemas internos). Nenhum dos dois define, porém, como
organizar as **pastas e arquivos dentro** de cada `models/` — hoje isso fica
a critério de cada projeto/pacote, e a comunidade dbt tem pelo menos duas
convenções concorrentes conhecidas (camadas staging/intermediate/marts vs.
camadas por domínio de negócio), nenhuma alinhada por padrão ao vocabulário
de camadas já adotado pelo framework.

Sem uma convenção única:

- **Modelos ficam difíceis de localizar**: sem uma estrutura de pastas
  previsível, encontrar o modelo dbt responsável por uma tabela Silver de um
  domínio específico exige buscar pelo repositório inteiro.
- **Divergência do vocabulário de camadas já adotado**: usar convenções
  genéricas da comunidade dbt (`staging/`, `intermediate/`, `marts/`) sem
  conexão com o vocabulário bronze/silver/gold já definido no
  [ADR-0006](./0006-arquitetura-medallion.md) obriga o time a manter dois
  vocabulários simultâneos para o mesmo conceito.

Este ADR adapta ao projeto dbt as convenções de nomenclatura de objetos do
*[Padrão de Arquitetura de Dados — MGI/SEGES/CDATA](./arquitetura_dados_mgi.pdf)*
(v3.0) — em particular,
a regra de nomear tabelas pela entidade em `snake_case` sem prefixo — à
estrutura de camadas já definida no ADR-0006.

## Decisão

Dentro de qualquer `models/` do monorepo — seja de um pacote
`dbt/<sistema>/`, de uma subpasta de órgão dentro dele
(`dbt/<sistema>/<orgao>/`), seja do projeto `dbt/<orgao>/` — os modelos são
organizados por **camada** (alinhada ao ADR-0006) e, dentro de cada camada,
por **domínio** ou **sistema de origem**:

```text
dbt/<sistema>/                    # pacote dbt compartilhado (ver ADR-0004)
  dbt_project.yml
  models/
    bronze/
      {entidade}.sql               # sistema já implícito no próprio pacote
    silver/
      <dominio>/
        {entidade}.sql
    gold/
      <produto_dados>/
        {entidade}.sql
  <orgao>/                        # modelos do pacote específicos de um órgão
    models/
      bronze/
        {entidade}.sql
      silver/
        <dominio>/
          {entidade}.sql
  macros/
  seeds/
  snapshots/

dbt/<orgao>/                       # projeto dbt do órgão
  dbt_project.yml
  packages.yml                    # importa os pacotes de dbt/<sistema>/ que este órgão consome
  models/
    bronze/
      <sistema_origem>/           # necessário aqui: um projeto de órgão pode ter vários sistemas internos
        {entidade}.sql
    silver/
      <dominio>/
        {entidade}.sql
    gold/
      <produto_dados>/
        {entidade}.sql
  macros/
  seeds/
  snapshots/
```

- Pasta de Bronze é organizada por **sistema de origem** apenas quando o
  `models/` em questão pode conter dados de mais de um sistema — o caso do
  projeto de um órgão (`dbt/<orgao>/`), que reúne os sistemas internos desse
  órgão. Dentro de um pacote `dbt/<sistema>/` (e de sua subpasta de órgão),
  o sistema já está implícito no próprio pacote, então a subpasta de
  sistema é omitida.
- Pastas de Silver e Gold são sempre organizadas por **domínio temático** e
  **produto de dados**, respectivamente, refletindo que essas camadas já
  aplicam alguma forma de modelagem além da simples cópia da fonte — essa
  regra não muda entre pacote e projeto de órgão.
- Nome do arquivo de modelo (`{entidade}.sql`) é o nome da entidade em
  `snake_case`, sem prefixo de camada — a camada já está implícita na
  pasta em que o arquivo vive, evitando repetir a informação no nome do
  arquivo (diferente do schema, que carrega o prefixo de camada — ver
  decisão complementar de nomenclatura de schemas/tabelas).
- `macros/`, `seeds/` e `snapshots/` seguem a convenção padrão do próprio
  dbt, sem necessidade de subdivisão adicional por este ADR.

### Regras gerais de nomenclatura

- Somente letras minúsculas (`a-z`), dígitos (`0-9`) e underscore (`_`).
- Proibido: espaços, hífens, acentos, cedilha ou outros caracteres
  especiais — mesma regra já aplicada a DAGs no ADR-0007.
- Nome de arquivo de modelo dbt deve coincidir com o nome da tabela/view
  materializada por ele, para que localizar o modelo a partir do nome do
  objeto no banco seja imediato.

## Alternativas consideradas

### Alternativa A: Sem convenção formal (status quo)

- Descrição: cada projeto dbt organiza `models/` livremente.
- Prós: nenhuma curva de aprendizado adicional; flexibilidade total por
  projeto.
- Contras: é o cenário que motiva esta decisão — dificulta localizar
  modelos entre projetos consumidores diferentes, já que cada um pode
  organizar `models/` de um jeito distinto.

### Alternativa B: Convenção genérica da comunidade dbt (staging/intermediate/marts)

- Descrição: adotar a convenção popular na comunidade dbt de organizar
  `models/` em `staging/`, `intermediate/` e `marts/`.
- Prós: convenção amplamente documentada e reconhecida por quem já trabalha
  com dbt fora do contexto deste framework.
- Contras: introduz um segundo vocabulário de camadas (staging/
  intermediate/marts) paralelo ao já adotado pelo framework
  (bronze/silver/gold, ADR-0006), obrigando tradução mental constante entre
  os dois e divergindo do vocabulário usado nas DAGs de ingestão e,
  presumivelmente, nos schemas do banco.

### Pastas por camada e domínio, alinhadas ao ADR-0006 — decisão proposta

- Descrição: `models/{camada}/{dominio_ou_sistema}/{entidade}.sql`,
  reaproveitando o vocabulário de camadas já definido para o framework.
- Por que foi escolhida: mantém um único vocabulário de camadas em todo o
  framework (DAGs, modelos dbt e, futuramente, schemas do banco), evitando
  que engenheiros precisem traduzir entre convenções diferentes ao
  transitar de uma DAG de ingestão para o modelo dbt que a consome.

## Tradeoffs

### Vantagens

- **[Alto impacto]** Um único vocabulário de camadas (bronze/silver/gold)
  é usado consistentemente entre DAGs de ingestão e modelos dbt, eliminando
  tradução mental entre convenções.
- **[Médio impacto]** Localizar o modelo responsável por uma entidade
  específica é previsível a partir da camada e do domínio/sistema, sem
  precisar buscar pelo repositório inteiro.
- **[Médio impacto]** Nome de arquivo igual ao nome do objeto materializado
  facilita ir do banco de dados até o código-fonte do modelo e vice-versa.
- **[Baixo impacto]** Reaproveita regras de nomenclatura já estabelecidas
  para DAGs (ADR-0007), reduzindo o número de convenções distintas que um
  contribuidor precisa aprender.

### Desvantagens

- **[Médio impacto]** Diverge da convenção mais popular da comunidade dbt
  (staging/intermediate/marts), o que pode gerar estranhamento inicial em
  quem já tem experiência prévia com dbt fora deste framework.
- **[Baixo impacto]** Organizar Bronze por sistema de origem e Silver/Gold
  por domínio significa que a mesma entidade pode "mudar de pasta-pai"
  conforme sobe de camada — previsível, mas exige entender a regra para não
  estranhar a diferença de critério entre Bronze e as demais camadas.
- **[Baixo impacto]** Não resolve, por si só, a nomenclatura do schema/
  tabela materializada no banco — depende de decisão complementar.

### Avaliação

Os ganhos superam os custos: manter um único vocabulário de camadas em todo
o framework — em vez de adotar a convenção genérica da comunidade dbt —
reduz a carga cognitiva de transitar entre DAGs de ingestão e modelos de
transformação, que é o problema central motivador desta decisão. A
divergência da convenção popular da comunidade dbt é um custo aceitável,
pago uma única vez no onboarding de quem já conhece dbt por fora.

## Consequências

- **Positivas**: modelos dbt tornam-se localizáveis a partir da camada e do
  domínio/sistema de origem, com o mesmo vocabulário já usado nas DAGs de
  ingestão.
- **Negativas**: contribuidores com experiência prévia em dbt precisam
  desaprender a convenção staging/intermediate/marts para adotar
  bronze/silver/gold neste framework.
- **Ações decorrentes**:
  - Migrar projetos dbt já existentes no monorepo (`dbt/ipea/`,
    `dbt/mir/`) para a estrutura de pastas por camada/domínio definida
    neste ADR, incluindo a extração de modelos hoje duplicados entre
    órgãos para pacotes `dbt/<sistema>/` conforme o ADR-0004.
  - Documentar o formato de `packages.yml` usado pelos projetos de órgão
    para importar pacotes locais de `dbt/<sistema>/`.
  - Adicionar verificação estática (lint/teste do framework) que valide a
    estrutura de pastas e a correspondência entre nome de arquivo e objeto
    materializado.
  - Documentar a decisão de nomenclatura de schemas/tabelas no banco como
    complementar a este ADR.

## Referências

- [Padrão de Arquitetura de Dados — MGI/SEGES/CDATA, v3.0](./arquitetura_dados_mgi.pdf)
  (documento interno de referência, ambiente DEV).
- [ADR-0002 — dbt como ferramenta de transformação de dados](./0002-dbt-como-ferramenta-de-transformacao-de-dados.md)
- [ADR-0004 — Monorepo como estratégia de organização de código](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)
- [ADR-0006 — Arquitetura medallion (bronze/silver/gold)](./0006-arquitetura-medallion.md)
- [ADR-0007 — Padrão de nomenclatura das pastas/arquivos de DAGs de ingestão](./0007-nomenclatura-pastas-dags-ingestao.md)
- [Estrutura de ADRs do repositório](./README.md)
