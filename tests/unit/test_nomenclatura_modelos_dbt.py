from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from typing import NamedTuple

import jinja2
import pytest
import yaml

DBT = Path(__file__).resolve().parents[2] / "airflow/dags/dbt"
PACOTE = "compras_gov"
PROJETO = DBT / PACOTE
SIGLAS = {"silver": "slv_", "gold": "gld_"}

LEGADO_SEM_PREFIXO = frozenset(
    {"contratos", "contratos_item", "fornecedor", "orgao", "uasg"}
)


class Modelo(NamedTuple):
    projeto: Path
    caminho: Path
    arquivo: Path

    @property
    def pacote(self) -> str:
        return yaml.safe_load((self.projeto / "dbt_project.yml").read_text())["name"]

    @property
    def nome(self) -> str:
        return self.arquivo.stem

    @property
    def camada(self) -> str:
        return self.caminho.parts[0]

    def __str__(self) -> str:
        return f"{self.pacote}/{self.caminho.as_posix()}"


def _modelos() -> list[Modelo]:
    projetos = sorted(p.parent for p in DBT.glob("*/dbt_project.yml"))
    return [
        Modelo(projeto, sql.relative_to(projeto / "models"), sql)
        for projeto in projetos
        for sql in sorted((projeto / "models").rglob("*.sql"))
    ]


MODELOS = _modelos()
MODELOS_DO_PACOTE = [m for m in MODELOS if m.pacote == PACOTE]


class _Retorno(Exception):
    def __init__(self, valor):
        self.valor = valor


def _chamar_macro(arquivo: Path, nome: str, *args):
    """Executa um macro dbt com jinja puro; o `return` do dbt vira exceção."""

    def retornar(valor):
        raise _Retorno(valor)

    modulo = (
        jinja2.Environment(undefined=jinja2.StrictUndefined)
        .from_string(arquivo.read_text())
        .make_module({"return": retornar})
    )
    try:
        getattr(modulo, nome)(*args)
    except _Retorno as retorno:
        return retorno.valor
    raise AssertionError(f"{arquivo.name}: {nome} terminou sem return")


def _no(modelo: Modelo) -> SimpleNamespace:
    return SimpleNamespace(
        name=modelo.nome, path=modelo.caminho.as_posix(), package_name=modelo.pacote
    )


def _tabela(modelo: Modelo) -> str:
    """Tabela que o dbt cria: o dbt usa o generate_alias_name do próprio pacote
    nos modelos dele; sem macro no pacote, a tabela é o nome do modelo."""
    macro = modelo.projeto / "macros/generate_alias_name.sql"
    if not macro.is_file():
        return modelo.nome
    return _chamar_macro(macro, "generate_alias_name", None, _no(modelo))


@pytest.mark.parametrize("modelo", MODELOS_DO_PACOTE, ids=str)
def test_silver_e_gold_levam_a_sigla_da_camada(modelo):
    if modelo.camada in SIGLAS:
        if modelo.nome in LEGADO_SEM_PREFIXO:
            return
        sigla = SIGLAS[modelo.camada]
        assert modelo.nome.startswith(sigla), (
            f"{modelo}: modelo de {modelo.camada} se chama {sigla}<entidade>.sql "
            f"(ADR-0023); a tabela continua <entidade>."
        )
    else:
        assert not modelo.nome.startswith(
            tuple(SIGLAS.values())
        ), f"{modelo}: só Silver e Gold levam sigla; aqui o nome é a entidade."


@pytest.mark.parametrize("modelo", MODELOS_DO_PACOTE, ids=str)
def test_tabela_e_o_nome_do_modelo_sem_a_sigla(modelo):
    """Silver e Gold perdem a sigla; Bronze e legado mantêm o nome."""
    esperado = modelo.nome
    if modelo.camada in SIGLAS and modelo.nome not in LEGADO_SEM_PREFIXO:
        esperado = modelo.nome.removeprefix(SIGLAS[modelo.camada])
    assert _tabela(modelo) == esperado


def test_pacote_sobrescreve_schema_e_alias():
    """Sem o generate_alias_name, `slv_x` viraria a tabela `slv_x`, sem erro."""
    for macro in ("generate_schema_name", "generate_alias_name"):
        assert (
            PROJETO / "macros" / f"{macro}.sql"
        ).is_file(), f"falta macros/{macro}.sql"


def test_nome_de_modelo_unico_entre_pacotes():
    """Pega também duas Bronzes de sistemas diferentes com a mesma entidade."""
    por_nome = defaultdict(list)
    for modelo in MODELOS:
        por_nome[modelo.nome].append(str(modelo))
    repetidos = {nome: lugares for nome, lugares in por_nome.items() if len(lugares) > 1}
    assert not repetidos, (
        "Nome de modelo repetido. O Cosmos monta o id da task e o --select do teste "
        f"só com o nome, sem o pacote (DuplicateTaskIdFound): {repetidos}"
    )


def test_tabela_fisica_unica():
    """Pega, por exemplo, um slv_x.sql novo ao lado de um x.sql legado na mesma pasta."""
    schema_medallion = DBT / "gov_bricks/macros/schema_medallion.sql"
    por_tabela = defaultdict(list)
    for modelo in MODELOS:
        schema = _chamar_macro(schema_medallion, "schema_medallion", _no(modelo))
        por_tabela[f"{schema}.{_tabela(modelo)}"].append(str(modelo))
    repetidas = {t: lugares for t, lugares in por_tabela.items() if len(lugares) > 1}
    assert not repetidas, f"Dois modelos gravam a mesma tabela: {repetidas}"


def _chaves(no) -> set[str]:
    if isinstance(no, dict):
        return set(no) | {c for v in no.values() for c in _chaves(v)}
    if isinstance(no, list):
        return {c for v in no for c in _chaves(v)}
    return set()


def test_ninguem_fixa_alias_a_mao():
    """A tabela vem só da convenção; um alias manual esconde a quebra dela."""
    for modelo in MODELOS_DO_PACOTE:
        assert "alias=" not in modelo.arquivo.read_text().replace(" ", ""), str(modelo)
    assert not {"alias", "+alias"} & _chaves(
        yaml.safe_load((PROJETO / "dbt_project.yml").read_text())
    )
    for schema in (PROJETO / "models").rglob("*.yml"):
        for entrada in (yaml.safe_load(schema.read_text()) or {}).get("models") or []:
            assert "alias" not in (
                entrada.get("config") or {}
            ), f"{schema}: {entrada['name']}"


def test_lista_de_legado_so_diminui():
    originais = {"contratos", "contratos_item", "fornecedor", "orgao", "uasg"}
    assert LEGADO_SEM_PREFIXO <= originais


def test_legado_listado_ainda_existe_sem_sigla():
    """Quem migrar um modelo legado precisa tirá-lo da lista."""
    existentes = {m.nome for m in MODELOS_DO_PACOTE if m.camada in SIGLAS}
    migrados = LEGADO_SEM_PREFIXO - existentes
    assert not migrados, f"Tire de LEGADO_SEM_PREFIXO: {sorted(migrados)}"
