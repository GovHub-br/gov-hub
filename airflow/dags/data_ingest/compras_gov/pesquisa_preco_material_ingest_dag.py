import logging
from datetime import datetime, timedelta
from typing import Any
from airflow.sdk import dag, task
from cliente_compras_gov import ClienteComprasGov
from cliente_postgres import ClientPostgresDB
from postgres_helpers import get_postgres_conn

SCHEMA = "compras_gov"
default_args = {
    "owner": "mgi",
    "queue": "mgi",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}


def _stamp(records: list[dict]) -> list[dict]:
    ts = datetime.now().isoformat()
    for r in records:
        r["dt_ingest"] = ts
    return records


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
    tags=["sistema:compras_gov", "dominio:pesquisa_preco"],
)
def pesquisa_preco_material_dag() -> None:
    @task
    def get_itens_material() -> list[str]:
        db = ClientPostgresDB(get_postgres_conn())
        rows = db.execute_query(
            f"SELECT DISTINCT codigoitem FROM {SCHEMA}.raw_item_material ORDER BY codigoitem"
        )
        itens = [str(r[0]) for r in rows]
        logging.info("Pesquisa de preços material: %s itens a processar", len(itens))
        return itens

    @task
    def gerar_lotes(itens: Any, tamanho: int = 100) -> list[list[str]]:
        return [itens[i : i + tamanho] for i in range(0, len(itens), tamanho)]

    @task(max_active_tis_per_dag=4)
    def fetch_preco_material(lote: list[str]) -> dict:
        api = ClienteComprasGov()
        db = ClientPostgresDB(get_postgres_conn())
        for codigo_item in lote:
            preco, _ = api.fetch_all_pages(
                "/modulo-pesquisa-preco/1_consultarMaterial",
                {"tipo": "codigoItemCatalogo", "codigo": codigo_item},
            )
            if preco:
                db.insert_data(
                    _stamp(preco), "raw_pesquisa_preco_material", schema=SCHEMA
                )
            detalhe, _ = api.fetch_all_pages(
                "/modulo-pesquisa-preco/2_consultarMaterialDetalhe",
                {"codigoItemCatalogo": codigo_item},
            )
            if detalhe:
                db.insert_data(
                    _stamp(detalhe), "raw_pesquisa_preco_material_detalhe", schema=SCHEMA
                )
        return {"preco": len(preco), "detalhe": len(detalhe)}

    @task
    def validate(results: Any) -> None:
        total_preco = sum(r["preco"] for r in results)
        total_detalhe = sum(r["detalhe"] for r in results)
        logging.info(
            "Pesquisa preço material: itens=%s preco=%s detalhe=%s",
            len(results),
            total_preco,
            total_detalhe,
        )

    itens = get_itens_material()
    lotes = gerar_lotes(itens)
    results = fetch_preco_material.expand(lote=lotes)
    validate(results)


pesquisa_preco_material_dag()
