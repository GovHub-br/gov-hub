import logging
from datetime import datetime, timedelta

from airflow.sdk import dag, task

from cliente_senado_federal import ClienteSenadoFederal
from landing_zone import write_raw

SISTEMA = "senado_federal"
ENTIDADE = "senadores"
PRIMARY_KEY = ["id"]

default_args = {
    "owner": "senado_federal",
    "queue": "senado_federal",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="senadores_ingest_dag",
    schedule="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere o cadastro de senadores (ativos e inativos) da API do "
        "Senado Federal para senado_federal.raw_senadores."
    ),
    tags=["sistema:senado_federal", "dominio:parlamentares"],
)
def senadores_ingest_dag() -> None:
    @task
    def fetch_and_store_senadores() -> dict:
        api = ClienteSenadoFederal()
        senadores = api.get_senadores_por_legislatura()

        registros = []
        for item in senadores or []:
            info = item.get("IdentificacaoParlamentar", {})
            mandato = item.get("Mandato", {})
            registros.append(
                {
                    "id": info.get("CodigoParlamentar"),
                    "nome_parlamentar": info.get("NomeParlamentar"),
                    "nome_completo": info.get("NomeCompletoParlamentar"),
                    "sexo": info.get("SexoParlamentar"),
                    "forma_tratamento": info.get("FormaTratamento"),
                    "url_foto": info.get("UrlFotoParlamentar"),
                    "url_pagina": info.get("UrlPaginaParlamentar"),
                    "email": info.get("EmailParlamentar"),
                    "sigla_partido": info.get("SiglaPartidoParlamentar"),
                    "uf": info.get("UfParlamentar"),
                    "id_legislatura": mandato.get("NumeroLegislatura"),
                }
            )

        if not registros:
            logging.warning("[senadores_ingest_dag] Nenhum senador encontrado.")
            return {ENTIDADE: 0}

        write_raw(SISTEMA, ENTIDADE, registros, primary_key=PRIMARY_KEY)
        logging.info("[senadores_ingest_dag] %s senador(es) ingerido(s).", len(registros))
        return {ENTIDADE: len(registros)}

    fetch_and_store_senadores()


senadores_ingest_dag()
