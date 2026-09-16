import logging
from datetime import datetime, timedelta

from airflow.sdk import dag, task

from cliente_camara_deputados import ClienteCamaraDeputados
from landing_zone import write_raw

SISTEMA = "camara_deputados"
ENTIDADE = "deputados"
PRIMARY_KEY = ["id", "siglaPartido", "idLegislatura"]

default_args = {
    "owner": "camara_deputados",
    "queue": "camara_deputados",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="deputados_ingest_dag",
    schedule="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere o cadastro de deputados federais da API da Câmara dos "
        "Deputados para camara_deputados.raw_deputados."
    ),
    tags=["sistema:camara_deputados", "dominio:parlamentares"],
)
def deputados_ingest_dag() -> None:
    @task
    def fetch_and_store_deputados() -> dict:
        api = ClienteCamaraDeputados()
        deputados = api.get_all_deputados()

        if not deputados:
            logging.warning("[deputados_ingest_dag] Nenhum deputado encontrado.")
            return {ENTIDADE: 0}

        # A API não garante uma linha por combinação (id, partido,
        # legislatura) livre de repetição entre páginas; deduplica em memória
        # para não estourar o ON CONFLICT com duas linhas de mesma chave no
        # mesmo lote (portado de data-application-mir).
        vistos: set[tuple] = set()
        registros = []
        for item in deputados:
            if item.get("siglaPartido") is None:
                item["siglaPartido"] = "Sem Partido"
            chave = tuple(item.get(campo) for campo in PRIMARY_KEY)
            if chave in vistos:
                continue
            vistos.add(chave)
            registros.append(item)

        write_raw(SISTEMA, ENTIDADE, registros, primary_key=PRIMARY_KEY)
        logging.info("[deputados_ingest_dag] %s deputado(s) ingerido(s).", len(registros))
        return {ENTIDADE: len(registros)}

    fetch_and_store_deputados()


deputados_ingest_dag()
