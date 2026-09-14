import logging
from datetime import datetime, timedelta

from airflow.models import Variable
from airflow.sdk import dag, task

from cliente_ted import ClienteTed
from landing_zone import write_raw

SISTEMA = "transferegov_ted"
ENTIDADE = "programas"

default_args = {
    "owner": "mir",
    "queue": "mir",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="programas_mir_ingest_dag",
    schedule="@daily",
    start_date=datetime(2023, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere programas de TED filtrados pela sigla da unidade "
        "descentralizadora do MIR (Variable airflow_orgao_ted) para "
        "transferegov_ted.raw_programas."
    ),
    tags=["sistema:transferegov_ted", "dominio:transferencias", "orgao:mir"],
)
def programas_mir_dag() -> None:
    @task
    def fetch_and_store() -> dict:
        sigla_alvo = Variable.get("airflow_orgao_ted", default_var="MIR")

        api = ClienteTed()
        programas = api.get_programas_by_sigla_unidade_descentralizadora(sigla_alvo) or []
        write_raw(SISTEMA, ENTIDADE, programas, primary_key=["id_programa"])

        logging.info(
            "[programas_mir_ingest_dag] sigla=%s total=%s", sigla_alvo, len(programas)
        )
        return {ENTIDADE: len(programas)}

    fetch_and_store()


programas_mir_dag()
