import logging
from datetime import datetime, timedelta

from airflow.sdk import dag, task

from cliente_ted import ClienteTed
from landing_zone import distinct_raw_values, write_raw

SISTEMA = "transferegov_ted"
ENTIDADE = "notas_de_credito"

default_args = {
    "owner": "mir",
    "queue": "mir",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="notas_de_credito_mir_ingest_dag",
    schedule="@daily",
    start_date=datetime(2023, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere as notas de crédito de cada plano de ação de TED do MIR já "
        "ingerido em transferegov_ted.raw_planos_acao."
    ),
    tags=["sistema:transferegov_ted", "dominio:transferencias", "orgao:mir"],
)
def notas_de_credito_mir_dag() -> None:
    @task
    def fetch_and_store() -> dict:
        try:
            plano_acao_ids = distinct_raw_values(SISTEMA, "planos_acao", "id_plano_acao")
        except Exception as exc:
            raise RuntimeError(
                "Entidade 'planos_acao' ainda não está na zona raw. Execute "
                "planos_acao_mir_ingest_dag antes de "
                "notas_de_credito_mir_ingest_dag."
            ) from exc

        api = ClienteTed()
        total = 0
        for id_plano_acao in plano_acao_ids:
            try:
                notas = (
                    api.get_notas_de_credito_by_id_plano_acao(str(id_plano_acao)) or []
                )
            except Exception as exc:
                logging.error(
                    "[notas_de_credito_mir_ingest_dag] Erro no plano de ação " "%s: %s",
                    id_plano_acao,
                    exc,
                )
                continue

            if not notas:
                continue
            write_raw(SISTEMA, ENTIDADE, notas, primary_key=["id_nota"])
            total += len(notas)

        logging.info("[notas_de_credito_mir_ingest_dag] total=%s", total)
        return {ENTIDADE: total}

    fetch_and_store()


notas_de_credito_mir_dag()
