# Como criar uma Silver nova

Guia de uma página para Silvers do compras_gov construídas sobre uma Bronze
em Parquet (o ramo DuckDB). Exemplo de referência: a ARP. As regras vêm do
[ADR-0009](../adr/0009-nomenclatura-pastas-arquivos-dbt.md) e do
[ADR-0010](../adr/0010-nomenclatura-schemas-tabelas-bronze-silver-gold.md).

## A regra em uma tabela

| Camada | Arquivo | Tabela criada | ARP |
|---|---|---|---|
| Bronze | dbt/compras_gov/models/bronze/<entidade>.sql | 001_bnz_compras_gov.<entidade> | bronze/arp.sql → 001_bnz_compras_gov.arp |
| Silver | dbt/compras_gov/models/silver/<dominio>/slv_<entidade>.sql | 002_slv_<dominio>.<entidade> | silver/arp/slv_arp.sql → 002_slv_arp.arp |

- **Silver leva `slv_`** no nome do modelo. A tabela fica sem a sigla: o
generate_alias_name do compras_gov a remove, também quando a DAG roda a
partir do projeto mgi. Os outros pacotes ainda não têm esse macro: lá,
slv_x.sql criaria a tabela slv_x. Não use config(alias=...) nem +schema.
- **Bronze não leva sigla.** O nome dela é a entidade da raw, e dele saem o
caminho do Parquet e o Asset que agenda a DAG.
- **O sistema não entra no nome.** Ele já está no pacote (dbt/<sistema>/).
A pasta da Silver é o domínio, que também vira o schema.

## Passo a passo

1. **Bronze.** Se ainda não existe, crie models/bronze/<entidade>.sql só com
{{ gov_bricks.bronze_parquet() }} e siga a receita "Novo domínio lendo a
raw em Parquet" da seção 5 do [AGENTS.md](../../AGENTS.md): o outlet na
DAG de ingestão, o origem_atual no catálogo e a amostra em AMOSTRAS.
2. **Silver.** Crie models/silver/<dominio>/slv_<entidade>.sql, que lê a
Bronze com {{ ref("<entidade>") }}. Use colunas explícitas (nunca
select *) em snake_case. Se partir de
make modelo ARGS="--camada silver --sistema compras_gov --entidade <entidade>",
crie antes a Bronze do passo 1: o arquivo sai slv_<entidade>.sql e lê a
Bronze por ref("<entidade>") quando models/bronze/<entidade>.sql já
existe. Gerada antes da Bronze, a Silver sai com source(...): troque por
ref("<entidade>"), senão a task da Silver não espera a da Bronze.
3. **`schema.yml`** na mesma pasta, com o nome do modelo (com a sigla) e os
metadados do ADR-0013. Coluna sem classificacao conta como pessoal.

version: 2

models:
- name: slv_<entidade>
description: O que a tabela é e o que já foi tratado.
meta:
owner: "@GovHub-br/oss"
sistema_origem: <sistema>
camada: silver
classificacao: publico
data_tests:
# Silver inicial (só renomeia): mesmas linhas e valores da Bronze.
- gov_bricks.mesma_contagem:
arguments:
comparar_com: ref("<entidade>")
- gov_bricks.mesmo_conteudo_em_snake_case:
arguments:
comparar_com: ref("<entidade>")
columns:
- name: <coluna>
description: O que a coluna significa.
meta: {classificacao: publico}

Quando a Silver passar a tratar o dado (deduplicar, tipar), tire os dois
testes de Silver inicial e teste a chave: gov_bricks.unicidade_composta,
not_null, unique.
4. **Registrar na DAG.** O arquivo da DAG não muda. No dbt_project.yml do
pacote, liste a pasta do domínio com a tag duckdb:

models:
compras_gov:
silver:
+materialized: table
<dominio>:
+tags: ["duckdb"]

A duckdb_<orgao>_transform_dag seleciona tag:duckdb, desde que o
projeto do órgão importe o pacote no packages.yml (o mgi já importa o
compras_gov). A task da Silver se chama slv_<entidade>_run, ou vira o
grupo slv_<entidade> (.run e .test) quando há teste só dela.

## Antes de abrir o PR

uv run pytest tests/unit/test_nomenclatura_modelos_dbt.py \
tests/unit/test_compras_gov_silver.py tests/unit/test_fluxo_bronze_parquet_dbt.py \
tests/unit/test_data_transform_dags.py -q
cd airflow/dags/dbt/mgi && DBT_PROFILES_DIR=.. DUCKDB_GOVHUB_PATH=:memory: \
dbt ls --target prod_duckdb --select slv_<entidade> # o modelo e só os testes dele
make lint && make test

## O que a guarda reprova

tests/unit/test_nomenclatura_modelos_dbt.py, que roda no CI, reprova: