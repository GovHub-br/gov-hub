import logging
from datetime import datetime, timedelta

from airflow.sdk import dag, task

from cliente_contratos import ClienteContratos
from landing_zone import distinct_raw_values, write_raw

SISTEMA = "contratos_gov"
ENTIDADE = "empenhos"

default_args = {
    "owner": "mir",
    "queue": "mir",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="empenhos_mir_ingest_dag",
    schedule="@daily",
    start_date=datetime(2023, 1, 1),
    catchup=False,
    default_args=default_args,
    description="Ingere os empenhos de cada contrato do MIR já ingerido em contratos_gov.raw_contratos.",
    tags=["sistema:contratos_gov", "dominio:contratacoes", "orgao:mir"],
)
def empenhos_mir_dag() -> None:
    @task
    def fetch_and_store() -> dict:
        try:
            contrato_ids = distinct_raw_values(SISTEMA, "contratos", "id")
        except Exception as exc:
            raise RuntimeError(
                "Entidade 'contratos' ainda não está na zona raw. "
                "Execute contratos_mir_ingest_dag antes de empenhos_mir_ingest_dag."
            ) from exc

        api = ClienteContratos()
        total = 0
        for contrato_id in contrato_ids:
            try:
                itens = api.get_empenhos_by_contrato_id(str(contrato_id)) or []
            except Exception as exc:
                logging.error(
                    "[empenhos_mir_ingest_dag] Erro no contrato %s: %s", contrato_id, exc
                )
                continue

            for item in itens:
                item["contrato_id"] = contrato_id
            write_raw(SISTEMA, ENTIDADE, itens, primary_key=["id", "contrato_id"])
            total += len(itens)

        logging.info("[empenhos_mir_ingest_dag] total=%s", total)
        return {ENTIDADE: total}

    fetch_and_store()


empenhos_mir_dag()
