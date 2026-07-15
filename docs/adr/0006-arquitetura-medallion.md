# ADR-0006: Arquitetura medallion (bronze/silver/gold)

- **Status**: Proposto
- **Data**: 2026-07-15
- **Autores**: João Egewarth
- **Revisores**: -

## Introdução ao problema

O `data-framework` precisa de um modelo de camadas para organizar dados em
diferentes estágios de qualidade e prontidão para consumo — desde o dado
bruto recebido de um sistema público até o produto de dados consumido por
dashboards, APIs ou análises. Sem esse modelo, cada projeto consumidor
decide, caso a caso, onde aplicar limpeza, deduplicação, regras de negócio
e agregações, o que gera dois problemas recorrentes:

- **Ambiguidade sobre onde transformar**: sem camadas com contrato
  explícito, lógica de limpeza técnica e lógica de negócio se misturam no
  mesmo modelo/tabela, dificultando isolar a causa de um erro (é um problema
  de qualidade do dado de origem ou uma regra de negócio incorreta?).
- **Falta de um ponto de auditoria confiável**: sem uma camada que preserve o
  dado exatamente como recebido da fonte, um erro de transformação
  descoberto tarde exige voltar à fonte original (nem sempre disponível ou
  reproduzível) em vez de reprocessar a partir de um estágio interno já
  persistido.

Esta decisão parte do **[Padrão de Arquitetura de Dados — MGI/SEGES/CDATA
(v3.0)](./arquitetura_dados_mgi.pdf)**, documento interno de referência que já formaliza um modelo de
camadas Bronze/Silver/Gold para a plataforma de dados multiproduto do MGI.
Embora esse documento seja específico a uma stack em Azure ADLS Gen2 +
Databricks Unity Catalog — diferente da stack do `data-framework`
(Airflow + dbt, [ADR-0001](./0001-airflow-como-orquestrador-de-fluxos-de-dados.md)
e [ADR-0002](./0002-dbt-como-ferramenta-de-transformacao-de-dados.md)) — o
contrato de qualidade por camada que ele define é independente de qualquer
tecnologia específica, e serve de precedente já validado em contexto de
dados públicos brasileiros.

Esta decisão precisa ser tomada agora porque a definição de camadas é um
pré-requisito para outras decisões de nomenclatura de schemas e tabelas
ainda em backlog.

## Decisão

O `data-framework` adota a **arquitetura medallion** — três camadas
progressivas e unidirecionais, Bronze, Silver e Gold — como modelo padrão
de organização de dados, com um contrato de qualidade explícito por camada:

- **Bronze**: fidelidade à fonte. Preserva o dado exatamente como recebido,
  acrescido apenas de metadados técnicos de ingestão (data/hora de
  ingestão, identificador de execução, arquivo/fonte de origem, hash ou
  versão do schema da fonte). Nenhuma correção de negócio, deduplicação ou
  enriquecimento é permitida nesta camada. Uma vez ingerido, um registro
  Bronze não é alterado — apenas relido por camadas seguintes.
- **Silver**: verdade única do dado. Aplica limpeza, deduplicação, tipagem
  correta e padronização de nomes de coluna, seguindo regras de qualidade
  documentadas. É a camada de referência para consumo técnico (analistas,
  cientistas de dados, pipelines Gold). Agregações, KPIs e joins
  especulativos de negócio não pertencem a esta camada.
- **Gold**: produto de dados. Entrega dados agregados, com KPIs, joins
  multi-domínio e modelagem voltada a consumo por BI, APIs e dashboards.
  Exige documentação completa e critério de qualidade mais rigoroso que as
  camadas anteriores.

O fluxo entre camadas é **unidirecional**: Silver deriva de Bronze, Gold
deriva de Silver. Consumidores finais (dashboards, APIs, relatórios) não
acessam Bronze diretamente.

Este ADR **não obriga** a existência física de estágios de pré-Bronze
(Landing/Raw) nem define onde cada camada é fisicamente persistida — isso
é tratado por decisões complementares e ainda em aberto sobre armazenamento
(object storage vs. banco direto). A adoção de Landing/Raw como estágios
físicos antes da Bronze é opcional e depende das características de cada
fonte de dados (ex.: necessidade de retenção do payload bruto antes de
qualquer parsing).

## Alternativas consideradas

### Alternativa A: Sem modelo de camadas (status quo / não fazer nada)

- Descrição: cada pipeline decide livremente onde aplicar limpeza,
  deduplicação e regras de negócio, sem convenção de camadas.
- Prós: nenhuma curva de aprendizado adicional; flexibilidade total por
  pipeline.
- Contras: é exatamente o cenário que gera os dois problemas descritos na
  introdução — mistura de lógica técnica e de negócio, e ausência de um
  ponto de auditoria confiável equivalente a uma camada Bronze imutável.

### Alternativa B: Duas camadas (raw + curated, sem Gold separado)

- Descrição: manter apenas uma camada de dado bruto e uma camada final já
  tratada e pronta para consumo, sem uma camada intermediária dedicada
  exclusivamente a limpeza técnica.
- Prós: menos pipelines por fonte de dados que o modelo de três camadas;
  mais simples para fontes triviais.
