import logging
import time
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
    tags=["sistema:compras_gov", "dominio:pesquisa_preco", "orgao:mgi"],
)
def pesquisa_preco_servico_dag() -> None:
    @task
    def get_blocos_servico() -> list[list[str]]:
        itens = distinct_raw_values(SISTEMA, "item_servico", "codigoServico")
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
            time.sleep(3)
            registros_preco = 0
            api_total_preco = None
            for batch, api_total_preco in api.iter_pages(
                "/modulo-pesquisa-preco/3_consultarServico",
                {"codigoItemCatalogo": codigo_item},
            ):
                write_raw(
                    SISTEMA,
                    "pesquisa_preco_servico",
                    batch,
                )
                registros_preco += len(batch)
            if api_total_preco is None:
                raise RuntimeError(
                    f"A API não retornou resposta válida (preço): item={codigo_item}."
                )
            if registros_preco != api_total_preco:
                raise RuntimeError(
                    f"Resposta incompleta (preço): item={codigo_item}, "
                    f"gravados={registros_preco}, api_total={api_total_preco}."
                )
            total_preco += registros_preco

            time.sleep(3)
            registros_detalhe = 0
            api_total_detalhe = None
            for batch, api_total_detalhe in api.iter_pages(
                "/modulo-pesquisa-preco/4_consultarServicoDetalhe",
                {"codigoItemCatalogo": codigo_item},
            ):
                write_raw(
                    SISTEMA,
                    "pesquisa_preco_servico_detalhe",
                    batch,
                )
                registros_detalhe += len(batch)
            if api_total_detalhe is None:
                raise RuntimeError(
                    f"A API não retornou resposta válida (detalhe): item={codigo_item}."
                )
            if registros_detalhe != api_total_detalhe:
                raise RuntimeError(
                    f"Resposta incompleta (detalhe): item={codigo_item}, "
                    f"gravados={registros_detalhe}, api_total={api_total_detalhe}."
                )
            total_detalhe += registros_detalhe

            logging.info(
                "Item %s: preco=%s detalhe=%s",
                codigo_item,
                registros_preco,
                registros_detalhe,
            )
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
