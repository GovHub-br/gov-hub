import logging
from datetime import datetime, timedelta

from airflow.sdk import dag, task

from cliente_ted import ClienteTed
from landing_zone import distinct_raw_values, write_raw

SISTEMA = "transferegov_ted"
ENTIDADE = "planos_acao"

default_args = {
    "owner": "mir",
    "queue": "mir",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="planos_acao_mir_ingest_dag",
    schedule="@daily",
    start_date=datetime(2023, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere os planos de ação de cada programa de TED do MIR já ingerido "
        "em transferegov_ted.raw_programas."
    ),
    tags=["sistema:transferegov_ted", "dominio:transferencias", "orgao:mir"],
)
def planos_acao_mir_dag() -> None:
    @task
    def fetch_and_store() -> dict:
        try:
            programa_ids = distinct_raw_values(SISTEMA, "programas", "id_programa")
        except Exception as exc:
            raise RuntimeError(
                "Entidade 'programas' ainda não está na zona raw. Execute "
                "programas_mir_ingest_dag antes de planos_acao_mir_ingest_dag."
            ) from exc

        api = ClienteTed()
        total = 0
        for id_programa in programa_ids:
            try:
                planos = api.get_planos_acao_by_id_programa(str(id_programa)) or []
            except Exception as exc:
                logging.error(
                    "[planos_acao_mir_ingest_dag] Erro no programa %s: %s",
                    id_programa,
                    exc,
                )
                continue

            if not planos:
                continue
            write_raw(SISTEMA, ENTIDADE, planos, primary_key=["id_plano_acao"])
            total += len(planos)

        logging.info("[planos_acao_mir_ingest_dag] total=%s", total)
        return {ENTIDADE: total}

    fetch_and_store()


planos_acao_mir_dag()
