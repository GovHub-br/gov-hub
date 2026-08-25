"""DAG de publicação dos ativos de BI do MGI (ADR-0019, ADR-0020).

Aplica no Superset o que está versionado no repositório: importa os bundles de
dashboard exportados, garante os papéis do plano de acesso, concede a cada
papel os datasets que ele alcança e instala o recorte de linhas de quem não tem
abrangência total.

O plano de acesso não é escrito aqui: ele é gerado por `make publicacao-sync` a
partir de catalogo/publicacao/mgi.yml e fica em superset/mgi/acesso.yml, ao
lado dos bundles. Esta DAG só o executa.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from airflow.sdk import dag, task

from cliente_superset import ErroSuperset
from superset_helpers import get_superset_client, get_uri_warehouse

ORGAO = "mgi"

# airflow/dags/data_publish/<orgao>/<arquivo>.py -> airflow/dags/superset/<orgao>
DIR_ATIVOS = Path(__file__).resolve().parents[2] / "superset" / ORGAO
CAMINHO_PLANO = DIR_ATIVOS / "acesso.yml"

log = logging.getLogger(__name__)

default_args = {
    "owner": ORGAO,
    "queue": ORGAO,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def _ler_plano() -> dict[str, Any]:
    if not CAMINHO_PLANO.is_file():
        raise ErroSuperset(
            f"Plano de acesso não encontrado: {CAMINHO_PLANO}. Rode: make publicacao-sync"
        )
    conteudo = yaml.safe_load(CAMINHO_PLANO.read_text(encoding="utf-8"))
    if not isinstance(conteudo, dict):
        raise ErroSuperset(f"Plano de acesso ilegível: {CAMINHO_PLANO}")
    return conteudo


@dag(
    dag_id=f"{ORGAO}_publish_dag",
    # Depois da transformação (mgi_transform_dag roda às 06:00): não faz sentido
    # publicar dashboard sobre uma Gold que ainda não foi materializada no dia.
    schedule="0 8 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Publica no Superset as dashboards versionadas do MGI e aplica os papéis "
        "e o recorte de linhas do plano de acesso (ADR-0019, ADR-0020)."
    ),
    tags=["orgao:mgi", "sistema:compras_gov", "camada:gold", "dominio:contratacoes"],
)
def mgi_publish_dag() -> None:
    @task
    def listar_bundles() -> list[str]:
        bundles = _ler_plano().get("bundles") or []
        log.info(
            "[publicacao] %s bundle(s) a importar: %s", len(bundles), ", ".join(bundles)
        )
        return list(bundles)

    @task
    def importar_bundle(bundle: str) -> str:
        cliente = get_superset_client()
        cliente.importar_bundle(DIR_ATIVOS / bundle, uri_database=get_uri_warehouse())
        return bundle

    @task
    def aplicar_papeis() -> int:
        """Cria os papéis e concede a cada um os datasets que ele alcança."""
        plano = _ler_plano()
        cliente = get_superset_client()
        database = plano.get("database") or ""

        aplicados = 0
        for papel in plano.get("papeis") or []:
            id_papel = cliente.garantir_papel(papel["nome"])
            aplicados += 1

            permissoes: list[int] = []
            for qualificado in papel.get("datasets") or []:
                schema, _, tabela = qualificado.rpartition(".")
                id_dataset = cliente.id_do_dataset(tabela, schema or None)
                if id_dataset is None:
                    # O import do bundle é que cria o dataset; se ele não está
                    # lá, publicar a permissão silenciosamente daria um papel
                    # que não enxerga nada.
                    raise ErroSuperset(
                        f"Dataset '{qualificado}' não existe no Superset — o import "
                        f"do bundle falhou ou o catálogo aponta para outro schema."
                    )
                permissao = cliente.permissao_do_dataset(database, tabela, id_dataset)
                if permissao is None:
                    raise ErroSuperset(
                        f"Permissão de acesso ao dataset '{qualificado}' (id {id_dataset}) "
                        "não encontrada no Superset."
                    )
                permissoes.append(permissao)

            cliente.conceder_permissoes(id_papel, permissoes)
            log.info(
                "[publicacao] Papel %s: %s dataset(s) concedido(s).",
                papel["nome"],
                len(permissoes),
            )
        return aplicados

    @task
    def aplicar_recortes() -> int:
        """Instala o filtro de linhas de cada papel sem abrangência total.

        Os ids dos papéis são consultados de novo, em vez de virem por XCom da
        task anterior: assim esta task pode ser reexecutada sozinha depois de
        uma falha, sem depender do resultado guardado da outra.
        """
        plano = _ler_plano()
        cliente = get_superset_client()

        aplicados = 0
        for recorte in plano.get("recortes") or []:
            id_papel = cliente.id_do_papel(recorte["papel"])
            if id_papel is None:
                raise ErroSuperset(
                    f"Recorte '{recorte['nome']}' referencia o papel "
                    f"'{recorte['papel']}', que não existe no Superset."
                )
            ids_dataset = []
            for qualificado in recorte.get("datasets") or []:
                schema, _, tabela = qualificado.rpartition(".")
                id_dataset = cliente.id_do_dataset(tabela, schema or None)
                if id_dataset is None:
                    raise ErroSuperset(
                        f"Recorte '{recorte['nome']}': dataset '{qualificado}' não "
                        "existe no Superset."
                    )
                ids_dataset.append(id_dataset)

            cliente.garantir_recorte(
                nome=recorte["nome"],
                clausula=recorte["clausula"],
                ids_dataset=ids_dataset,
                ids_papel=[id_papel],
                descricao=(
                    "Recorte por órgão gerado a partir de catalogo/publicacao/"
                    f"{ORGAO}.yml (ADR-0020). Não edite pela interface."
                ),
            )
            aplicados += 1
        log.info("[publicacao] %s recorte(s) aplicado(s).", aplicados)
        return aplicados

    importados = importar_bundle.expand(bundle=listar_bundles())
    papeis = aplicar_papeis()
    # O papel só pode receber um dataset que já exista: quem cria o dataset é o
    # import do bundle, e o recorte só se aplica a um papel que já exista.
    importados >> papeis >> aplicar_recortes()


mgi_publish_dag()
