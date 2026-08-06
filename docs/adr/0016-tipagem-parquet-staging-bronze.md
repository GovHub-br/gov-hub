# ADR-0016: Tipagem de Parquet — promover Staging (MinIO) → Bronze

- **Status**: Proposto
- **Data**: 2026-08-06
- **Autores**: Lucas Bottino, Arthur Melo, João Egewarth, Matheus Miranda
- **Revisores**: -

> Este ADR avalia a possibilidade de fazer a camada `staging` em
> Object Storage (MinIO) ser considerada a camada `bronze` através do
> uso de arquivos Parquet com tipagem/contrato explícito, e propõe uma
> estratégia operacional para garantir validade e evolução de esquema.

## Introdução ao problema

Atualmente o fluxo de ingestão escreve artefatos em `staging/` no
MinIO (objetos brutos). Queremos avaliar se esses artefatos — quando
formato Parquet — podem ser tratados automaticamente como a camada
`bronze` (registrados como dataset consumível), de modo que o banco de
dados (warehouse) armazene apenas `silver` e `mart`.

Vantagens esperadas:

- reduzir duplicação de armazenamento e movimento de dados;
- acelerar availability de dados para downstreams que leem Parquet;
- simplificar pipeline: promoção de staging → bronze automática.

Restrições e riscos:

- Parquet contém esquema embutido, mas o formato sozinho não garante
  consistência (múltiplos arquivos podem divergir em esquema);
- ausência de metadados transacionais (lista/manifest) torna difícil
  garantir atomicidade/visão consistente ao ler um dataset;
- evolução de esquema (colunas renomeadas, tipos alterados, nulidade)
  precisa ser tratada explicitamente.

## Decisão (resumo)

Adotamos uma solução em duas camadas:

1. Curto prazo (piloto/aceitável): permitir que Parquets tipados no
   `staging/` sejam promovidos a `bronze/` somente após uma etapa de
   validação/registro que:
   - valida esquema (conformidade com um `contract`/schema esperado);
   - valida estatísticas e checksums (integridade);
   - grava um `manifest`/metadado (json) no object storage descrevendo
     quais arquivos compõem o bronze e sua versão;
   - registra o esquema no catálogo de metadados (OpenMetadata ou
     equivalente).

2. Médio prazo (recomendado): migrar para um *table format* com
   metadados e governance (preferência: Apache Iceberg; alternativa:
   Delta Lake ou Apache Hudi). Esse formato oferece:
   - metadados centralizados (manifests, snapshots, transações);
   - melhor suporte à evolução e tempo de leitura consistente;
   - compatibilidade com engines (Spark, Flink, Trino, Presto, etc.).

Com isso, o `staging/` poderá ser considerado `bronze/` quando os
arquivos fizerem parte de um snapshot aprovado (manifest registrado).

## Alternativas consideradas

### Alternativa A: Confiar somente no Parquet + convenção de caminhos

- Descrição: considerar qualquer Parquet salvo em `staging/` como
  bronze sem validação adicional.
- Prós: mínimo esforço operacional; pipelines simples.
- Contras: alto risco de inconsistência entre arquivos, leituras
  incompletas, e dificuldade de rastrear quais arquivos pertencem a
  uma versão do dataset. [Alto impacto negativo]

### Alternativa B: Parquet + validação/manifest (proposta de curto prazo)

- Descrição: exigir etapa de validação e registro (manifest + catálogo)
  antes da promoção para `bronze`.
- Prós: baixo esforço incremental; mantém uso simples de Parquet; gera
  artefatos audíveis (manifest) para consumo.
- Contras: ainda não fornece transações robustas e snapshot isolation;
  exige escrita e governança de manifests. [Médio impacto]

### Alternativa C: Adotar Table Format (Iceberg/Delta/Hudi)

- Descrição: armazenar datasets como tabelas geridas por um table format
  que persiste metadados no object storage e oferece snapshots.
- Prós: transações, esquema-versioning, compatibilidade com query engines,
  maior maturidade operacional para data lakes. [Alto impacto positivo]
- Contras: introduz nova tecnologia/stack, curva operacional e de
  integração com infra existente (Airflow+dag runners). [Médio impacto]

## Tradeoffs

### Vantagens da decisão adotada

- **[Alto impacto]** Garantir datasets `bronze` com contrato explícito
  melhora confiança dos consumidores e reduz carga duplicada no
  warehouse.
- **[Médio impacto]** Opção de curto prazo (validação+manifest) permite
  benefício rápido sem grande mudança arquitetural.
- **[Alto impacto]** Adoção futura de Iceberg/Delta traz ganhos operacionais
  significativos (snapshots, rollbacks, partition evolution).

### Desvantagens / Custos

- **[Médio impacto]** Esforço para implementar validador, manifest store
  e integração com catálogo (OpenMetadata).
- **[Médio impacto]** Operacional: need to manage schema registry and
  policies for evolution and backfills.
- **[Médio impacto]** Se optarmos por table-format, há custo de
  integração e possíveis mudanças em ferramentas de consulta.

### Avaliação

Promover `staging` para `bronze` com segurança é viável se adotarmos
validação e registro de metadados; a solução mais robusta e sustentável
é migrar para um table format (Iceberg/Delta). Portanto:

- Implantamos a validação e manifest como primeiro passo (baixo custo);
- Projetamos o piloto com objetivo de migrar para Iceberg/Delta
  posteriormente (médio prazo).

## Consequências

- Positivas:
  - Redução de movimentação de dados para o warehouse; [Médio impacto]
  - Consumidores que leem Parquet do MinIO terão datasets com contrato
    e versão; [Médio impacto]
  - Melhoria na governança via catálogo de metadados. [Médio impacto]

- Negativas:
  - Implementação de um validador/manifest e políticas de promoção;
    [Médio impacto]
  - Se ignorarmos table formats, limitações permanecerão (sem
    snapshots/transações). [Médio impacto]

- Ações decorrentes (próximos passos):
  1. Criar piloto `parquet-validator` (DAG + módulo em `dags/validators/`)
     que:
     - valida esquema com `pyarrow` vs. um `contract` (json/schema);
     - calcula checksums e estatísticas (row count, size, min/max por
       coluna quando relevante);
     - grava um `manifest.json` no mesmo prefixo com lista de arquivos
       e metadados; e registra esquema/versão em OpenMetadata.
  2. Atualizar DAGs de ingestão para escrever arquivos Parquet com
     esquema explícito (usando `pyarrow`/`fastparquet`) e emitir um
     evento de promoção para validação.
  3. Implementar consumidores de `manifest` para leitura consistente
     (scripts de leitura que consultam o manifest antes de abrir
     arquivos).
  4. Avaliar e planejar migração para Apache Iceberg (ou Delta) com
     protótipo pequeno: tabelas de 1-2 pipelines, integração com Trino
     ou Spark para consultas.
  5. Documentar políticas de evolução de esquema, backfills e rollback.

## Referências e bibliografia técnica

- Parquet schema and evolution notes: Apache Parquet docs;
- Table formats: Apache Iceberg (https://iceberg.apache.org), Delta
  Lake (https://delta.io), Apache Hudi;
- Python tooling: `pyarrow`, `fastparquet`, `delta-rs`/`pyarrow` bindings;
- Metadata/catalog: OpenMetadata, Amundsen (catalog integration);
- Ferramentas úteis: `parquet-tools`, `parquet-mr` for inspection, and
  `aws-sdk`/`boto3` or `minio` client for object operations.