- Contras: mistura, na mesma camada, a responsabilidade de limpeza técnica
  (deduplicação, tipagem) com a de modelagem de negócio (agregações, KPIs),
  reintroduzindo parte da ambiguidade que motiva esta decisão. Não separa
  claramente "dado confiável" de "produto de dados pronto para consumo".

### Medallion (Bronze/Silver/Gold) — decisão proposta

- Descrição: três camadas progressivas com contrato de qualidade distinto
  cada uma, seguindo o modelo já validado pelo documento de arquitetura do
  MGI/SEGES/CDATA.
- Por que foi escolhida: separa claramente fidelidade à fonte (Bronze),
  confiabilidade técnica (Silver) e modelagem de negócio para consumo
  (Gold), resolvendo diretamente a ambiguidade e a falta de um ponto de
  auditoria confiável levantadas na introdução — sem exigir uma tecnologia
  ou stack de armazenamento específica.

## Tradeoffs

### Vantagens

- **[Alto impacto]** Contrato de qualidade claro por camada elimina a
  ambiguidade sobre onde aplicar cada tipo de transformação — um erro de
  dado é rapidamente localizável como problema de origem (Bronze), de
  limpeza (Silver) ou de regra de negócio (Gold).
- **[Alto impacto]** Bronze imutável cria um ponto de auditoria e
  reprocessamento confiável: um bug em Silver ou Gold pode ser corrigido e
  reprocessado sem depender de a fonte original ainda estar disponível.
- **[Médio impacto]** Precedente já validado em contexto de dados públicos
  brasileiros (MGI/SEGES/CDATA), reduzindo o risco de adotar um modelo não
  testado nesse contexto.
- **[Médio impacto]** Vocabulário comum (bronze/silver/gold) entre projetos
  consumidores do framework reduz a curva de aprendizado ao transitar entre
  times e projetos.
- **[Baixo impacto]** Isola o impacto de mudanças: reprocessar Silver ou
  Gold não exige tocar em Bronze, e vice-versa.

### Desvantagens

- **[Alto impacto]** Introduz overhead de pipelines: qualquer dado passa
  por, no mínimo, duas transformações (Bronze → Silver → Gold), mesmo
  quando a lógica final seria simples o suficiente para uma única etapa.
- **[Médio impacto]** Sem enforcement automático, nada impede que lógica de
  negócio "vaze" para Bronze ou Silver por conveniência — a disciplina de
  respeitar o contrato de cada camada depende de revisão de código.
- **[Médio impacto]** Camadas adicionais podem aumentar custo de
  armazenamento (dado persistido redundantemente em cada camada) quando não
  há política de retenção definida — decisão que este ADR delega a um
  documento complementar sobre armazenamento.
- **[Baixo impacto]** Este ADR não define, por si só, a nomenclatura
  concreta de schemas e tabelas por camada — depende de decisões
  complementares ainda em aberto.

### Avaliação

Os ganhos superam os custos: formalizar três camadas com contrato de
qualidade explícito resolve um problema que a maioria dos pipelines de
dados públicos precisaria endereçar de qualquer forma, e o overhead de
pipelines adicionais é aceitável dado o ganho de auditabilidade — especialmente
relevante em um contexto de dados públicos sujeitos a auditoria e LGPD. O
principal risco ativo é a ausência de enforcement automático do contrato de
cada camada, que permanece dependente de revisão de código até que testes
ou lint específicos sejam criados para verificá-lo.

## Consequências

- **Positivas**: pipelines dos projetos consumidores passam a ter um
  vocabulário e contrato de qualidade padronizados; a camada Bronze
  imutável cria uma base auditável e reprocessável; a separação entre
  Silver e Gold evita que lógica de negócio contamine a camada de
  confiabilidade técnica.
- **Negativas**: aumenta o número mínimo de transformações/pipelines por
  fonte de dados; exige disciplina de revisão de código para impedir que
  lógica de negócio vaze para as camadas erradas, já que não há
  enforcement automático do contrato.
- **Ações decorrentes**:
  - Definir, em documento complementar, a nomenclatura concreta de
    schemas e tabelas por camada.
  - Definir critérios objetivos de promoção entre camadas (ex.: papéis de
    ownership, regras de qualidade documentadas), possivelmente em um ADR
    futuro de governança de dados.
  - Decidir separadamente, em documento complementar ainda em aberto, se e
    como usar object storage para as camadas Bronze/Silver/Gold — esta
    decisão de arquitetura de camadas não obriga um mecanismo de
    armazenamento específico.

## Referências

- [Padrão de Arquitetura de Dados — MGI/SEGES/CDATA, v3.0](./arquitetura_dados_mgi.pdf)
  (documento interno de referência, ambiente DEV).
- [ADR-0001 — Apache Airflow como orquestrador de fluxos de dados](./0001-airflow-como-orquestrador-de-fluxos-de-dados.md)
- [ADR-0002 — dbt como ferramenta de transformação de dados](./0002-dbt-como-ferramenta-de-transformacao-de-dados.md)
- [ADR-0004 — Monorepo como estratégia de organização de código](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)
- [Estrutura de ADRs do repositório](./README.md)
