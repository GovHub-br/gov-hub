"""Carregamento do catálogo de publicação (ADR-0019, ADR-0020).

O vocabulário de sensibilidade é o mesmo do catálogo de sistemas
estruturantes — classificação, ordem de restrição e o tipo ``Problema`` vêm de
``scripts.modelagem.catalogo``, para que "pessoal" signifique exatamente a
mesma coisa nos dois catálogos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..modelagem.catalogo import (
    ORDEM_CLASSIFICACAO,
    RAIZ,
    ErroCatalogo,
)

DIR_CATALOGO = RAIZ / "catalogo"
DIR_PUBLICACAO = DIR_CATALOGO / "publicacao"
ARQUIVO_ACESSO = DIR_CATALOGO / "acesso.yml"

# Onde vivem os artefatos que este catálogo governa.
DIR_SUPERSET = RAIZ / "airflow" / "dags" / "superset"
DIR_DBT = RAIZ / "airflow" / "dags" / "dbt"
DIR_RELATORIOS = RAIZ / "airflow" / "dags" / "data_report"

ABRANGENCIAS = frozenset({"proprio", "total"})
FORMATOS = frozenset({"csv", "parquet"})
DESTINOS = frozenset({"storage", "email"})

# Nome do arquivo gerado com o plano de acesso de cada órgão.
ARQUIVO_PLANO = "acesso.yml"


@dataclass(frozen=True)
class Nivel:
    """Um nível de acesso: quais classificações ele enxerga."""

    id: str
    nome: str
    descricao: str
    ve_classificacoes: tuple[str, ...]

    def ve(self, classificacao: str) -> bool:
        return classificacao in self.ve_classificacoes


@dataclass(frozen=True)
class Acesso:
    """O vocabulário de níveis de acesso (``catalogo/acesso.yml``)."""

    niveis: dict[str, Nivel]
    prefixo_papel: str
    papel_herda: str
    chave_recorte: str
    sufixo_recorte: str

    def nivel(self, id_nivel: str) -> Nivel:
        try:
            return self.niveis[id_nivel]
        except KeyError:
            conhecidos = ", ".join(self.ordenados()) or "nenhum"
            raise ErroCatalogo(
                f"Nível de acesso '{id_nivel}' não existe. Declarados: {conhecidos}."
            ) from None

    def ordenados(self) -> list[str]:
        """Níveis do menos para o mais abrangente."""
        return sorted(
            self.niveis,
            key=lambda id_nivel: len(self.niveis[id_nivel].ve_classificacoes),
        )

    def alcanca(self, nivel_de: str, nivel_ate: str) -> bool:
        """Diz se quem tem ``nivel_de`` enxerga tudo o que ``nivel_ate`` exige."""
        visto = set(self.nivel(nivel_de).ve_classificacoes)
        return set(self.nivel(nivel_ate).ve_classificacoes).issubset(visto)

    def papel(self, orgao: str, nivel: str) -> str:
        return f"{self.prefixo_papel}_{orgao}_{nivel}"

    def filtro_recorte(self, orgao: str) -> str:
        return f"{self.prefixo_papel}_{orgao}_{self.sufixo_recorte}"


@dataclass(frozen=True)
class Dataset:
    """Um dataset publicado — um modelo dbt exposto na ferramenta de BI."""

    id: str
    modelo: str
    descricao: str
    nivel: str
    recorte: bool = False

    @property
    def camada(self) -> str:
        """Camada do modelo dbt (``gold/produto/entidade`` → ``gold``)."""
        return self.modelo.split("/", 1)[0] if self.modelo else ""


@dataclass(frozen=True)
class Dashboard:
    """Uma dashboard versionada como bundle exportado do Superset."""

    id: str
    titulo: str
    descricao: str
    bundle: str
    nivel: str
    datasets: tuple[str, ...] = ()


@dataclass(frozen=True)
class Relatorio:
    """Um relatório periódico entregue fora da ferramenta de BI."""

    id: str
    titulo: str
    descricao: str
    dag: str
    dataset: str
    formato: str
    destinos: tuple[str, ...]
    nivel: str
    destinatarios_variavel: str | None = None


@dataclass(frozen=True)
class Consumidor:
    """Um órgão que consome o que outro publica — vira papel no Superset."""

    id: str
    nome: str
    nivel: str
    codigo_orgao: str
    abrangencia: str
    codigo_orgao_verificado: bool = False
    dashboards: tuple[str, ...] = ()
    relatorios: tuple[str, ...] = ()

    @property
    def tem_recorte(self) -> bool:
        """Só quem não tem abrangência total é filtrado por órgão."""
        return self.abrangencia != "total"


@dataclass(frozen=True)
class Publicacao:
    """O que um órgão publica e quem consome."""

    orgao: str
    nome: str
    owner: str
    database: str
    datasets: dict[str, Dataset] = field(default_factory=dict)
    dashboards: dict[str, Dashboard] = field(default_factory=dict)
    relatorios: dict[str, Relatorio] = field(default_factory=dict)
    consumidores: dict[str, Consumidor] = field(default_factory=dict)

    @property
    def dir_bundles(self) -> Path:
        return DIR_SUPERSET / self.orgao

    @property
    def dir_dbt(self) -> Path:
        return DIR_DBT / self.orgao

    @property
    def dir_relatorios(self) -> Path:
        return DIR_RELATORIOS / self.orgao

    @property
    def caminho_plano(self) -> Path:
        """Onde vive o plano de acesso gerado, ao alcance da DAG de publicação."""
        return self.dir_bundles / ARQUIVO_PLANO


@dataclass(frozen=True)
class CatalogoPublicacao:
    """Os níveis de acesso e a publicação declarada de cada órgão."""

    acesso: Acesso
    orgaos: dict[str, Publicacao]

    def orgao(self, id_orgao: str) -> Publicacao:
        try:
            return self.orgaos[id_orgao]
        except KeyError:
            conhecidos = ", ".join(sorted(self.orgaos)) or "nenhum"
            raise ErroCatalogo(
                f"Órgão '{id_orgao}' não tem catálogo de publicação. "
                f"Catalogados: {conhecidos}."
            ) from None


def classificacao_acima_de(classificacao: str, nivel: Nivel) -> bool:
    """Diz se a classificação está fora do que o nível pode ver."""
    return not nivel.ve(classificacao)


def mais_restritiva(classificacoes: list[str]) -> str:
    """A classificação mais restritiva da lista; ``publico`` se vazia."""
    posicao = max(
        (
            ORDEM_CLASSIFICACAO.index(c)
            for c in classificacoes
            if c in ORDEM_CLASSIFICACAO
        ),
        default=0,
    )
    return ORDEM_CLASSIFICACAO[posicao]


def _ler_yaml(caminho: Path) -> dict[str, Any]:
    try:
        conteudo = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ErroCatalogo(f"YAML inválido em {caminho}: {exc}") from exc
    if not isinstance(conteudo, dict):
        raise ErroCatalogo(f"{caminho} não contém um mapeamento YAML no topo.")
    return conteudo


def _texto(bruto: Any) -> str:
    return str(bruto).strip() if bruto is not None else ""


def _lista(bruto: Any) -> tuple[str, ...]:
    if not bruto:
        return ()
    if isinstance(bruto, str):
        return (bruto.strip(),)
    return tuple(_texto(item) for item in bruto)


def carregar(dir_catalogo: Path | None = None) -> CatalogoPublicacao:
    """Lê o catálogo de publicação do disco.

    Como no catálogo de modelagem, campo ausente vira valor vazio em vez de
    exceção: quem aponta o que falta é ``validacao``, para que um catálogo
    incompleto ainda possa ser inspecionado.
    """
    base = dir_catalogo or DIR_CATALOGO
    arquivo_acesso = base / "acesso.yml"
    if not arquivo_acesso.is_file():
        raise ErroCatalogo(
            f"Arquivo de níveis de acesso não encontrado: {arquivo_acesso}"
        )

    acesso = _carregar_acesso(arquivo_acesso)

    orgaos: dict[str, Publicacao] = {}
    dir_publicacao = base / "publicacao"
    for arquivo in (
        sorted(dir_publicacao.glob("*.yml")) if dir_publicacao.is_dir() else []
    ):
        if arquivo.name.startswith("_"):
            continue
        publicacao = _carregar_publicacao(arquivo)
        orgaos[publicacao.orgao] = publicacao

    return CatalogoPublicacao(acesso=acesso, orgaos=orgaos)


def _carregar_acesso(arquivo: Path) -> Acesso:
    bruto = _ler_yaml(arquivo)
    niveis = {
        id_nivel: Nivel(
            id=id_nivel,
            nome=_texto(dados.get("nome")),
            descricao=_texto(dados.get("descricao")),
            ve_classificacoes=_lista(dados.get("ve_classificacoes")),
        )
        for id_nivel, dados in (bruto.get("niveis") or {}).items()
        if isinstance(dados, dict)
    }
    papel = bruto.get("papel") or {}
    recorte = bruto.get("recorte") or {}
    return Acesso(
        niveis=niveis,
        prefixo_papel=_texto(papel.get("prefixo")),
        papel_herda=_texto(papel.get("herda")),
        chave_recorte=_texto(recorte.get("chave")),
        sufixo_recorte=_texto(recorte.get("sufixo")),
    )


def _carregar_publicacao(arquivo: Path) -> Publicacao:
    bruto = _ler_yaml(arquivo)

    datasets = {
        id_dataset: Dataset(
            id=id_dataset,
            modelo=_texto(dados.get("modelo")),
            descricao=_texto(dados.get("descricao")),
            nivel=_texto(dados.get("nivel")),
            recorte=bool(dados.get("recorte", False)),
        )
        for id_dataset, dados in (bruto.get("datasets") or {}).items()
        if isinstance(dados, dict)
    }

    dashboards = {
        id_dash: Dashboard(
            id=id_dash,
            titulo=_texto(dados.get("titulo")),
            descricao=_texto(dados.get("descricao")),
            bundle=_texto(dados.get("bundle")),
            nivel=_texto(dados.get("nivel")),
            datasets=_lista(dados.get("datasets")),
        )
        for id_dash, dados in (bruto.get("dashboards") or {}).items()
        if isinstance(dados, dict)
    }

    relatorios = {
        id_rel: Relatorio(
            id=id_rel,
            titulo=_texto(dados.get("titulo")),
            descricao=_texto(dados.get("descricao")),
            dag=_texto(dados.get("dag")),
            dataset=_texto(dados.get("dataset")),
            formato=_texto(dados.get("formato")),
            destinos=_lista(dados.get("destinos")),
            nivel=_texto(dados.get("nivel")),
            destinatarios_variavel=_texto(dados.get("destinatarios_variavel")) or None,
        )
        for id_rel, dados in (bruto.get("relatorios") or {}).items()
        if isinstance(dados, dict)
    }

    consumidores = {
        id_cons: Consumidor(
            id=id_cons,
            nome=_texto(dados.get("nome")),
            nivel=_texto(dados.get("nivel")),
            codigo_orgao=_texto(dados.get("codigo_orgao")),
            abrangencia=_texto(dados.get("abrangencia")),
            codigo_orgao_verificado=bool(dados.get("codigo_orgao_verificado", False)),
            dashboards=_lista(dados.get("dashboards")),
            relatorios=_lista(dados.get("relatorios")),
        )
        for id_cons, dados in (bruto.get("consumidores") or {}).items()
        if isinstance(dados, dict)
    }

    return Publicacao(
        orgao=_texto(bruto.get("orgao")) or arquivo.stem,
        nome=_texto(bruto.get("nome")),
        owner=_texto(bruto.get("owner")),
        database=_texto(bruto.get("database")),
        datasets=datasets,
        dashboards=dashboards,
        relatorios=relatorios,
        consumidores=consumidores,
    )
