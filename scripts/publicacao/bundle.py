"""Leitura dos bundles de dashboard exportados do Superset (ADR-0019).

Uma dashboard é construída na interface do Superset, exportada como bundle de
YAML e versionada em ``airflow/dags/superset/<orgao>/<bundle>/``. Este módulo
lê esse bundle para que a validação possa comparar o que ele *realmente* expõe
com o que o catálogo *autoriza* — sem essa leitura, o nível de acesso
declarado seria só uma intenção.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ARQUIVO_METADADOS = "metadata.yaml"
PASTAS = ("databases", "datasets", "charts", "dashboards")


@dataclass(frozen=True)
class DatabaseBundle:
    arquivo: Path
    nome: str
    uuid: str
    uri: str


@dataclass(frozen=True)
class DatasetBundle:
    arquivo: Path
    tabela: str
    schema: str
    uuid: str
    database_uuid: str
    # Colunas que o dataset expõe a quem monta um gráfico. É esta lista, e não
    # a do modelo dbt, que define o que chega à tela.
    colunas: tuple[str, ...] = ()
    # SQL, quando o dataset é virtual (recorte de colunas feito na consulta).
    sql: str | None = None

    @property
    def virtual(self) -> bool:
        return bool(self.sql)


@dataclass(frozen=True)
class GraficoBundle:
    arquivo: Path
    nome: str
    uuid: str
    # UUID do dataset que alimenta o gráfico. É por ele que se sabe se um
    # gráfico do bundle lê algo que o catálogo não declarou.
    dataset_uuid: str


@dataclass(frozen=True)
class DashboardBundle:
    arquivo: Path
    titulo: str
    slug: str
    uuid: str


@dataclass(frozen=True)
class Bundle:
    """Um bundle exportado do Superset, como está no disco."""

    id: str
    caminho: Path
    versao: str
    tipo: str
    databases: tuple[DatabaseBundle, ...] = ()
    datasets: tuple[DatasetBundle, ...] = ()
    dashboards: tuple[DashboardBundle, ...] = ()
    graficos: tuple[GraficoBundle, ...] = ()
    # Arquivos que não puderam ser lidos como YAML, com o erro de cada um.
    ilegiveis: dict[str, str] = field(default_factory=dict)

    def dataset(self, tabela: str) -> DatasetBundle | None:
        for dataset in self.datasets:
            if dataset.tabela == tabela:
                return dataset
        return None


def _arquivos_yaml(pasta: Path) -> list[Path]:
    if not pasta.is_dir():
        return []
    return sorted(p for p in pasta.rglob("*.yaml") if p.is_file())


def _ler(caminho: Path, ilegiveis: dict[str, str]) -> dict[str, Any]:
    try:
        conteudo = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        ilegiveis[caminho.name] = str(exc)
        return {}
    if not isinstance(conteudo, dict):
        ilegiveis[caminho.name] = "não contém um mapeamento YAML no topo"
        return {}
    return conteudo


def _texto(bruto: Any) -> str:
    return str(bruto).strip() if bruto is not None else ""


def carregar(caminho: Path, id_bundle: str | None = None) -> Bundle | None:
    """Lê um bundle do disco. ``None`` quando a pasta não existe."""
    if not caminho.is_dir():
        return None

    ilegiveis: dict[str, str] = {}
    metadados = (
        _ler(caminho / ARQUIVO_METADADOS, ilegiveis)
        if (caminho / ARQUIVO_METADADOS).is_file()
        else {}
    )

    databases = tuple(
        DatabaseBundle(
            arquivo=arquivo,
            nome=_texto(dados.get("database_name")),
            uuid=_texto(dados.get("uuid")),
            uri=_texto(dados.get("sqlalchemy_uri")),
        )
        for arquivo in _arquivos_yaml(caminho / "databases")
        for dados in (_ler(arquivo, ilegiveis),)
    )

    datasets = tuple(
        DatasetBundle(
            arquivo=arquivo,
            tabela=_texto(dados.get("table_name")),
            schema=_texto(dados.get("schema")),
            uuid=_texto(dados.get("uuid")),
            database_uuid=_texto(dados.get("database_uuid")),
            colunas=tuple(
                _texto(coluna.get("column_name"))
                for coluna in (dados.get("columns") or [])
                if isinstance(coluna, dict) and coluna.get("column_name")
            ),
            sql=_texto(dados.get("sql")) or None,
        )
        for arquivo in _arquivos_yaml(caminho / "datasets")
        for dados in (_ler(arquivo, ilegiveis),)
    )

    dashboards = tuple(
        DashboardBundle(
            arquivo=arquivo,
            titulo=_texto(dados.get("dashboard_title")),
            slug=_texto(dados.get("slug")),
            uuid=_texto(dados.get("uuid")),
        )
        for arquivo in _arquivos_yaml(caminho / "dashboards")
        for dados in (_ler(arquivo, ilegiveis),)
    )

    graficos = tuple(
        GraficoBundle(
            arquivo=arquivo,
            nome=_texto(dados.get("slice_name")),
            uuid=_texto(dados.get("uuid")),
            dataset_uuid=_texto(dados.get("dataset_uuid")),
        )
        for arquivo in _arquivos_yaml(caminho / "charts")
        for dados in (_ler(arquivo, ilegiveis),)
    )

    return Bundle(
        id=id_bundle or caminho.name,
        caminho=caminho,
        versao=_texto(metadados.get("version")),
        tipo=_texto(metadados.get("type")),
        databases=databases,
        datasets=datasets,
        dashboards=dashboards,
        graficos=graficos,
        ilegiveis=ilegiveis,
    )
