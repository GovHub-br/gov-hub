import logging
from datetime import datetime, timedelta

from airflow.sdk import dag, task

from cliente_transferegov_emendas import ClienteTransfereGov
from landing_zone import distinct_raw_values, write_raw

SISTEMA = "transferegov_emendas"
ENTIDADE = "planos_acao_especiais"
PRIMARY_KEY = ["id_plano_acao"]

default_args = {
    "owner": "transferegov_emendas",
    "queue": "transferegov_emendas",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="planos_acao_especiais_ingest_dag",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere os planos de ação de transferências especiais da API do "
        "TransfereGov para transferegov_emendas.raw_planos_acao_especiais. A "
        "API não expõe um endpoint 'todos os programas' para este recurso, "
        "então a DAG itera pelos id_programa já ingeridos em "
        "transferegov_emendas.raw_programas_especiais — depende de "
        "programas_especiais_ingest_dag ter rodado antes."
    ),
    tags=["sistema:transferegov_emendas", "dominio:emendas_parlamentares"],
)
def planos_acao_especiais_ingest_dag() -> None:
    @task
    def fetch_and_store() -> dict:
        api = ClienteTransfereGov()

        try:
            programas_ids = distinct_raw_values(
                SISTEMA, "programas_especiais", "id_programa"
            )
        except Exception as exc:
            logging.warning(
                "[planos_acao_especiais_ingest_dag] programas_especiais ainda não "
                "ingerido: %s",
                exc,
            )
            return {ENTIDADE: 0}

        if not programas_ids:
            logging.warning(
                "[planos_acao_especiais_ingest_dag] Nenhum programa encontrado."
            )
            return {ENTIDADE: 0}

        total = 0
        for id_programa in programas_ids:
            planos = api.get_all_planos_acao_especiais_by_programa(int(id_programa))
            if not planos:
                continue
            write_raw(SISTEMA, ENTIDADE, planos, primary_key=PRIMARY_KEY)
            total += len(planos)

        logging.info("[planos_acao_especiais_ingest_dag] total=%s", total)
        return {ENTIDADE: total}

    fetch_and_store()


planos_acao_especiais_ingest_dag()
