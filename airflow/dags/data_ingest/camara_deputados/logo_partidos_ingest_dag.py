import logging
import time
from datetime import datetime, timedelta

from airflow.sdk import dag, task

from cliente_camara_deputados import ClienteCamaraDeputados
from landing_zone import write_raw

SISTEMA = "camara_deputados"
ENTIDADE = "logo_partidos"
PRIMARY_KEY = ["id"]

default_args = {
    "owner": "camara_deputados",
    "queue": "camara_deputados",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="logo_partidos_ingest_dag",
    schedule="@weekly",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere o cadastro de partidos políticos e a URL do logo de cada um, "
        "da API da Câmara dos Deputados, para "
        "camara_deputados.raw_logo_partidos."
    ),
    tags=["sistema:camara_deputados", "dominio:parlamentares"],
)
def logo_partidos_ingest_dag() -> None:
    @task
    def fetch_and_store_partidos() -> dict:
        api = ClienteCamaraDeputados()
        partidos_basicos = api.get_all_partidos()

        registros = []
        for partido in partidos_basicos or []:
            partido_id = partido.get("id")
            if not partido_id:
                continue
            detalhe = api.get_partido_by_id(partido_id)
            time.sleep(0.5)
            if not detalhe:
                continue
            registros.append(
                {
                    "id": detalhe.get("id"),
                    "sigla": detalhe.get("sigla"),
                    "nome": detalhe.get("nome"),
                    "uri": detalhe.get("uri"),
                    "urlLogo": detalhe.get("urlLogo"),
                }
            )

        if not registros:
            logging.warning("[logo_partidos_ingest_dag] Nenhum partido encontrado.")
            return {ENTIDADE: 0}

        write_raw(SISTEMA, ENTIDADE, registros, primary_key=PRIMARY_KEY)
        logging.info(
            "[logo_partidos_ingest_dag] %s partido(s) ingerido(s).", len(registros)
        )
        return {ENTIDADE: len(registros)}

    fetch_and_store_partidos()


logo_partidos_ingest_dag()
