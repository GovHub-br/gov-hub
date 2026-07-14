# ADR-0003: GovHub como um framework compartilhado de dados

- **Status**: Proposto
- **Data**: 2026-07-14
- **Autores**: Matheus Lacerda
- **Revisores**: -

## Introdução ao problema

Projetos de dados públicos no Brasil vêm sendo construídos de forma
independente entre si, cada um implementando sua própria stack de ingestão,
transformação, qualidade e publicação de dados. Isso gera quatro problemas
recorrentes:

- **Duplicação de código**: lógica de ingestão, ETL e validação de qualidade
  de dados é reimplementada em cada projeto, mesmo quando o problema resolvido
  é essencialmente o mesmo (extrair de fontes públicas, tratar, publicar).
- **Falta de padronização**: cada projeto adota stacks, convenções e
  estruturas de repositório diferentes. Isso dificulta a manutenção, encarece
  a contratação e transferência de conhecimento entre times, e torna difícil
  para alguém que já trabalhou em um projeto GovHub contribuir rapidamente em
  outro.
- **Governança e conformidade**: dados públicos no Brasil estão sujeitos à
  LGPD e a políticas de dados abertos. Sem um framework comum, práticas de
  segurança, anonimização e publicação de dados ficam sujeitas ao critério
  individual de cada projeto, criando risco de inconsistência e não
  conformidade.
- **Custo de manutenção e onboarding**: cada novo projeto público reinicia do
  zero — repositório, CI, estrutura de pastas, decisões de arquitetura — o que
  eleva o custo de start-up de cada iniciativa e a curva de aprendizado para
  novos times.

Essa decisão precisa ser tomada agora porque o `data-framework` está sendo
criado com a intenção explícita de ser herdado por múltiplos projetos futuros.
As decisões tomadas aqui — incluindo a decisão de existir como framework —
moldam a forma como todos os projetos consumidores serão estruturados,
mantidos e evoluídos.

## Decisão

O `data-framework` (GovHub) será construído e mantido como um **framework
compartilhado e opinativo**, não como uma biblioteca de utilitários nem como
um conjunto de exemplos por projeto. Projetos de dados públicos herdam deste
framework a estrutura de repositório, as convenções de ingestão/transformação
/publicação de dados e as práticas de governança e conformidade, em vez de
reimplementá-las individualmente.

Isso implica que:

- Mudanças no framework se propagam (via versionamento) para todos os
  projetos consumidores.
- O framework impõe estrutura e convenções, não apenas oferece funções
  reutilizáveis — a divergência de um projeto em relação ao padrão do
  framework deve ser exceção justificada, não regra.
- Decisões de arquitetura, segurança e conformidade (ex.: tratamento de dados
  sob LGPD) são centralizadas aqui e não delegadas a cada projeto.

## Alternativas consideradas

### Alternativa A: Cada projeto mantém sua própria stack (status quo)

- Descrição: nenhum framework ou padrão comum; cada time decide e implementa
  sua stack de dados isoladamente.
- Prós: máxima liberdade e autonomia por projeto; nenhuma dependência
  externa para gerenciar.
- Contras: perpetua a duplicação de código, a falta de padronização e a
  inconsistência de governança já observadas hoje. Cada novo projeto público
  paga novamente o custo de decisões já resolvidas em outro lugar.

### Alternativa B: Biblioteca compartilhada (não framework)

- Descrição: extrair apenas utilitários e componentes comuns (ex.: clientes
  de conectores, funções de validação) como bibliotecas importáveis, sem
  impor estrutura de projeto, arquitetura ou convenções de organização.
- Prós: menor acoplamento — projetos usam só o que precisam, sem herdar
  decisões arquiteturais; adoção incremental é mais fácil.
- Contras: não resolve a falta de padronização estrutural nem centraliza
  governança/conformidade de forma consistente, já que cada projeto ainda
  decide como organizar e conectar essas bibliotecas. O problema de
  onboarding e curva de aprendizado entre projetos permanece, pois a
  "forma" de cada projeto continua distinta.

### Framework compartilhado — decisão proposta

- Descrição: um framework próprio e opinativo, herdado por todos os
  projetos de dados públicos, cobrindo estrutura de repositório, ingestão,
  transformação, qualidade e publicação de dados, além de práticas de
  governança e conformidade.
- Por que foi escolhida: é a única alternativa que endereça diretamente os
  quatro problemas identificados na introdução — duplicação, padronização,
  governança e custo de onboarding — de forma sistêmica, e não apenas
  parcial.

## Tradeoffs

| Dimensão | Ganho | Custo/Risco |
|---|---|---|
| Duplicação de código | Lógica de ingestão/ETL/qualidade escrita uma vez e reutilizada por todos os projetos | Bugs ou limitações no framework afetam todos os projetos consumidores simultaneamente |
| Padronização | Onboarding mais rápido entre projetos; conhecimento transferível entre times | Menos flexibilidade para projetos com necessidades genuinamente atípicas |
| Governança e conformidade (LGPD, dados abertos) | Práticas de segurança e publicação de dados centralizadas e auditáveis em um único lugar | Framework se torna ponto único de responsabilidade regulatória — exige rigor extra na manutenção |
| Custo de manutenção de longo prazo | Evolução e correções feitas uma vez beneficiam todos os projetos | Framework passa a exigir versionamento, testes de compatibilidade e comunicação de breaking changes a múltiplos times consumidores |
| Acoplamento entre projetos | — | Projetos passam a depender do ciclo de release do framework; mudanças exigem coordenação entre times |

## Consequências

- **Positivas**: novos projetos de dados públicos partem de uma base sólida,
  testada e alinhada a práticas de governança já validadas, reduzindo tempo
  de start-up e risco de não conformidade.
- **Negativas**: o `data-framework` passa a carregar responsabilidade sobre
  múltiplos projetos em produção; qualquer mudança exige disciplina de
  versionamento e comunicação para não quebrar consumidores. Cria-se também
  a necessidade de um processo de governança do próprio framework (quem
  aprova mudanças, como se propõe evolução).
- **Ações decorrentes**:
  - Definir processo de versionamento e release do framework (ADR futuro).
  - Definir processo de comunicação de breaking changes a projetos
    consumidores.
  - Estabelecer, em ADRs subsequentes, as convenções concretas de estrutura,
    ingestão, transformação e publicação mencionadas nesta decisão.

## Referências

- [Estrutura de ADRs do repositório](./README.md)
