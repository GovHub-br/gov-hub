# ADR-0011: Arquitetura agnóstica a motor de processamento de dados

- **Status**: Proposto
- **Data**: 2026-08-07
- **Autores**: -
- **Revisores**: -

## Introdução ao problema

O `data-framework` é herdado por múltiplos projetos de dados públicos
([ADR-0003](./0003-govhub-como-framework-compartilhado-de-dados.md)) que
compartilham a mesma base de código em um monorepo
([ADR-0004](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)).
Esses projetos, porém, não rodam sobre a mesma infraestrutura: alguns órgãos
operam inteiramente on-premise com PostgreSQL, outros já possuem contratos
de nuvem com plataformas analíticas próprias (ex.: Databricks/Spark,
Synapse, BigQuery), e alguns transitam de um cenário para o outro no meio da
vida do projeto.

O [ADR-0002](./0002-dbt-como-ferramenta-de-transformacao-de-dados.md)
escolheu dbt como ferramenta de transformação **com foco em PostgreSQL**,
por ser o banco predominante nos projetos consumidores hoje. Essa escolha
resolve *qual ferramenta* escreve a transformação, mas não impede que o
código escrito com ela fique preso a *um motor de execução específico*. Sem
uma decisão explícita, três problemas aparecem:

- **Modelo compartilhado que só roda em um órgão**: um modelo dbt colocado
  em uma pasta de sistema compartilhado (`dbt/<sistema>/`, ADR-0004) é, por
  definição, executado pelo banco de cada órgão que consome aquele pacote.
  Se ele usar uma função exclusiva do PostgreSQL, ele silenciosamente deixa
  de ser compartilhável — o problema só aparece quando o segundo órgão
  tenta usá-lo.
- **Migração de motor vira reescrita de pipeline**: se a lógica de
  transformação estiver expressa em código de um motor (PySpark, UDFs,
  SQL proprietário), trocar de motor — ou atender a um órgão novo com
  motor diferente — exige reescrever as transformações, não apenas mudar
  configuração de deployment.
- **Aprisionamento a fornecedor**: contratos públicos não podem depender de
  ferramentas proprietárias que gerem risco de aprisionamento, restrição já
  levantada nos ADRs [0001](./0001-airflow-como-orquestrador-de-fluxos-de-dados.md)
  e [0002](./0002-dbt-como-ferramenta-de-transformacao-de-dados.md). Um
  motor de processamento acoplado ao código é uma forma de aprisionamento
  tão efetiva quanto uma licença.

Essa decisão precisa ser tomada agora porque ela define uma **restrição de
escrita** — o que pode e o que não pode aparecer dentro de um modelo
compartilhado. Restrições desse tipo custam pouco quando estabelecidas antes
de o código existir, e custam uma migração inteira quando estabelecidas
depois.

## Decisão

O `data-framework` é **agnóstico ao motor de processamento de dados**: o
motor concreto é uma escolha de *deployment*, não uma característica do
código. Nenhum componente do framework — nem do código compartilhado entre
órgãos — pode assumir qual motor executa a transformação.

Concretamente:

1. **Transformação é sempre modelo dbt.** Toda lógica analítica é expressa
   como modelo dbt (ADR-0002), nunca como código de motor (PySpark,
   procedures, jobs proprietários). O motor entra apenas como *adapter* dbt.
2. **O SQL compartilhado se restringe ao subconjunto portável.** Modelos que
   vivem em pastas de sistema compartilhado (`dbt/<sistema>/`, ADR-0004) usam
   apenas construções SQL suportadas por todos os adapters alvo do
   framework. Quando uma função específica de motor for inevitável, ela é
   isolada em uma **macro dbt** com `{{ adapter.dispatch() }}` e uma
   implementação por adapter — a especificidade fica na macro, não espalhada
   pelos modelos.
3. **O motor é configuração, não código.** A escolha do motor vive no
   `profiles.yml`/target do projeto dbt de cada órgão (`dbt/<orgao>/`,
   ADR-0009), não em condicionais dentro dos modelos.
4. **Fronteira explícita entre mover e transformar.** DAGs de ingestão
   ([ADR-0007](./0007-nomenclatura-pastas-dags-ingestao.md)) movem dados
   (extraem da fonte, escrevem no destino) e podem fazer normalização
   estrutural mínima; elas **não** executam transformação analítica. Quando
   uma DAG precisar manipular dados tabulares em Python, usa uma API de
   DataFrame em processo sobre arquivos — nunca um SDK de motor
   (`pyspark`, cliente de warehouse) que assumiria um cluster específico.
