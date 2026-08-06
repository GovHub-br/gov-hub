# ADR-0015: Estratégia de `Extractor` via Strategy para DAGs

- **Status**: Proposto
- **Data**: 2026-08-06
- **Autores**: Lucas Bottino, Arthur Melo
- **Revisores**: -

> Este ADR define uma nova estrutura para desenvolvimento de extratores
> dentro das DAGs baseada no padrão Strategy, generalizando um conceito
> de `Extractor` para suportar fontes heterogêneas (bancos relacionais,
> APIs, CSV/TXT, NoSQL, PDFs, object storage, etc.).

## Introdução ao problema

Atualmente as DAGs contêm código de ingestão/extração com variarão de
abordagens por tipo de fonte. Essa dispersão gera duplicação de lógica
(conexão, retries, idempotência, registro de metadados) e dificulta a
adoção de novos tipos de fonte de maneira consistente.

Queremos uma API e convenção clara para implementar e reutilizar
extratores dentro das DAGs, de forma que:

- Extratores compartilhem comportamentos transversais (retries, logs,
  metadados).
- Seja fácil adicionar suporte a novas fontes (ex.: PDFs, APIs,
  sistemas legados) sem modificar o código das DAGs.
- Haja um ponto central (registry/factory) que construa um
  `Extraction` a partir de uma configuração declarativa.

Essa decisão precisa ser tomada agora para padronizar novas
implementações e evitar perda de tempo com soluciones ad-hoc
quando integrarmos novos provedores de dados.

## Decisão

Adotamos um padrão Strategy para `Extractor`: um objeto `Extractor`
genérico atua como fachada e delega a execução para uma implementação
concreta de `SourceExtractor` (interface). Cada fonte tem um
`SourceExtractor` responsável por:

- interpretar a configuração específica da fonte;
- criar e executar a extração (streaming por lote, paginação, query SQL);
- retornar dados e metadados (esquema inferido, estatísticas, watermark);
- oferecer guarantees de idempotência ou checkpoints quando aplicável.

Elementos chave da proposta:

- Interface base: `SourceExtractor` com método `build_extraction(source_cfg, target)`
  (nome e assinatura a definir no código).
- Classe `Extractor` (fachada) que, dado uma configuração declarativa,
  resolve a implementação concreta via `ExtractorFactory`/`Registry` e
  chama `build_extraction(...)`.
- Implementações iniciais: `RelationalDatabaseExtractor`, `ApiExtractor`,
  `CsvExtractor`, `NoSqlExtractor`, `PdfExtractor`, `ObjectStorageExtractor`.
- Convenção de configuração: cada DAG fornece um dicionário/objeto de
  `source` com `type: <string>` e `params: {...}`; esse `type` mapeia para
  um `SourceExtractor` registrado.
- Local do código: manter a implementação em `dags/extractors/` para que
  seja acessível às DAGs e fácil de testar.

Com isso, uma DAG invocaria algo como:

```
extract = Extractor.build_extraction(source_cfg, target)
```

e `Extractor` cuidaria do resto (inicialização, logging, métricas).

## Alternativas consideradas

### Alternativa A: Cada DAG com implementações ad-hoc por fonte

- Descrição: manter a abordagem atual — cada DAG implementa sua própria
  lógica de extração para a(s) fonte(s) que consome.
- Prós: máxima liberdade; pouca infraestrutura nova.
- Contras: duplicação de código, inconsistência, dificuldade para adicionar
  novos tipos de fonte, manutenção custosa.

### Alternativa B: Adotar uma ferramenta/plug-in externa (ex.: Singer,
NiFi)

- Descrição: delegar extração a framework especializado e integrar
  via connectors/agents.
- Prós: já existe ecossistema de conectores; foco no problema de ingestão.
- Contras: aumento de superfície operacional, dependência externa,
  possível desalinhamento com a forma como equipes codificam DAGs no
  repositório (controle de versão, testes, deployment). [Médio impacto]

### Alternativa C: Especificação declarativa (YAML) + engine genérica

- Descrição: descrever extrações em YAML (queries, endpoints, mapeamentos)
  e executar por uma engine genérica que interpreta a especificação.
- Prós: menor código por DAG; facilita variações sem programação.
- Contras: limitações para processos que exigem lógica customizada
  (ex.: extrações com multipasso, transforms no fly) e custo de implementar
  engine robusta. [Médio/Alto impacto]

### Não fazer nada / manter status quo

- Manter a mistura de abordagens atuais.
- Consequência: acelera no curto prazo, mas aumenta dívida técnica e
  custo operacional a médio prazo.

## Tradeoffs

### Vantagens

- **[Alto impacto]** Reutilização: reduz duplicação e mantém um ponto
  único para melhorias transversais (retries, logging, metadados).
- **[Médio impacto]** Extensibilidade: adicionar um novo tipo de fonte
  envolve implementar a interface e registrar a implementação.
- **[Médio impacto]** Testabilidade: extratores serão componentes
  unit-testáveis isoladamente.

### Desvantagens

- **[Médio impacto]** Esforço inicial: criar a infra (interfaces,
  fábrica, registry, doc) requer tempo de desenvolvimento.
- **[Baixo/Médio impacto]** Curva de aprendizado: times terão que
  seguir a convenção para registrar extratores.
- **[Médio impacto]** Risco de over-engineering se uma única fonte for
  necessária para a maioria dos casos simples.

### Avaliação

Nosso contexto favorece padronização: os ganhos de manutenção e
extensibilidade superam o custo de implementação. A implantação será
iterativa: começar com poucos extractors (relacional, csv, api) e
expandir conforme demanda.

## Consequências

- Positivas:
  - Código de extração mais consistente entre DAGs. [Alto impacto]
  - Facilidade para adicionar novos conectores. [Médio impacto]
  - Melhoria na observabilidade e injeção padronizada de metadados.

- Negativas:
  - Trabalho inicial para criar a infra e migrar implementações
    existentes. [Médio impacto]
  - Possível rigidez se a interface não for suficientemente flexível;
    precisamos projetar APIs mínimas e extensíveis. [Médio impacto]

- Ações decorrentes:
  - Criar `dags/extractors/` com: `base.py` (interfaces), `registry.py`,
    implementações iniciais (`relational.py`, `csv.py`, `api.py`).
  - Documentar convenções e assinatura (linkar este ADR) no README das DAGs.
  - Escrever testes unitários para `base` e para cada extractor inicial.
  - Planejar migração de 2-3 DAGs piloto para validar a ergonomia.

## Referências

- Diagrama de classes proposto (anexado à discussão interna).
- ADRs relacionados: `0011-arquitetura-agnostica-motor-processamento.md` (alinhamento de
  processamento agnóstico), `0007-nomenclatura-pastas-dags-ingestao.md` (convenções de pastas),
  `0014-padrao-documentacao-dags-dbt-openmetadata.md` (metadados/documentação).
- Bibliotecas sugeridas por tipo de fonte (não mandatórias):
  - SQL: `sqlalchemy` para conexão e abstração de SQL;
  - APIs: `httpx` ou `requests` para chamadas HTTP, com adapters para
    paginação/timeout;
  - CSV/TXT: `pandas` ou `csv` nativo para grandes arquivos streaming;
  - PDFs: `pdfplumber`/`pypdf` para extração de texto; quando houver
    tabelas usar OCR/Tabula conforme necessário;
  - NoSQL: `pymongo` (Mongo), drivers nativos para Cassandra/Dynamo quando
    aplicável;
  - Object Storage: `boto3` / cliente S3 compatível para leitura de objetos.
