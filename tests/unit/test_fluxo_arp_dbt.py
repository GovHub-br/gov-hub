"""Exercita os SQLs reais da ARP sem serviços externos nem limpeza de dados."""

import os
import re
from collections import Counter
from pathlib import Path

import duckdb
import pytest
import yaml
from fsspec.implementations.dirfs import DirFileSystem
from fsspec.implementations.local import LocalFileSystem
from jinja2 import Environment, StrictUndefined

PROJETO = Path(__file__).resolve().parents[2] / "airflow/dags/dbt/compras_gov"
BRONZE = PROJETO / "models/bronze/arp.sql"
SILVER = PROJETO / "models/silver/arp/silver_compras_gov_arp.sql"

# Contrato observado nos Parquets da ARP. Inclui os tipos não textuais para
# detectar conversões acidentais, além de valores que a futura limpeza tratará.
COLUNAS = [
    "numeroAtaRegistroPreco",
    "codigoUnidadeGerenciadora",
    "nomeUnidadeGerenciadora",
    "codigoOrgao",
    "nomeOrgao",
    "linkAtaPNCP",
    "linkCompraPNCP",
    "numeroCompra",
    "anoCompra",
    "codigoModalidadeCompra",
    "nomeModalidadeCompra",
    "dataAssinatura",
    "dataVigenciaInicial",
    "dataVigenciaFinal",
    "valorTotal",
    "statusAta",
    "objeto",
    "quantidadeItens",
    "dataHoraAtualizacao",
    "dataHoraInclusao",
    "dataHoraExclusao",
    "ataExcluido",
    "numeroControlePncpAta",
    "numeroControlePncpCompra",
    "idCompra",
    "dt_ingest",
]


def renderizar(caminho):
    return (
        Environment(undefined=StrictUndefined)
        .from_string(caminho.read_text())
        .render(
            config=lambda **kwargs: "",
            env_var=os.getenv,
            ref=lambda nome: f'"{nome}"',
        )
    )


@pytest.mark.parametrize("bucket", [None, "outro-bucket"])
def test_parquet_bronze_silver_preserva_linhas_valores_e_tipos(
    tmp_path, monkeypatch, bucket
):
    if bucket is None:
        monkeypatch.delenv("MINIO_BUCKET", raising=False)
    else:
        monkeypatch.setenv("MINIO_BUCKET", bucket)

    class S3Local(DirFileSystem):
        protocol = "s3"

    with duckdb.connect() as conexao:
        conexao.register_filesystem(S3Local(path=str(tmp_path), fs=LocalFileSystem()))
        tipos = {
            "codigoOrgao": "BIGINT",
            "quantidadeItens": "BIGINT",
            "valorTotal": "DOUBLE",
            "ataExcluido": "BOOLEAN",
        }
        declaracoes = ", ".join(f'"{c}" {tipos.get(c, "VARCHAR")}' for c in COLUNAS)
        conexao.execute(f"create table amostra ({declaracoes})")
        linha: list[object] = ["  original  " for _ in COLUNAS]
        for coluna, valor in {
            "codigoOrgao": 48000,
            "quantidadeItens": 0,
            "valorTotal": 12.5,
            "ataExcluido": True,
            "dataAssinatura": "data inválida",
            "dataHoraExclusao": None,
        }.items():
            linha[COLUNAS.index(coluna)] = valor
        conexao.executemany(
            f"insert into amostra values ({', '.join('?' for _ in COLUNAS)})",
            [linha, linha, [None] * len(COLUNAS)],
        )
        pasta = tmp_path / (bucket or "data-lake") / "compras_gov/arp/2026/10"
        pasta.mkdir(parents=True)
        conexao.execute(
            "copy amostra to ? (format parquet)", [str(pasta / "parte.parquet")]
        )
        sql_bronze = renderizar(BRONZE)
        assert f"s3://{bucket or 'data-lake'}/compras_gov/arp/" in sql_bronze
        conexao.execute(f"create table arp as {sql_bronze}")
        sql_silver = renderizar(SILVER)
        for _ in range(2):
            conexao.execute(
                f"create or replace table silver_compras_gov_arp as {sql_silver}"
            )
            assert Counter(
                conexao.sql("select * from silver_compras_gov_arp").fetchall()
            ) == Counter(conexao.sql("select * from arp").fetchall())
        descricao = conexao.sql("describe silver_compras_gov_arp").fetchall()
        assert [c[1] for c in descricao] == [
            c[1] for c in conexao.sql("describe arp").fetchall()
        ]
        metadados = yaml.safe_load(SILVER.with_name("schema.yml").read_text())["models"][
            0
        ]
        assert [c["name"] for c in metadados["columns"]] == [c[0] for c in descricao]
        assert all(re.fullmatch("[a-z][a-z0-9_]*", c[0]) for c in descricao)
        assert all(
            c["description"] and c["meta"]["classificacao"] == "publico"
            for c in metadados["columns"]
        )
        teste = renderizar(PROJETO / "tests/silver_compras_gov_arp_contagem.sql")
        teste_conteudo = renderizar(PROJETO / "tests/silver_compras_gov_arp_conteudo.sql")
        assert conexao.sql(teste).fetchall() == []
        assert conexao.sql(teste_conteudo).fetchall() == []
        conexao.execute(
            "update silver_compras_gov_arp set nome_orgao = 'alterado' "
            "where nome_orgao is not null"
        )
        assert conexao.sql(teste).fetchall() == []
        assert len(conexao.sql(teste_conteudo).fetchall()) == 4
        conexao.execute("delete from silver_compras_gov_arp where ata_excluido is null")
        assert conexao.sql(teste).fetchall() == [(1,)]


def test_source_arp_aponta_para_a_bronze_materializada():
    fontes = yaml.safe_load((PROJETO / "models/bronze/sources.yml").read_text())[
        "sources"
    ]
    bronze = next(f for f in fontes if f["name"] == "compras_gov_bronze")
    assert bronze["schema"] == "001_bnz_compras_gov"
    assert next(t for t in bronze["tables"] if t["name"] == "arp")["identifier"] == "arp"
    raw = next(f for f in fontes if f["name"] == "compras_gov")
    assert all(t["name"] != "arp" for t in raw["tables"])
    assert '{{ ref("arp") }}' in SILVER.read_text()
