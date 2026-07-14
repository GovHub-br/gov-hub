# ADR-0000: Por que ADRs

- **Status**: Aceito
- **Data**: 2026-07-14
- **Autores**: Matheus Lacerda
- **Revisores**: -

## Introdução ao problema

O `data-framework` é herdado por múltiplos projetos de dados públicos no
Brasil. Decisões arquiteturais e técnicas tomadas aqui — estrutura, padrões
de ingestão/transformação, escolha de bibliotecas, requisitos não funcionais
como segurança e conformidade — se propagam para todos os projetos
consumidores, muitas vezes para times que não participaram da discussão
original.

Sem um processo formal de registro de decisões, isso gera problemas
conhecidos em projetos de longa duração e múltiplos times:

- **Perda de conhecimento institucional**: o motivo por trás de uma decisão
  se perde assim que a pessoa que a tomou sai do time ou do projeto, restando
  apenas o código — que mostra o *quê*, nunca o *porquê*.
- **Decisões revertidas sem contexto**: arquitetos ou times que não
  participaram da decisão original a revertem ou contornam sem entender as
  restrições que a motivaram, reintroduzindo problemas já resolvidos.
- **Falta de rastreabilidade**: não há vínculo claro entre um requisito
  (ex.: conformidade com LGPD) e a implementação que o atende, dificultando
  auditorias e revisões.
- **Onboarding lento**: novos membros — e novos times que adotam o
  framework — não têm um histórico consultável do que já foi decidido e por
  quê, e acabam repetindo perguntas e discussões já encerradas.
- **Discussões repetidas**: tópicos já avaliados e rejeitados voltam à tona
  periodicamente, consumindo tempo do time sem necessidade, pois o motivo da
  rejeição não ficou registrado.
- **Inconsistência entre revisões de código**: sem um registro objetivo de
  decisões, revisores de PR não têm uma referência comum para apontar quando
  uma mudança viola um padrão já estabelecido.

Esses problemas se agravam no contexto do GovHub especificamente porque o
framework tem múltiplos consumidores desacoplados no tempo: um projeto pode
adotar o framework anos depois de uma decisão ter sido tomada, sem qualquer
contato com quem a tomou.

## Decisão

