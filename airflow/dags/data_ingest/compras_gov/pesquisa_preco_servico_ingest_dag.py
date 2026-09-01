import logging
from datetime import datetime, timedelta
from typing import Any
from airflow.sdk import dag, task
from batching import chunked
from cliente_compras_gov import ClienteComprasGov
from landing_zone import distinct_raw_values, write_raw

SISTEMA = "compras_gov"
BLOCK_SIZE = 100
default_args = {
    "owner": "mgi",
    "queue": "mgi",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="pesquisa_preco_servico_ingest_dag",
    schedule="0 3 * * 0",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Consulta preços e detalhes de serviços já catalogados na API de pesquisa de preço do Compras.gov.br, gravando "
        "em compras_gov.raw_pesquisa_preco_servico e raw_pesquisa_preco_servico_detalhe."
    ),
    tags=["sistema:compras_gov", "dominio:pesquisa_preco"],
)
def pesquisa_preco_servico_dag() -> None:
    @task
    def get_blocos_servico() -> list[list[str]]:
        itens = distinct_raw_values(SISTEMA, "item_servico", "codigoservico")
        blocos = chunked(itens, BLOCK_SIZE)
        logging.info(
            "Pesquisa de preços serviço: %s itens em %s blocos de até %s",
            len(itens),
            len(blocos),
            BLOCK_SIZE,
        )
        return blocos

    @task(max_active_tis_per_dag=4)
    def fetch_preco_servico(lote: list[str]) -> dict:
        api = ClienteComprasGov()
        total_preco = 0
        total_detalhe = 0
        for codigo_item in lote:
            preco, _ = api.fetch_all_pages(
                "/modulo-pesquisa-preco/3_consultarServico",
                {"codigoItemCatalogo": codigo_item},
            )
            if preco:
                write_raw(SISTEMA, "pesquisa_preco_servico", preco)
            detalhe, _ = api.fetch_all_pages(
                "/modulo-pesquisa-preco/4_consultarServicoDetalhe",
                {"codigoItemCatalogo": codigo_item},
            )
            if detalhe:
                write_raw(SISTEMA, "pesquisa_preco_servico_detalhe", detalhe)
            total_preco += len(preco)
            total_detalhe += len(detalhe)
        return {"preco": total_preco, "detalhe": total_detalhe}

    @task
    def validate(results: Any) -> None:
        total_preco = sum(r["preco"] for r in results)
        total_detalhe = sum(r["detalhe"] for r in results)
        logging.info(
            "Pesquisa preço serviço: blocos=%s preco=%s detalhe=%s",
            len(results),
            total_preco,
            total_detalhe,
        )

    blocos = get_blocos_servico()
    results = fetch_preco_servico.expand(lote=blocos)
    validate(results)


pesquisa_preco_servico_dag()