5. **Acesso a armazenamento também é agnóstico.** Leitura e escrita em
   object storage passam por uma abstração de sistema de arquivos
   (`fsspec`), de modo que MinIO on-prem, S3 e ADLS sejam trocáveis por
   variável de ambiente, sem caminho de código distinto por provedor.
6. **Exceções são localizadas, não globais.** Um modelo que genuinamente
   dependa de um recurso exclusivo de um motor é permitido, desde que viva
   na pasta do órgão que o usa (`dbt/<orgao>/` ou `dbt/<sistema>/<orgao>/`,
   ADR-0004) — nunca em uma pasta de sistema compartilhado. A regra de
   promoção do ADR-0004 se aplica ao contrário aqui: um modelo só sobe para
   a pasta compartilhada depois de perder a dependência de motor.

Este ADR **não** define qual motor cada órgão deve usar, nem obriga que o
framework seja testado contra todos os motores existentes — define apenas
que o código compartilhado não pode impedir a troca.

## Alternativas consideradas

### Alternativa A: Acoplar explicitamente ao PostgreSQL (status quo de fato)

- Descrição: assumir PostgreSQL como o motor do framework e usar livremente
  suas extensões, funções e tipos nos modelos compartilhados.
- Prós: aproveita ao máximo o banco predominante nos projetos consumidores
  hoje (ADR-0002); nenhuma restrição de escrita para os times; permite
  otimizações específicas que um subconjunto portável não permite.
- Contras: fecha a porta para órgãos que já operam em nuvem com plataforma
  analítica própria, exatamente o cenário que motiva esta decisão. Como o
  acoplamento aconteceria de forma difusa (uma função aqui, um tipo ali),
  ele só seria descoberto no momento da migração — quando o custo de
  desfazê-lo é máximo.

### Alternativa B: Acoplar a um motor distribuído (Spark/Databricks)

- Descrição: padronizar o framework sobre um motor distribuído, escrevendo
  transformações em PySpark ou SQL do motor escolhido.
- Prós: escala melhor para volumes muito grandes; ecossistema maduro de
  processamento; alinhado a órgãos que já contrataram esse tipo de
  plataforma.
- Contras: inviabiliza os projetos on-premise, que hoje são a maioria e
  operam com PostgreSQL sem qualquer cluster disponível. Introduz custo
  operacional e de infraestrutura desproporcional ao volume real da maioria
  das fontes de dados públicos ingeridas pelo framework, e contraria a
  restrição de aprisionamento quando o motor é o serviço gerenciado de um
  fornecedor específico.

### Alternativa C: Camada de abstração própria sobre os motores

- Descrição: o framework define sua própria API/representação intermediária
  de transformação, e traduz para o motor de destino em tempo de execução.
- Prós: agnosticismo total, sem depender do conjunto de adapters de
  terceiros; permite expressar a transformação uma única vez.
- Contras: é reimplementar, com uma equipe pequena, o problema que o dbt e
  seus adapters já resolvem — com o agravante de que a abstração própria
  não teria comunidade, documentação nem contribuidores externos. Toda
  função nova de cada motor viraria trabalho de manutenção do framework, e
  a curva de aprendizado passaria a ser de uma linguagem interna, anulando
  o ganho de onboarding que motiva o framework (ADR-0003).

### Não fazer nada / manter status quo

- Descrição: não declarar restrição alguma; cada time escreve o modelo da
  forma que funciona no seu banco.
- Consequência: na prática converge para a Alternativa A, mas de forma não
  intencional e não documentada — o framework ficaria acoplado ao
  PostgreSQL sem que ninguém tivesse decidido isso, e sem que o custo dessa
  escolha estivesse registrado em lugar algum.

## Tradeoffs

### Vantagens

- **[Alto impacto]** Um modelo colocado em pasta de sistema compartilhado
  realmente funciona para todos os órgãos que consomem aquele pacote — o
  compartilhamento prometido pelo ADR-0004 deixa de depender de coincidência
  de infraestrutura entre órgãos.
- **[Alto impacto]** Trocar de motor (ou atender um órgão novo com motor
  diferente) passa a ser mudança de configuração de deployment, não
  reescrita de pipeline.
- **[Médio impacto]** Reduz risco de aprisionamento a fornecedor, restrição
  concreta em contratos públicos e coerente com as decisões dos ADRs 0001 e
  0002.
- **[Médio impacto]** A fronteira explícita entre "mover" (DAG) e
  "transformar" (dbt) elimina a ambiguidade sobre onde escrever cada lógica,
  reforçando o contrato de camadas do
  [ADR-0006](./0006-arquitetura-medallion.md).
