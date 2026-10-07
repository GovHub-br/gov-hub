import logging
import time
from datetime import datetime, timedelta
from typing import Any
from airflow.sdk import dag, task
from batching import chunked
from cliente_compras_gov import ClienteComprasGov
from landing_zone import distinct_raw_values, write_raw

SISTEMA = "compras_gov"
BLOCK_SIZE = 500
default_args = {
    "owner": "mgi",
    "queue": "mgi",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="pesquisa_preco_material_ingest_dag",
    schedule="0 3 * * 0",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Consulta preços e detalhes de materiais já catalogados na API de pesquisa de preço do Compras.gov.br, "
        "gravando em compras_gov.raw_pesquisa_preco_material e raw_pesquisa_preco_material_detalhe."
    ),
    tags=["sistema:compras_gov", "dominio:pesquisa_preco", "orgao:mgi"],
)
def pesquisa_preco_material_dag() -> None:
    @task
    def get_itens_material() -> list[str]:
        itens = distinct_raw_values(SISTEMA, "item_material", "codigoItem")
        logging.info("Pesquisa de preços material: %s itens a processar", len(itens))
        return itens

    @task
    def gerar_lotes(itens: Any) -> list[list[str]]:
        return chunked(itens, BLOCK_SIZE)

    @task(max_active_tis_per_dag=2)
    def fetch_preco_material(lote: list[str], **context: Any) -> dict:
        api = ClienteComprasGov()
        total_preco = 0
        total_detalhe = 0
        indice = context["ti"].map_index
        for codigo_item in lote:
            time.sleep(1)
            preco, _ = api.fetch_all_pages(
                "/modulo-pesquisa-preco/1_consultarMaterial",
                {"tipo": "codigoItemCatalogo", "codigo": codigo_item},
            )
            if preco:
                write_raw(
                    SISTEMA,
                    "pesquisa_preco_material",
                    preco,
                    run_id=f"{context['run_id']}-map-{indice}-item-{codigo_item}-preco",
                )
            total_preco += len(preco)
            time.sleep(1)
            detalhe, _ = api.fetch_all_pages(
                "/modulo-pesquisa-preco/2_consultarMaterialDetalhe",
                {"codigoItemCatalogo": codigo_item},
            )
            if detalhe:
                write_raw(
                    SISTEMA,
                    "pesquisa_preco_material_detalhe",
                    detalhe,
                    run_id=f"{context['run_id']}-map-{indice}-item-{codigo_item}-detalhe",
                )
            total_detalhe += len(detalhe)

        return {"itens": len(lote), "preco": total_preco, "detalhe": total_detalhe}

    @task
    def validate(results: Any) -> None:
        total_itens = sum(r["itens"] for r in results)
        total_preco = sum(r["preco"] for r in results)
        total_detalhe = sum(r["detalhe"] for r in results)
        logging.info(
            "Pesquisa preço material: itens=%s preco=%s detalhe=%s",
            total_itens,
            total_preco,
            total_detalhe,
        )

    itens = get_itens_material()
    lotes = gerar_lotes(itens)
    results = fetch_preco_material.expand(lote=lotes)
    validate(results)


pesquisa_preco_material_dag()
