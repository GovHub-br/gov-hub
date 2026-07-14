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
| `Proposto` | Em discussão, ainda não decidido. |
| `Aceito` | Decisão tomada e revisada por pelo menos 1 par. |
| `Rejeitado` | Proposta avaliada e descartada. |
| `Substituído por ADR-XXXX` | Decisão superada por um ADR mais recente. |
| `Depreciado` | Decisão não é mais relevante (contexto desapareceu). |

## Como propor um novo ADR

1. Copie `template.md` para `NNNN-titulo-em-kebab-case.md` (próximo número
   disponível).
2. Preencha todas as seções — especialmente **Alternativas** e **Tradeoffs**,
   que são obrigatórias mesmo quando a decisão parece óbvia.
3. Abra um PR. O ADR deve ser revisado como qualquer mudança de arquitetura.
4. Ao ser aceito, atualize o status e adicione o ADR ao índice abaixo.

## Índice

| ADR | Título | Status |
|---|---|---|
| [0000](./0000-por-que-adrs.md) | Por que ADRs | Proposto |
| [0001](./0001-airflow-como-orquestrador-de-fluxos-de-dados.md) | Apache Airflow como orquestrador de fluxos de dados | Proposto |
| [0003](./0003-govhub-como-framework-compartilhado-de-dados.md) | GovHub como um framework compartilhado de dados | Proposto |
