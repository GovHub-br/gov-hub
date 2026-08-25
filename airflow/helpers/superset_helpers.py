"""Acesso ao Superset a partir de uma Connection do Airflow (ADR-0019).

Espelha o que `postgres_helpers` faz com o banco: a credencial fica na
Connection do Airflow, não no código nem no bundle versionado.
"""

from __future__ import annotations

import logging
import os

from airflow.sdk import BaseHook

from cliente_superset import ClienteSuperset

CONEXAO_PADRAO = "superset_default"


def get_superset_client(conn_id: str = CONEXAO_PADRAO) -> ClienteSuperset:
    """Monta um cliente autenticável do Superset a partir da Connection."""
    conexao = BaseHook.get_connection(conn_id)
    esquema = conexao.schema or "http"
    porta = f":{conexao.port}" if conexao.port else ""
    base_url = f"{esquema}://{conexao.host}{porta}"

    extras = conexao.extra_dejson if conexao.extra else {}
    logging.info("[superset_helpers] Cliente do Superset em %s.", base_url)
    return ClienteSuperset(
        base_url=base_url,
        usuario=conexao.login or "",
        senha=conexao.password or "",
        provider=str(extras.get("provider", "db")),
    )


def get_uri_warehouse() -> str | None:
    """URI de conexão do warehouse que o bundle deve usar neste ambiente.

    Vem de SUPERSET_DW_URI; sem ela, o bundle é importado com a URI que ele
    traz — o que só serve ao ambiente onde ele foi exportado.
    """
    return os.environ.get("SUPERSET_DW_URI") or None