- **[Baixo impacto]** Concentrar especificidade de motor em macros
  `dispatch` dá um inventário auditável de exatamente onde o framework não é
  portável.

### Desvantagens

- **[Alto impacto]** Abre mão de otimizações específicas de motor nos
  modelos compartilhados. Em casos de volume alto, isso significa aceitar
  um plano de execução pior do que o que seria possível escrevendo para um
  motor só.
- **[Médio impacto]** O "subconjunto portável" não é uma lista fechada e
  verificável automaticamente hoje — na prática, a portabilidade de um
  modelo compartilhado depende de revisão de código, e uma violação pode
  passar despercebida até o segundo órgão tentar usar o modelo.
- **[Médio impacto]** Macros com `dispatch` por adapter adicionam uma
  indireção real: ler o que um modelo faz passa a exigir abrir também a
  macro e identificar qual implementação roda naquele deployment.
- **[Baixo impacto]** Restringe o uso de bibliotecas Python nas DAGs de
  ingestão, mesmo quando um SDK de motor resolveria um caso pontual de forma
  mais direta.

### Avaliação

Os ganhos superam os custos neste contexto. O framework existe para ser
herdado por múltiplos órgãos com infraestruturas diferentes (ADR-0003), e
uma decisão que torne o código compartilhado executável em apenas parte
deles anula boa parte do valor do monorepo. O custo mais concreto — abrir
mão de otimizações específicas — é aceitável porque os volumes típicos das
fontes de dados públicos ingeridas hoje estão longe do ponto em que a
diferença de plano de execução se torna limitante; se algum domínio chegar
lá, a exceção localizada em pasta de órgão é a válvula de escape prevista.

Permanece como **risco ativo** a ausência de verificação automática de
portabilidade: até que exista lint ou execução de CI contra mais de um
adapter, "este modelo é portável" é uma afirmação sustentada por revisão
humana, e a primeira evidência de violação tende a ser um erro em produção
no deployment de outro órgão.

## Consequências

- **Positivas**: o código compartilhado do monorepo passa a ser
  genuinamente compartilhável entre órgãos com infraestruturas distintas;
  a escolha de motor deixa de ser uma decisão irreversível tomada
  implicitamente pelo primeiro time que escreveu um modelo; a fronteira
  entre DAG e dbt fica explícita.
- **Negativas**: cria uma restrição de escrita que os times precisam
  conhecer e respeitar, sem enforcement automático inicial; adiciona
  indireção (macros `dispatch`) nos pontos em que a especificidade é
  inevitável; abre mão de otimizações por motor no código compartilhado.
- **Ações decorrentes**:
  - Documentar, junto às convenções de dbt (ADR-0009), a lista dos adapters
    considerados alvo do framework e o subconjunto SQL portável esperado.
  - Criar a convenção de macros `dispatch` para os casos de especificidade
    inevitável, com uma pasta/arquivo previsível dentro de `macros/`.
  - Avaliar, no CI, a compilação (`dbt compile`) dos pacotes compartilhados
    contra mais de um adapter, transformando a portabilidade em verificação
    automática em vez de revisão humana.
  - Registrar, em revisão de PR, a regra de que um modelo com dependência de
    motor não pode viver em pasta de sistema compartilhado — candidato a
    entrada no `CODEOWNERS` das pastas compartilhadas (ADR-0004).

## Referências

- [ADR-0001 — Apache Airflow como orquestrador de fluxos de dados](./0001-airflow-como-orquestrador-de-fluxos-de-dados.md)
- [ADR-0002 — dbt como ferramenta de transformação de dados](./0002-dbt-como-ferramenta-de-transformacao-de-dados.md)
- [ADR-0003 — GovHub como framework compartilhado de dados](./0003-govhub-como-framework-compartilhado-de-dados.md)
- [ADR-0004 — Monorepo como estratégia de organização de código](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)
- [ADR-0006 — Arquitetura medallion (bronze/silver/gold)](./0006-arquitetura-medallion.md)
- [ADR-0009 — Padrão de nomenclatura das pastas/arquivos de projetos dbt](./0009-nomenclatura-pastas-arquivos-dbt.md)
- [dbt — `adapter.dispatch` e macros multi-adapter](https://docs.getdbt.com/reference/dbt-jinja-functions/dispatch)
- [fsspec — Filesystem interfaces for Python](https://filesystem-spec.readthedocs.io/)
- [Estrutura de ADRs do repositório](./README.md)
