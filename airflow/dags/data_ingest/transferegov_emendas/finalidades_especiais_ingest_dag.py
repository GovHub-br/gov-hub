import logging
from datetime import datetime, timedelta

from airflow.sdk import dag, task

from cliente_transferegov_emendas import ClienteTransfereGov
from landing_zone import write_raw

SISTEMA = "transferegov_emendas"
ENTIDADE = "finalidades_especiais"
PRIMARY_KEY = [
    "id_executor",
    "cd_area_politica_publica_tipo_pt",
    "area_politica_publica_pt",
]

default_args = {
    "owner": "transferegov_emendas",
    "queue": "transferegov_emendas",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="finalidades_especiais_ingest_dag",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere as finalidades (áreas de política pública) por executor de "
        "transferências especiais da API do TransfereGov para "
        "transferegov_emendas.raw_finalidades_especiais. Fonte 100% nacional, "
        "sem filtro de órgão."
    ),
    tags=["sistema:transferegov_emendas", "dominio:emendas_parlamentares"],
)
def finalidades_especiais_ingest_dag() -> None:
    @task
    def fetch_and_store() -> dict:
        api = ClienteTransfereGov()
        registros = api.get_all_finalidades_especiais(page_size=1000)

        if not registros:
            logging.warning(
                "[finalidades_especiais_ingest_dag] Nenhuma finalidade encontrada."
            )
            return {ENTIDADE: 0}

        write_raw(SISTEMA, ENTIDADE, registros, primary_key=PRIMARY_KEY)
        logging.info("[finalidades_especiais_ingest_dag] %s registro(s).", len(registros))
        return {ENTIDADE: len(registros)}

    fetch_and_store()


finalidades_especiais_ingest_dag()
