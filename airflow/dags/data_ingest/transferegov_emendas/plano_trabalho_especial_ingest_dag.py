import logging
from datetime import datetime, timedelta

from airflow.sdk import dag, task

from cliente_transferegov_emendas import ClienteTransfereGov
from landing_zone import write_raw

SISTEMA = "transferegov_emendas"
ENTIDADE = "plano_trabalho_especial"
PRIMARY_KEY = ["id_plano_trabalho"]

default_args = {
    "owner": "transferegov_emendas",
    "queue": "transferegov_emendas",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="plano_trabalho_especial_ingest_dag",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere os planos de trabalho de transferências especiais da API do "
        "TransfereGov para transferegov_emendas.raw_plano_trabalho_especial. "
        "Fonte 100% nacional, sem filtro de órgão."
    ),
    tags=["sistema:transferegov_emendas", "dominio:emendas_parlamentares"],
)
def plano_trabalho_especial_ingest_dag() -> None:
    @task
    def fetch_and_store() -> dict:
        api = ClienteTransfereGov()
        registros = api.get_all_plano_trabalho_especial(page_size=1000)

        if not registros:
            logging.warning(
                "[plano_trabalho_especial_ingest_dag] Nenhum plano de trabalho "
                "encontrado."
            )
            return {ENTIDADE: 0}

        write_raw(SISTEMA, ENTIDADE, registros, primary_key=PRIMARY_KEY)
        logging.info(
            "[plano_trabalho_especial_ingest_dag] %s registro(s).", len(registros)
        )
        return {ENTIDADE: len(registros)}

    fetch_and_store()


plano_trabalho_especial_ingest_dag()
