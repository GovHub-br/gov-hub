from datetime import datetime, timedelta
import logging
import time

from airflow.sdk import dag, task, Param, get_current_context
from batching import chunked
from cliente_compras_gov import ClienteComprasGov
from landing_zone import distinct_raw_values, write_raw

SISTEMA = "compras_gov"
BLOCK_SIZE = 50

default_args = {
    "owner": "mgi",
    "queue": "mgi",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="pgc_detalhe_catalogo_ingest_dag",
    schedule="0 3 * * 0",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "DAG para ingestão de dados do PGC Detalhe Catálogo do "
        "Compras.gov.br para a zona raw."
    ),
    tags=["sistema:compras_gov", "orgao:mgi", "camada:raw", "dominio:pgc"],
    params={
        "modo": Param(
            "incremental",
            enum=["incremental", "fria"],
            description="Modo de execução da DAG: incremental ou full",
        ),
        "ano_inicio": Param(
            2023,
            type="integer",
            description="Ano inicial para consulta do PGC Detalhe Catalogo (2023)",
        ),
    },
)
def pgc_detalhe_catalogo_dag() -> None:
    @task
    def get_codigos_itens() -> list[list[dict]]:
        try:
            codigo_material = distinct_raw_values(
                SISTEMA,
                "item_material",
                "codigoClasse",
            )
            codigo_servico = distinct_raw_values(
                SISTEMA,
                "item_servico",
                "codigoGrupo",
            )
        except Exception as exc:
            raise RuntimeError(
                "As entidades 'item_material' e 'item_servico' precisam estar "
                "na zona raw antes da execução desta DAG."
            ) from exc

        itens = [{"codigo": codigo, "tipo": "Material"} for codigo in codigo_material]
        itens += [{"codigo": codigo, "tipo": "Servico"} for codigo in codigo_servico]

        blocos = chunked(itens, BLOCK_SIZE)

        logging.info("PGC Detalhe Catálogo: %s itens para processar", len(itens))
        return blocos

    @task(max_active_tis_per_dag=1)
    def fetch_pgc_detalhe_catalogo(bloco: list[dict]) -> dict:
        context = get_current_context()
        current_date = datetime.now()
        ano_atual = current_date.year
        modo = context["params"]["modo"]

        if modo == "fria":
            ano_inicio = context["params"]["ano_inicio"]
            ano_fim = ano_atual
            anos = list(range(ano_inicio, ano_fim + 1))
            logging.info("Modo de execução: fria. Anos a processar: %s", anos)
        else:
            anos = [ano_atual]
            logging.info("Modo de execução: incremental. Ano a processar: %s", anos)

        api = ClienteComprasGov()
        total_registros = 0

        for item in bloco:
            codigo_item = item["codigo"]
            tipo = item["tipo"]

            for ano in anos:
                try:
                    time.sleep(3)
                    pgc, _ = api.fetch_all_pages(
                        "/modulo-pgc/2_consultarPgcDetalheCatalogo",
                        {"anoPcaProjetoCompra": ano, "tipo": tipo, "codigo": codigo_item},
                    )
                    if not pgc:
                        logging.info(
                            "Sem registros: ano=%s, tipo=%s, codigo=%s",
                            ano,
                            tipo,
                            codigo_item,
                        )
                        continue
                    write_raw(
                        SISTEMA,
                        "pgc_detalhe_catalogo",
                        pgc,
                        run_id=(
                            f"{context['run_id']}-tipo-{tipo}-codigo-{codigo_item}-ano-{ano}"
                        ),
                    )
                    total_registros += len(pgc)
                    logging.info(
                        "PGC Detalhe Catalogo: ano=%s, tipo=%s, codigo=%s, registros=%s",
                        ano,
                        tipo,
                        codigo_item,
                        len(pgc),
                    )
                except Exception:
                    logging.exception(
                        "Erro ao buscar PGC Detalhe Catalogo para ano=%s, tipo=%s, codigo=%s",
                        ano,
                        tipo,
                        codigo_item,
                    )
        return {
            "itens_processados": len(bloco),
            "registros": total_registros,
        }

    @task
    def validate_resultados(resultados_itens: list[dict]) -> None:
        total_itens = sum(r["itens_processados"] for r in resultados_itens)
        total_registros = sum(r["registros"] for r in resultados_itens)
        logging.info("Validação: %s itens, %s registros", total_itens, total_registros)

    blocos = get_codigos_itens()
    resultados = fetch_pgc_detalhe_catalogo.expand(bloco=blocos)

    # O Airflow resolve o XComArg para os resultados antes de executar a task.
    validate_resultados(resultados)  # ty: ignore[invalid-argument-type]


pgc_detalhe_catalogo_dag()