O `data-framework` adota **Architectural Decision Records (ADRs)** como
processo formal de registro de decisões arquiteturais e técnicas, seguindo
as práticas descritas no
[guia da AWS sobre o processo de ADR](https://docs.aws.amazon.com/pt_br/prescriptive-guidance/latest/architectural-decision-records/adr-process.html):

- **O que gera um ADR**: decisões que afetam estrutura (ex.: padrões como
  microsserviços), requisitos não funcionais (segurança, disponibilidade,
  tolerância a falhas), dependências entre componentes, interfaces/contratos
  publicados, ou técnicas de construção (bibliotecas, frameworks,
  ferramentas, processos).
- **Conteúdo mínimo**: todo ADR registra contexto, a decisão em si e suas
  consequências — e, nas convenções deste repositório (ver
  [template.md](./template.md)), também alternativas consideradas e
  tradeoffs explícitos.
- **Propriedade**: qualquer pessoa pode propor um ADR, mas cada ADR tem um
  responsável (autor) que conduz a revisão e mantém o documento até ser
  aceito ou rejeitado.
- **Ciclo de vida**: `Proposto` → `Aceito` ou `Rejeitado` → eventualmente
  `Substituído por ADR-XXXX`, conforme já descrito em [README.md](./README.md).
- **Imutabilidade**: um ADR aceito não é reescrito para mudar a decisão.
  Mudanças de rumo exigem um novo ADR que substitui o anterior, preservando
  o histórico completo — inclusive o de decisões rejeitadas, cujo motivo de
  rejeição também é documentado para evitar discussões repetidas.
- **Uso em revisão de código**: um ADR aceito é referência objetiva em code
  review — se uma mudança contraria um ADR vigente, o revisor aponta o link
  do ADR; a mudança é ajustada ou um novo ADR é proposto para alterar a
  decisão.

## Alternativas consideradas

### Não documentar decisões arquiteturais (status quo)

- Descrição: decisões continuam sendo tomadas em discussões pontuais (PRs,
  chamadas, mensagens), sem registro centralizado.
- Prós: nenhum overhead de processo; decisões são tomadas mais rápido no
  momento.
- Contras: é exatamente o cenário que gera os problemas descritos na
  introdução — perda de contexto, decisões revertidas, discussões repetidas.
  Inaceitável dado que o framework é herdado por múltiplos projetos ao longo
  do tempo.

### Documentação de arquitetura tradicional (wiki, documento único de arquitetura)

- Descrição: manter um documento vivo (ex.: wiki ou arquivo único) descrevendo
  a arquitetura atual do framework.
- Prós: visão consolidada e atual do sistema em um único lugar.
- Contras: documentos de arquitetura tradicionais descrevem o *estado atual*,
  não o *histórico de decisões* — é fácil perder o porquê de uma escolha
  quando o documento é atualizado ou reescrito. Não há imutabilidade nem
  rastreabilidade de quando e por que uma decisão mudou.

### ADRs (decisão proposta)

- Descrição: um registro imutável por decisão, com contexto, alternativas,
  tradeoffs e consequências, seguindo um ciclo de vida formal de revisão e
  substituição.
- Por que foi escolhida: é a única alternativa que preserva o histórico
  completo de decisões — incluindo as rejeitadas — e força o registro
  explícito do "porquê", que é o que efetivamente falta nos outros formatos.

## Tradeoffs

| Dimensão | Ganho | Custo/Risco |
|---|---|---|
| Preservação de contexto | Motivo de cada decisão fica registrado e consultável indefinidamente | Exige disciplina para escrever ADRs mesmo quando a decisão parece "óbvia" no momento |
| Velocidade de decisão | — | Processo de revisão (leitura, comentários, aprovação) adiciona latência a decisões que antes eram informais |
| Onboarding de novos times/membros | Histórico legível reduz tempo de ramp-up e perguntas repetidas | ADRs desatualizados ou mal escritos podem confundir mais do que ajudar — exige manutenção do índice |
| Consistência arquitetural | Referência objetiva em code review, reduzindo debates subjetivos | Um ADR mal escopado pode engessar decisões que deveriam ser reavaliadas com mais frequência |
| Rastreabilidade e auditoria | Vínculo claro entre requisitos (ex.: LGPD) e decisões técnicas que os atendem | Overhead de manter ADRs sincronizados com a realidade do código ao longo do tempo |

## Consequências

- **Positivas**: o framework passa a ter um log histórico de decisões
  consultável por qualquer projeto consumidor, presente ou futuro. Revisões
  de código e discussões de arquitetura passam a ter uma referência objetiva
  em vez de depender da memória de quem participou da decisão original.
- **Negativas**: toda decisão de escopo arquitetural (estrutura, requisitos
  não funcionais, dependências, interfaces, técnicas de construção) passa a
  exigir a escrita de um ADR antes de ser considerada definitiva, o que
  adiciona um passo ao processo de decisão que antes podia ser informal.
- **Ações decorrentes**:
  - Toda decisão futura dentro do escopo definido nesta ADR deve ser
    registrada como um novo ADR, seguindo [template.md](./template.md).
  - PRs que implementam uma decisão arquitetural devem referenciar o ADR
    correspondente na descrição.
  - Revisores de código devem apontar ADRs vigentes quando uma mudança os
    contraria, propondo atualização do código ou um novo ADR substituto.

## Referências

- [AWS Prescriptive Guidance — Architectural Decision Records: ADR process](https://docs.aws.amazon.com/pt_br/prescriptive-guidance/latest/architectural-decision-records/adr-process.html)
- [Estrutura de ADRs do repositório](./README.md)
- [Template de ADR](./template.md)
