"""Leitura da classificação de sensibilidade declarada nos modelos dbt.

A classificação de uma coluna é declarada uma única vez, no ``schema.yml`` do
modelo que a produz (ADR-0013). A publicação não redeclara nada: ela lê dali
para decidir quem pode ver o quê. É isso que faz a decisão de acesso seguir a
coluna quando o modelo muda, em vez de envelhecer numa lista à parte.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .catalogo import DIR_DBT

# ADR-0013: coluna sem classificação explícita é tratada como dado pessoal —
# o padrão falha para o lado restritivo.
CLASSIFICACAO_PADRAO = "pessoal"


@dataclass(frozen=True)
class ModeloDbt:
    """Um modelo dbt e a sensibilidade declarada dele e de suas colunas."""

    nome: str
    projeto: str
    caminho_sql: Path
    caminho_schema: Path | None
    descricao: str
    classificacao: str
    # Apenas as colunas documentadas em schema.yml. Coluna que o modelo produz
    # e ninguém documentou não aparece aqui — e a validação trata essa ausência
    # como informação, não como ausência de risco.
    colunas: dict[str, str]

    def classificacao_de(self, coluna: str) -> str | None:
        return self.colunas.get(coluna)


def _ler_yaml(caminho: Path) -> dict[str, Any]:
    conteudo = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    return conteudo if isinstance(conteudo, dict) else {}


def _projetos(dir_dbt: Path) -> list[Path]:
    return [p for p in sorted(dir_dbt.iterdir()) if (p / "dbt_project.yml").is_file()]


def localizar_sql(orgao: str, modelo: str, dir_dbt: Path | None = None) -> Path | None:
    """Acha o ``.sql`` de um modelo, no projeto do órgão ou nos pacotes dele.

    O caminho declarado no catálogo (``gold/produto/entidade``) é relativo a
    ``models/``. Um órgão pode publicar tanto a Gold que ele materializa quanto
    a Silver de um pacote de sistema estruturante que ele importa.
    """
    base = dir_dbt or DIR_DBT
    if not base.is_dir():
        return None

    candidato = base / orgao / "models" / f"{modelo}.sql"
    if candidato.is_file():
        return candidato

    for projeto in _projetos(base):
        candidato = projeto / "models" / f"{modelo}.sql"
        if candidato.is_file():
            return candidato
    return None


def carregar_modelo(
    orgao: str, modelo: str, dir_dbt: Path | None = None
) -> ModeloDbt | None:
    """Lê o modelo e o ``schema.yml`` da pasta dele. ``None`` se o SQL não existe."""
    caminho_sql = localizar_sql(orgao, modelo, dir_dbt)
    if caminho_sql is None:
        return None

    nome = caminho_sql.stem
    projeto = _nome_do_projeto(caminho_sql)
    caminho_schema = caminho_sql.parent / "schema.yml"
    if not caminho_schema.is_file():
        return ModeloDbt(
            nome=nome,
            projeto=projeto,
            caminho_sql=caminho_sql,
            caminho_schema=None,
            descricao="",
            classificacao=CLASSIFICACAO_PADRAO,
            colunas={},
        )

    declarado: dict[str, Any] = {}
    for entrada in _ler_yaml(caminho_schema).get("models") or []:
        if isinstance(entrada, dict) and entrada.get("name") == nome:
            declarado = entrada
            break

    meta = declarado.get("meta") or {}
    colunas: dict[str, str] = {}
    for coluna in declarado.get("columns") or []:
        if not isinstance(coluna, dict) or not coluna.get("name"):
            continue
        meta_coluna = coluna.get("meta") or {}
        colunas[str(coluna["name"])] = str(
            meta_coluna.get("classificacao") or CLASSIFICACAO_PADRAO
        )

    return ModeloDbt(
        nome=nome,
        projeto=projeto,
        caminho_sql=caminho_sql,
        caminho_schema=caminho_schema,
        descricao=str(declarado.get("description") or "").strip(),
        classificacao=str(meta.get("classificacao") or CLASSIFICACAO_PADRAO),
        colunas=colunas,
    )


def _nome_do_projeto(caminho_sql: Path) -> str:
    """Nome do projeto dbt a que o arquivo pertence (a pasta acima de models/)."""
    for pai in caminho_sql.parents:
        if (pai / "dbt_project.yml").is_file():
            return pai.name
    return ""
