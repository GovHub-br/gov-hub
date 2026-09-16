import logging
from datetime import datetime, timedelta

from airflow.sdk import dag, task

from cliente_senado_federal import ClienteSenadoFederal
from landing_zone import write_raw

SISTEMA = "senado_federal"
ENTIDADE = "senadores_filiacoes"
PRIMARY_KEY = ["id", "sigla_partido", "dt_filiacao"]

default_args = {
    "owner": "senado_federal",
    "queue": "senado_federal",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="senadores_filiacoes_ingest_dag",
    schedule="@weekly",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere o histórico simplificado de filiações partidárias de cada "
        "senador, da API do Senado Federal, para "
        "senado_federal.raw_senadores_filiacoes."
    ),
    tags=["sistema:senado_federal", "dominio:parlamentares"],
)
def senadores_filiacoes_ingest_dag() -> None:
    @task
    def fetch_and_store_filiacoes() -> dict:
        api = ClienteSenadoFederal()
        senadores_base = api.get_senadores_por_legislatura()

        registros = []
        for sen in senadores_base or []:
            info = sen.get("IdentificacaoParlamentar", {})
            cod_id = info.get("CodigoParlamentar")
            nome = info.get("NomeParlamentar")
            if not cod_id:
                continue

            filiacoes = api.get_filiacoes_senador(cod_id)
            if not filiacoes:
                logging.debug(
                    "[senadores_filiacoes_ingest_dag] Nenhuma filiação para %s (ID: %s)",
                    nome,
                    cod_id,
                )
                continue

            for filiacao in filiacoes:
                partido = filiacao.get("Partido", {})
                registros.append(
                    {
                        "id": cod_id,
                        "nome_parlamentar": nome,
                        "sigla_partido": partido.get("SiglaPartido")
                        or "Sigla não disponível",
                        "nome_partido": partido.get("NomePartido")
                        or "Nome não disponível",
                        "dt_filiacao": filiacao.get("AnoFiliacao")
                        or "Data não disponível",
                        "dt_desfiliacao": filiacao.get("AnoDesfiliacao"),
                        "uf": info.get("UfParlamentar"),
                    }
                )

        # Deduplica em memória para não estourar o ON CONFLICT com duas
        # linhas de mesma chave no mesmo lote (portado de
        # data-application-mir).
        deduplicados: dict[tuple, dict] = {}
        for registro in registros:
            chave = tuple(registro.get(campo) for campo in PRIMARY_KEY)
            deduplicados.setdefault(chave, registro)
        registros = list(deduplicados.values())

        if not registros:
            logging.warning(
                "[senadores_filiacoes_ingest_dag] Nenhuma filiação encontrada."
            )
            return {ENTIDADE: 0}

        write_raw(SISTEMA, ENTIDADE, registros, primary_key=PRIMARY_KEY)
        logging.info(
            "[senadores_filiacoes_ingest_dag] %s registro(s) ingerido(s).", len(registros)
        )
        return {ENTIDADE: len(registros)}

    fetch_and_store_filiacoes()


senadores_filiacoes_ingest_dag()
