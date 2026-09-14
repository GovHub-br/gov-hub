import logging
from datetime import datetime, timedelta

from airflow.sdk import dag, task

from cliente_transferegov_emendas import ClienteTransfereGov
from landing_zone import write_raw

SISTEMA = "transferegov_emendas"
ENTIDADE = "executor_especial"
PRIMARY_KEY = ["id_plano_acao", "id_executor"]

default_args = {
    "owner": "transferegov_emendas",
    "queue": "transferegov_emendas",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="executor_especial_ingest_dag",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere os executores dos planos de ação de transferências especiais "
        "da API do TransfereGov para transferegov_emendas.raw_executor_especial. "
        "Fonte 100% nacional, sem filtro de órgão."
    ),
    tags=["sistema:transferegov_emendas", "dominio:emendas_parlamentares"],
)
def executor_especial_ingest_dag() -> None:
    @task
    def fetch_and_store() -> dict:
        api = ClienteTransfereGov()
        registros = api.get_all_executores_especiais(page_size=1000)

        if not registros:
            logging.warning("[executor_especial_ingest_dag] Nenhum executor encontrado.")
            return {ENTIDADE: 0}

        # A API não garante ausência de repetição de (id_plano_acao, id_executor)
        # entre páginas; deduplica em memória para não estourar o ON CONFLICT
        # com duas linhas de mesma chave no mesmo lote.
        vistos: set[tuple] = set()
        deduplicados = []
        for item in registros:
            chave = tuple(item.get(campo) for campo in PRIMARY_KEY)
            if chave in vistos:
                continue
            vistos.add(chave)
            deduplicados.append(item)

        write_raw(SISTEMA, ENTIDADE, deduplicados, primary_key=PRIMARY_KEY)
        logging.info("[executor_especial_ingest_dag] %s registro(s).", len(deduplicados))
        return {ENTIDADE: len(deduplicados)}

    fetch_and_store()


executor_especial_ingest_dag()
