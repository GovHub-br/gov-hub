import logging
from datetime import datetime, timedelta
from typing import Any

from airflow.sdk import dag, task

from batching import block_offsets
from cliente_compras_gov import ClienteComprasGov
from landing_zone import distinct_raw_rows, write_raw

SISTEMA = "compras_gov"

# Combinações da raw de itens de ARP sobre as quais esta DAG pagina.
COLUNAS_ATA = ["numeroataregistropreco", "codigounidadegerenciadora"]
COLUNAS_ITEM = COLUNAS_ATA + ["numeroitem"]
BLOCK_SIZE = 150

default_args = {
    "owner": "mgi",
    "queue": "mgi",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="arp_detalhes_ingest_dag",
    schedule="0 7 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere detalhes de unidades, adesões e empenhos das ARPs já ingeridas, a partir da API do Compras.gov.br, "
        "para compras_gov.raw_arp_unidades_item, raw_arp_adesoes_item e raw_arp_empenhos_saldo."
    ),
    tags=["sistema:compras_gov", "dominio:arp"],
)
def arp_detalhes_dag() -> None:
    @task
    def get_item_offsets() -> list[int]:
        total = len(distinct_raw_rows(SISTEMA, "arp_item", COLUNAS_ITEM))
        offsets = block_offsets(total, BLOCK_SIZE)
        logging.info("ARP detalhes itens: %s itens em %s blocos", total, len(offsets))
        return offsets

    @task
    def get_par_offsets() -> list[int]:
        total = len(distinct_raw_rows(SISTEMA, "arp_item", COLUNAS_ATA))
        offsets = block_offsets(total, BLOCK_SIZE)
        logging.info("ARP detalhes empenhos: %s atas em %s blocos", total, len(offsets))
        return offsets

    @task(max_active_tis_per_dag=4)
    def fetch_unidades_adesoes(offset: int) -> dict:
        rows = distinct_raw_rows(SISTEMA, "arp_item", COLUNAS_ITEM)[
            offset : offset + BLOCK_SIZE
        ]
        api = ClienteComprasGov()
        total_unidades = 0
        total_adesoes = 0
        for ata, ug, item in rows:
            ctx = {
                "numeroataregistropreco": str(ata),
                "codigounidadegerenciadora": str(ug),
                "numeroitem": str(item),
            }
            unidades, _ = api.consultar_arp_unidades_item(str(ata), str(ug), str(item))
            if unidades:
                write_raw(SISTEMA, "arp_unidades_item", [{**ctx, **r} for r in unidades])
            adesoes, _ = api.consultar_arp_adesoes_item(str(ata), str(ug), str(item))
            if adesoes:
                write_raw(SISTEMA, "arp_adesoes_item", [{**ctx, **r} for r in adesoes])
            total_unidades += len(unidades)
            total_adesoes += len(adesoes)
        return {"unidades": total_unidades, "adesoes": total_adesoes}

    @task(max_active_tis_per_dag=4)
    def fetch_empenhos(offset: int) -> dict:
        rows = distinct_raw_rows(SISTEMA, "arp_item", COLUNAS_ATA)[
            offset : offset + BLOCK_SIZE
        ]
        api = ClienteComprasGov()
        total_empenhos = 0
        for ata, ug in rows:
            ctx = {
                "numeroataregistropreco": str(ata),
                "codigounidadegerenciadora": str(ug),
            }
            empenhos, _ = api.consultar_arp_empenhos_saldo(str(ata), str(ug))
            if empenhos:
                write_raw(SISTEMA, "arp_empenhos_saldo", [{**ctx, **r} for r in empenhos])
            total_empenhos += len(empenhos)
        return {"empenhos": total_empenhos}

    @task
    def validate_itens(results: Any) -> None:
        total_unidades = sum(r["unidades"] for r in results)
        total_adesoes = sum(r["adesoes"] for r in results)
        logging.info(
            "ARP detalhes itens: unidades=%s adesoes=%s", total_unidades, total_adesoes
        )

    @task
    def validate_empenhos(results: Any) -> None:
        total = sum(r["empenhos"] for r in results)
        logging.info("ARP detalhes empenhos: total=%s", total)

    item_offsets = get_item_offsets()
    par_offsets = get_par_offsets()
    validate_itens(fetch_unidades_adesoes.expand(offset=item_offsets))
    validate_empenhos(fetch_empenhos.expand(offset=par_offsets))


arp_detalhes_dag()
