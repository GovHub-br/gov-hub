import logging
from datetime import datetime, timedelta
from typing import Any

from airflow.sdk import dag, task

from cliente_compras_gov import ClienteComprasGov
from landing_zone import distinct_raw_values, write_raw

SISTEMA = "compras_gov"
PAGE_SIZE = 500

default_args = {
    "owner": "mgi",
    "queue": "mgi",
    "retries": 3,
    "retry_delay": timedelta(minutes=10),
}


def _get_intervalo(context: dict) -> tuple[str, str]:
    data_inicial = str(context["data_interval_start"].date())
    data_final = str(context["data_interval_end"].date())
    return data_inicial, data_final


@dag(
    dag_id="contratos_ingest_dag",
    schedule="0 5 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    description="Ingere contratos por órgão da API do Compras.gov.br para compras_gov.raw_contratos.",
    tags=["sistema:compras_gov", "dominio:contratos"],
)
def contratos_dag() -> None:
    @task
    def get_orgaos() -> list[str]:
        try:
            orgaos = distinct_raw_values(SISTEMA, "orgao", "codigoorgao")
        except Exception as exc:
            raise RuntimeError(
                "Entidade 'orgao' ainda não está na zona raw. "
                "Execute orgao_ingest_dag antes de contratos_ingest_dag."
            ) from exc
        logging.info("Total de órgãos a processar: %s", len(orgaos))
        return orgaos

    @task(max_active_tis_per_dag=4)
    def ingest_orgao(codigo_orgao: str, **context: dict) -> dict:
        data_inicial, data_final = _get_intervalo(context)
        api = ClienteComprasGov()
        contratos = 0

        for batch, _ in api.iter_pages(
            "/modulo-contratos/1_consultarContratos",
            {
                "codigoOrgao": codigo_orgao,
                "dataVigenciaInicialMin": data_inicial,
                "dataVigenciaInicialMax": data_final,
            },
        ):
            write_raw(
                SISTEMA,
                "contratos",
                batch,
                primary_key=["codigounidadegestora", "numerocontrato", "nifornecedor"],
            )
            contratos += len(batch)

        logging.info(
            "Órgão %s %s→%s: contratos=%s",
            codigo_orgao,
            data_inicial,
            data_final,
            contratos,
        )
        return {"contratos": contratos}

    @task
    def validate(results: Any) -> None:
        total_contratos = sum(r["contratos"] for r in results)
        logging.info(
            "Contratos total: contratos=%s orgaos=%s", total_contratos, len(results)
        )

    orgaos = get_orgaos()
    results = ingest_orgao.expand(codigo_orgao=orgaos)
    validate(results)


contratos_dag()
