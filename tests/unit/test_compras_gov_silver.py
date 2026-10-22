"""Exceção local do Compras.gov: Silver compartilhada sem alterar o framework."""

from pathlib import Path
from types import SimpleNamespace

import jinja2
import pytest
import yaml

DBT = Path(__file__).resolve().parents[2] / "airflow/dags/dbt"


class Retorno(Exception):
    def __init__(self, valor):
        self.valor = valor


def renderizar_macro(arquivo, nome, *args, **contexto):
    def retornar(valor):
        raise Retorno(valor)

    modulo = (
        jinja2.Environment(undefined=jinja2.StrictUndefined)
        .from_string(arquivo.read_text())
        .make_module({"return": retornar, **contexto})
    )
    with pytest.raises(Retorno) as resultado:
        getattr(modulo, nome)(*args)
    return resultado.value.valor


def schema_padrao(node):
    return renderizar_macro(
        DBT / "gov_bricks/macros/schema_medallion.sql", "schema_medallion", node
    )


@pytest.mark.parametrize("dominio", ["arp", "contratacoes", "organizacional", "futuro"])
def test_schema_compartilhado_so_no_compras_gov(dominio):
    config = yaml.safe_load((DBT / "compras_gov/dbt_project.yml").read_text())
    silver = config["models"]["compras_gov"]["silver"]
    node = SimpleNamespace(
        path=f"silver/{dominio}/entidade.sql", package_name="compras_gov"
    )
    assert (
        renderizar_macro(
            DBT / "compras_gov/macros/generate_schema_name.sql",
            "generate_schema_name",
            silver["+schema"],
            node,
            gov_bricks=SimpleNamespace(schema_medallion=schema_padrao),
        )
        == "002_slv_compras_gov"
    )
    assert schema_padrao(node) == f"002_slv_{dominio}"


@pytest.mark.parametrize(
    "tipo,banco,esperado",
    [
        ("duckdb", "govhub_local", "data_warehouse"),
        ("postgres", "warehouse_local", "warehouse_local"),
    ],
)
def test_database_silver_respeita_alias_duckdb_e_banco_postgres(tipo, banco, esperado):
    config = yaml.safe_load((DBT / "compras_gov/dbt_project.yml").read_text())
    expressao = config["models"]["compras_gov"]["silver"]["+database"]
    assert (
        jinja2.Template(expressao).render(
            target=SimpleNamespace(type=tipo, database=banco)
        )
        == esperado
    )


def test_bronze_e_outros_pacotes_mantem_convencao():
    for caminho, pacote, esperado in [
        ("bronze/arp.sql", "compras_gov", "001_bnz_compras_gov"),
        ("silver/contratos/contrato.sql", "contratos_gov", "002_slv_contratos"),
        ("gold/contratacoes/contratos_por_orgao.sql", "mgi", "003_gld_contratacoes"),
    ]:
        assert (
            schema_padrao(SimpleNamespace(path=caminho, package_name=pacote)) == esperado
        )
    for pacote in ("mgi", "contratos_gov"):
        config = yaml.safe_load((DBT / pacote / "dbt_project.yml").read_text())
        assert config["models"][pacote].get("silver", {}).get("+schema") is None


def test_arp_usa_nome_do_arquivo_sem_alias():
    pasta = DBT / "compras_gov/models/silver/arp"
    nome = "silver_compras_gov_arp"
    assert (pasta / f"{nome}.sql").exists()
    assert "alias=" not in (pasta / f"{nome}.sql").read_text()
    assert yaml.safe_load((pasta / "schema.yml").read_text())["models"][0]["name"] == nome
