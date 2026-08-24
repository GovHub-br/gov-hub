"""Sincronização das chaves conformadas com os macros dbt (ADR-0017).

O macro ``chave_conformada`` precisa conhecer a normalização de cada chave, e
essa informação vive em ``catalogo/chaves.yml``. Em vez de duplicá-la à mão no
dbt — onde ela silenciosamente divergiria —, o arquivo de macros é *gerado* a
partir do catálogo, no mesmo espírito do ``requirements.txt``: artefato
derivado, verificado no CI, nunca editado à mão.
"""

from __future__ import annotations

from pathlib import Path

from .catalogo import Catalogo
from .gerador import DIR_DBT, Escrita, _escrever

PACOTE_BASE = "gov_bricks"
ARQUIVO_MACRO = DIR_DBT / PACOTE_BASE / "macros" / "chaves_geradas.sql"


def renderizar(catalogo: Catalogo) -> str:
    """Conteúdo do macro que devolve as chaves conformadas do catálogo."""
    linhas = [
        "{#",
        "    GERADO por `make catalogo-sync` a partir de catalogo/chaves.yml.",
        "    Não edite à mão — a edição é desfeita na próxima geração e o CI",
        "    reprova o build quando este arquivo diverge do catálogo.",
        "#}",
        "{% macro chaves_conformadas() %}",
        "    {{",
        "        return(",
        "            {",
    ]
    for id_chave in sorted(catalogo.chaves):
        chave = catalogo.chaves[id_chave]
        tamanho = chave.tamanho if chave.tamanho else "none"
        linhas.append(
            f'                "{id_chave}": '
            f'{{"normalizacao": "{chave.normalizacao}", "tamanho": {tamanho}, '
            f'"classificacao": "{chave.classificacao}"}},'
        )
    linhas += [
        "            }",
        "        )",
        "    }}",
        "{% endmacro %}",
        "",
    ]
    return "\n".join(linhas)


def sincronizar(catalogo: Catalogo, caminho: Path | None = None) -> list[Escrita]:
    """Regrava o macro gerado a partir do catálogo."""
    destino = caminho or ARQUIVO_MACRO
    return [_escrever(destino, renderizar(catalogo), forcar=True)]


def esta_sincronizado(catalogo: Catalogo, caminho: Path | None = None) -> bool:
    """Diz se o macro no disco corresponde ao catálogo atual."""
    destino = caminho or ARQUIVO_MACRO
    if not destino.is_file():
        return False
    return destino.read_text(encoding="utf-8") == renderizar(catalogo)
