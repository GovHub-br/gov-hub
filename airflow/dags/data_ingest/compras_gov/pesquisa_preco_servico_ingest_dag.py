import logging
from datetime import datetime, timedelta
from typing import Any
from airflow.sdk import dag, task
from cliente_compras_gov import ClienteComprasGov
from landing_zone import distinct_raw_values, write_raw

SISTEMA = "compras_gov"
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
    def get_itens_servico() -> list[str]:
        itens = distinct_raw_values(SISTEMA, "item_servico", "codigoservico")
        logging.info("Pesquisa de preços serviço: %s itens a processar", len(itens))
        return itens

    @task(max_active_tis_per_dag=4)
    def fetch_preco_servico(codigo_item: str) -> dict:
        api = ClienteComprasGov()
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
        return {"preco": len(preco), "detalhe": len(detalhe)}

    @task
    def validate(results: Any) -> None:
        total_preco = sum(r["preco"] for r in results)
        total_detalhe = sum(r["detalhe"] for r in results)
        logging.info(
            "Pesquisa preço serviço: itens=%s preco=%s detalhe=%s",
            len(results),
            total_preco,
            total_detalhe,
        )

    itens = get_itens_servico()
    results = fetch_preco_servico.expand(codigo_item=itens)
    validate(results)


pesquisa_preco_servico_dag()
