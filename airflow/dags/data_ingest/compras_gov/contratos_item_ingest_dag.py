import logging
from datetime import datetime, timedelta
from typing import Any

from airflow.sdk import dag, task

from batching import chunked, limit_local
from cliente_compras_gov import ClienteComprasGov
from landing_zone import distinct_raw_values, write_raw

SISTEMA = "compras_gov"
BLOCK_SIZE = 50

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
    dag_id="contratos_item_ingest_dag",
    schedule="0 5 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    description="Ingere itens de contratos por órgão da API do Compras.gov.br para compras_gov.raw_contratos_item.",
    tags=["sistema:compras_gov", "dominio:contratos"],
)
def contratos_item_dag() -> None:
    @task
    def get_orgao_blocks() -> list[list[str]]:
        try:
            orgaos = distinct_raw_values(SISTEMA, "orgao", "codigoorgao")
        except Exception as exc:
            raise RuntimeError(
                "Entidade 'orgao' ainda não está na zona raw. "
                "Execute orgao_ingest_dag antes de contratos_item_ingest_dag."
            ) from exc
        orgaos = limit_local(orgaos, "INGEST_MAX_ORGAOS", "órgãos")
        blocks = chunked(orgaos, BLOCK_SIZE)
        logging.info(
            "Total de órgãos a processar: %s em %s blocos de até %s",
            len(orgaos),
            len(blocks),
            BLOCK_SIZE,
        )
        return blocks

    @task(max_active_tis_per_dag=4)
    def ingest_orgaos(codigos_orgao: list[str], **context: dict) -> dict:
        data_inicial, data_final = _get_intervalo(context)
        api = ClienteComprasGov()
        itens = 0

        for codigo_orgao in codigos_orgao:
            itens_orgao = 0
            for batch, _ in api.iter_pages(
                "/modulo-contratos/2_consultarContratosItem",
                {
                    "codigoOrgao": codigo_orgao,
                    "dataVigenciaInicialMin": data_inicial,
                    "dataVigenciaInicialMax": data_final,
                },
            ):
                write_raw(
                    SISTEMA,
                    "contratos_item",
                    batch,
                    primary_key=[
                        "codigounidadegestora",
                        "numerocontrato",
                        "nifornecedor",
                        "numeroitem",
                        "contratoitemexcluido",
                    ],
                )
                itens_orgao += len(batch)

            logging.info(
                "Órgão %s %s→%s: itens=%s",
                codigo_orgao,
                data_inicial,
                data_final,
                itens_orgao,
            )
            itens += itens_orgao

        return {"itens": itens}

    @task
    def validate(results: Any) -> None:
        total_itens = sum(r["itens"] for r in results)
        logging.info(
            "Contratos item total: itens=%s blocos=%s", total_itens, len(results)
        )

    blocks = get_orgao_blocks()
    results = ingest_orgaos.expand(codigos_orgao=blocks)
    validate(results)


contratos_item_dag()
