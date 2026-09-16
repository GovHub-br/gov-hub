import logging
from datetime import datetime, timedelta

from airflow.sdk import dag, task

from cliente_senado_federal import ClienteSenadoFederal
from landing_zone import write_raw

SISTEMA = "senado_federal"
ENTIDADE = "legislaturas"
PRIMARY_KEY = ["id"]

default_args = {
    "owner": "senado_federal",
    "queue": "senado_federal",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="legislaturas_ingest_dag",
    schedule="@weekly",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere as legislaturas do Congresso Nacional (período de vigência "
        "e data de eleição) da API do Senado Federal para "
        "senado_federal.raw_legislaturas."
    ),
    tags=["sistema:senado_federal", "dominio:parlamentares"],
)
def legislaturas_ingest_dag() -> None:
    @task
    def fetch_and_store_legislaturas() -> dict:
        api = ClienteSenadoFederal()
        legislaturas = api.get_periodo_legislacao()

        if not legislaturas:
            logging.warning("[legislaturas_ingest_dag] Nenhuma legislatura encontrada.")
            return {ENTIDADE: 0}

        registros = [
            {
                "id": int(leg["NumeroLegislatura"]),
                "data_inicio": leg.get("DataInicio"),
                "data_fim": leg.get("DataFim"),
                "data_eleicao": leg.get("DataEleicao"),
            }
            for leg in legislaturas
            if leg.get("NumeroLegislatura") is not None
        ]

        write_raw(SISTEMA, ENTIDADE, registros, primary_key=PRIMARY_KEY)
        logging.info(
            "[legislaturas_ingest_dag] %s legislatura(s) ingerida(s).", len(registros)
        )
        return {ENTIDADE: len(registros)}

    fetch_and_store_legislaturas()


legislaturas_ingest_dag()
