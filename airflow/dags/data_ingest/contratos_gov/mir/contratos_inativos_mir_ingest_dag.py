import json
import logging
from datetime import datetime, timedelta

from airflow.models import Variable
from airflow.sdk import dag, task

from cliente_contratos import ClienteContratos
from landing_zone import write_raw

SISTEMA = "contratos_gov"
ENTIDADE = "contratos"

default_args = {
    "owner": "mir",
    "queue": "mir",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="contratos_inativos_mir_ingest_dag",
    schedule="@daily",
    start_date=datetime(2023, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere contratos inativos por UG do MIR da API contratos.comprasnet.gov.br "
        "para contratos_gov.raw_contratos (mesma tabela de contratos_mir_ingest_dag)."
    ),
    tags=["sistema:contratos_gov", "dominio:contratacoes", "orgao:mir"],
)
def contratos_inativos_mir_dag() -> None:
    @task
    def fetch_and_store() -> dict:
        codigos_ug = (
            json.loads(Variable.get("airflow_variables", default_var="{}"))
            .get("mir", {})
            .get("codigos_ug", [])
        )
        if not codigos_ug:
            logging.warning(
                "[contratos_inativos_mir_ingest_dag] Sem codigos_ug configurados para mir."
            )
            return {"contratos": 0}

        api = ClienteContratos()
        total = 0
        for ug_code in codigos_ug:
            contratos = api.get_contratos_inativos_by_ug(ug_code) or []
            write_raw(SISTEMA, ENTIDADE, contratos, primary_key=["id"])
            total += len(contratos)
            logging.info(
                "[contratos_inativos_mir_ingest_dag] UG %s: %s contratos inativos",
                ug_code,
                len(contratos),
            )

        return {"contratos": total}

    fetch_and_store()


contratos_inativos_mir_dag()
