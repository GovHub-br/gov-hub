# gov-bricks

**gov-bricks** é o `data-framework` do [Gov Hub BR](https://gov-hub.io/govhub/):
uma base compartilhada e opinativa para projetos de dados públicos brasileiros,
cobrindo ingestão, transformação, qualidade e publicação de dados.

Em vez de cada projeto reimplementar sua própria stack, os projetos consumidores
herdam deste repositório a estrutura, as convenções e os utilitários comuns —
ver [ADR-0003](docs/adr/0003-govhub-como-framework-compartilhado-de-dados.md).
O repositório é um **monorepo**: framework e código dos projetos consumidores
convivem aqui, organizados por sistema e órgão
([ADR-0004](docs/adr/0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)).

## Stack

| Camada | Ferramenta |
|---|---|
| Orquestração | Apache Airflow 2.8 ([ADR-0001](docs/adr/0001-airflow-como-orquestrador-de-fluxos-de-dados.md)) |
| Transformação | dbt + Astronomer Cosmos ([ADR-0002](docs/adr/0002-dbt-como-ferramenta-de-transformacao-de-dados.md)) |
| Landing zone | Object storage — MinIO on-prem, S3/ADLS na nuvem ([ADR-0012](docs/adr/0012-ingestao-object-storage-vs-database.md)) |
| Modelagem | Arquitetura medallion: bronze → silver → gold ([ADR-0006](docs/adr/0006-arquitetura-medallion.md)) |
| Dependências | `uv` + `pyproject.toml` |
| Qualidade | `black`, `ruff`, `ty`, `sqlfmt`, `pytest` |

## Estrutura

```
airflow/
  dags/
    data_ingest/<sistema>/[<orgao>/]   # DAGs de ingestão
    data_ingest/<orgao>/               # sistema interno de um único órgão
    dbt/<sistema>/                     # pacote dbt compartilhado
    dbt/<orgao>/                       # projeto dbt do órgão
    homologation/                      # DAGs de qualidade/homologação
  helpers/                             # utilitários Python compartilhados
  plugins/                             # clientes de fonte e integrações
docker/                                # Dockerfile, docker-compose.yml, init do Postgres
docs/adr/                              # decisões de arquitetura
tests/                                 # unit (CI) e integration (docker compose)
```

As convenções de nomenclatura de pastas e arquivos estão nos ADRs
[0007](docs/adr/0007-nomenclatura-pastas-dags-ingestao.md) (DAGs de ingestão),
[0009](docs/adr/0009-nomenclatura-pastas-arquivos-dbt.md) (dbt) e
[0010](docs/adr/0010-nomenclatura-schemas-tabelas-bronze-silver-gold.md)
(schemas e tabelas).

## Utilitários compartilhados

### `airflow/plugins/`

| Módulo | O que faz |
|---|---|
| `cliente_base.py` | Cliente HTTP base (`httpx`) com retry e backoff exponencial |
| `cliente_postgres.py` | Cliente PostgreSQL: criação de tabela por inferência de tipos, upsert, deduplicação |
| `cliente_sqlserver.py` | Leitura de tabelas SQL Server via `MsSqlHook` |
| `cliente_storage.py` | Abstração `fsspec` da landing zone (`STORAGE_BACKEND`: `minio`/`s3`/`adls`) |
| `cliente_email.py` | Extração de anexos CSV/ZIP de caixas IMAP |
| `email_ingest_dag_factory.py` | Factory de DAG para ingestão de relatórios recebidos por email |
| `schedule_loader.py` | Schedules dinâmicos via Airflow Variable `dynamic_schedules` |

### `airflow/helpers/`

| Módulo | O que faz |
|---|---|
| `landing_zone.py` | `build_landing_path`, `write_parquet`, `read_parquet`, `list_files` |
| `homologation_helpers.py` | Checks de qualidade em Polars (`not_null`, `schema`, `row_count`, `no_duplicates`, `null_rate`) |
| `homologation_flow.py` | Fluxo landing zone → validação → Postgres |
| `postgres_helpers.py` | Resolução de connection string a partir de uma connection do Airflow |
| `retry_helpers.py` | Decorator `retry_on_exception` com backoff |
| `safe_request.py` | Variante de request tolerante a 204, corpo vazio e JSON inválido |

Convenção da landing zone:
`{bucket}/{source}/{entity}/{ano}/{mes}/{dia}/{run_id}.parquet`

## Começando

Pré-requisitos: Python 3.11, [uv](https://docs.astral.sh/uv/getting-started/installation/),
Docker, Docker Compose e Make.

```bash
make setup      # instala deps, gera requirements.txt, cria .env e instala git hooks
make compose    # sobe Airflow + Postgres + MinIO e configura variables/connections
```

Airflow em http://localhost:8080 (`airflow`/`airflow`), console do MinIO em
http://localhost:9001 (`minioadmin`/`minioadmin`).

## Comandos

| Comando | Descrição |
|---|---|
| `make install` | Instala as dependências com `uv sync` |
| `make requirements` | Regenera o `requirements.txt` (runtime) usado pela imagem Docker |
| `make format` | Aplica `black`, `ruff --fix` e `sqlfmt` |
| `make lint` | Verifica `black`, `ruff`, `ty` e `sqlfmt` |
| `make test` | Testes unitários com cobertura (o que roda no CI) |
| `make test-integration` | Testes de integração (sobe MinIO e Postgres) |
| `make dev` / `make dev-check` | Configura e valida variables/connections do Airflow local |

> `requirements.txt` é um artefato gerado por `make requirements` — não edite à
> mão. Dependências entram no `pyproject.toml`.

## Contribuindo

Leia o [Guia de Contribuição](.github/CONTRIBUTING.md) e o
[Protocolo de Aprovação de Pull Requests](.github/MERGE_REQUEST_PROTOCOL.md).
Commits e títulos de PR seguem [Conventional Commits](.github/TEMPLATES/COMMIT_TEMPLATE.md).
A revisão obrigatória por pasta é definida em [`.github/CODEOWNERS`](.github/CODEOWNERS).

## Licença

[MIT](LICENSE).
