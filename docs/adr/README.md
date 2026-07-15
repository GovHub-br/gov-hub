# Architecture Decision Records (ADRs)

Este diretório guarda as decisões arquiteturais e técnicas do `data-framework`,
o framework de engenharia de dados compartilhado por projetos de dados públicos
no Brasil (GovHub).

## Por que ADRs

Este repositório é herdado por múltiplos projetos. Decisões tomadas aqui se
propagam para todos os consumidores do framework, muitas vezes sem que os
times consumidores participem da discussão original. Um ADR registra o
contexto, as alternativas avaliadas e o racional de cada decisão, permitindo
que qualquer time — presente ou futuro — entenda *por que* o framework é como
é, não apenas *o que* ele faz.

Veja o racional completo e os benefícios deste processo em
[ADR-0000](./0000-por-que-adrs.md), baseado no
[guia de ADRs da AWS](https://docs.aws.amazon.com/pt_br/prescriptive-guidance/latest/architectural-decision-records/adr-process.html).

## Convenções

- **Numeração**: sequencial, com 4 dígitos.
  Ex.: `0003-govhub-como-framework-compartilhado-de-dados.md`.
- **Nome de arquivo**: `NNNN-titulo-em-kebab-case.md`.
- **Imutabilidade**: um ADR aceito não é editado retroativamente para mudar a
  decisão. Se a decisão muda, crie um novo ADR e marque o antigo como
  `Superseded by ADR-XXXX`.
- **Idioma**: português, salvo quando o termo técnico for mais claro em
  inglês (ex.: nomes de ferramentas, siglas do ecossistema de dados).
- **Template**: todo ADR novo parte de [`template.md`](./template.md).

## Ciclo de vida (Status)

| Status | Significado |
|---|---|
| `Backlog` | Necessidade de decisão identificada e número reservado, mas ADR ainda não escrito. |
| `Proposto` | Em discussão, ainda não decidido. |
| `Aceito` | Decisão tomada e revisada por pelo menos 1 par. |
| `Rejeitado` | Proposta avaliada e descartada. |
| `Substituído por ADR-XXXX` | Decisão superada por um ADR mais recente. |
| `Depreciado` | Decisão não é mais relevante (contexto desapareceu). |

## Como propor um novo ADR

1. Copie `template.md` para `NNNN-titulo-em-kebab-case.md` (próximo número
   disponível) — ou, se já existir um arquivo stub com status `Backlog` para
   o tema, parta dele em vez de criar um novo número.
2. Preencha todas as seções — especialmente **Alternativas** e **Tradeoffs**,
   que são obrigatórias mesmo quando a decisão parece óbvia.
3. Abra um PR. O ADR deve ser revisado como qualquer mudança de arquitetura.
4. Ao ser aceito, atualize o status e adicione o ADR ao índice abaixo.

### Arquivos `Backlog`

Um ADR com status `Backlog` reserva um número para um tema já identificado
como carente de decisão, mas ainda não escrito — útil para mapear a dívida
de documentação sem bloquear a numeração de ADRs que já estão prontos. Ele
contém só título, status e um resumo de escopo; quem for escrevê-lo de fato
substitui o corpo pelo conteúdo de `template.md`, preenchido normalmente.

## Índice

| ADR | Título | Status |
|---|---|---|
| [0000](./0000-por-que-adrs.md) | Por que ADRs | Proposto |
| [0001](./0001-airflow-como-orquestrador-de-fluxos-de-dados.md) | Apache Airflow como orquestrador de fluxos de dados | Proposto |
| [0002](./0002-dbt-como-ferramenta-de-transformacao-de-dados.md) | dbt como ferramenta de transformação de dados | Proposto |
| [0003](./0003-govhub-como-framework-compartilhado-de-dados.md) | GovHub como um framework compartilhado de dados | Proposto |
| [0004](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md) | Monorepo como estratégia de organização de código | Proposto |
| [0005](./0005-selecao-de-dags-por-dag-selector-antes-do-parsing.md) | Seleção de DAGs por arquivo `dag_selector` antes do parsing | Proposto |
| [0006](./0006-arquitetura-medallion.md) | Arquitetura medallion (bronze/silver/gold) | Proposto |
| [0007](./0007-nomenclatura-pastas-dags-ingestao.md) | Padrão de nomenclatura das pastas/arquivos de DAGs de ingestão | Proposto |
| [0008](./0008-padrao-uso-tags-nomenclatura.md) | Padrão de uso de tags/nomenclatura no Airflow | Proposto |
| [0009](./0009-nomenclatura-pastas-arquivos-dbt.md) | Padrão de nomenclatura das pastas/arquivos de projetos dbt | Proposto |
| [0010](./0010-nomenclatura-schemas-tabelas-bronze-silver-gold.md) | Padrão de nomenclatura de schemas e tabelas bronze/silver/gold | Proposto |
| [0011](./0011-arquitetura-agnostica-motor-processamento.md) | Arquitetura agnóstica a motor de processamento de dados | Backlog |
| [0012](./0012-ingestao-object-storage-vs-database.md) | Ingestão em object storage em vez de banco diretamente | Backlog |
| [0013](./0013-padrao-documentacao-metadados-tabelas.md) | Padrão de documentação de metadados de tabelas | Backlog |
| [0014](./0014-padrao-documentacao-dags-dbt-openmetadata.md) | Padrão de documentação de DAGs/dbt para envio ao OpenMetadata | Backlog |
