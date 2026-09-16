import logging
from datetime import datetime, timedelta

from airflow.sdk import dag, task

from cliente_transferegov_emendas import ClienteTransfereGov
from landing_zone import write_raw

SISTEMA = "transferegov_emendas"
ENTIDADE = "empenhos_especiais"
PRIMARY_KEY = ["id_empenho"]

default_args = {
    "owner": "transferegov_emendas",
    "queue": "transferegov_emendas",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="empenhos_especiais_ingest_dag",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere os empenhos de transferências especiais (emendas parlamentares "
        "individuais) da API do TransfereGov para "
        "transferegov_emendas.raw_empenhos_especiais. Fonte 100% nacional, sem "
        "filtro de órgão."
    ),
    tags=["sistema:transferegov_emendas", "dominio:emendas_parlamentares"],
)
def empenhos_especiais_ingest_dag() -> None:
    @task
    def fetch_and_store() -> dict:
        api = ClienteTransfereGov()
        registros = api.get_all_empenhos_especiais(page_size=1000)

        if not registros:
            logging.warning("[empenhos_especiais_ingest_dag] Nenhum empenho encontrado.")
            return {ENTIDADE: 0}

        write_raw(SISTEMA, ENTIDADE, registros, primary_key=PRIMARY_KEY)
        logging.info("[empenhos_especiais_ingest_dag] %s registro(s).", len(registros))
        return {ENTIDADE: len(registros)}

    fetch_and_store()


empenhos_especiais_ingest_dag()
