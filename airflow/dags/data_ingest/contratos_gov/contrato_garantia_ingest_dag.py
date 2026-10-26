"""Ingestão semanal das garantias dos contratos no escopo de detalhamento.

GET /api/contrato/{contrato_id}/garantias não pagina nem filtra por data. Os
IDs vêm das raws de contratos ativos e inativos, filtrados pelo órgão consumidor.
Uma chamada por contrato é inevitável; o Airflow expande blocos, não IDs, para
respeitar core.max_map_length (ADR-0021).

A fonte costuma devolver [] e isso não é erro. Quando há garantia, o cliente
confere o contrato_id do payload contra o da URL antes de preservar a linha;
um vínculo divergente não pode ser corrigido silenciosamente. O vencimento
fica na raw como veio da fonte, para o recorte temporal posterior na Silver.

A varredura completa envolve milhares de chamadas e só deve estrear em
homologação. INGEST_MAX_CONTRATOS limita a amostra no compose local. Com o
limite padrão de UGs, a raw local pode não conter contratos do MGI (46000):
nesse caso, ingira cabeçalhos de uma UG desse órgão ou ajuste o escopo apenas
no ambiente de teste, sem ampliar a varredura de UGs em produção.
"""

import logging
from datetime import datetime, timedelta
from math import ceil
from typing import Any

from airflow.sdk import dag, get_current_context, task

from batching import chunked, limit_local
from cliente_contratos_gov import ClienteContratosGov
from contratos_gov_scope import ids_contratos_no_escopo, orgaos_no_escopo
from landing_zone import write_raw

SISTEMA = "contratos_gov"
ENTIDADE = "contrato_garantia"
PK = ["id"]
BLOCK_SIZE = 25
MAX_BLOCOS = 1024

default_args = {
    "owner": "mgi",
    "queue": "mgi",
    "retries": 3,
    "retry_delay": timedelta(minutes=10),
}


@dag(
    dag_id="contrato_garantia_ingest_dag",
    schedule="0 15 * * 6",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere garantias por contrato da API Contratos.gov.br para "
        "contratos_gov.raw_contrato_garantia, em blocos e no escopo dos órgãos consumidores."
    ),
    tags=["sistema:contratos_gov", "dominio:contratacoes"],
)
def contrato_garantia_dag() -> None:
    @task
    def get_contract_blocks() -> list[list[str]]:
        ids = ids_contratos_no_escopo(orgaos_no_escopo())
        ids = limit_local(ids, "INGEST_MAX_CONTRATOS", "contratos")
        if not ids:
            raise RuntimeError(
                "INGEST_MAX_CONTRATOS deixou a lista vazia: configure um limite "
                "positivo para validar a ingestão local."
            )
        tamanho = max(BLOCK_SIZE, ceil(len(ids) / MAX_BLOCOS))
        blocos = chunked(ids, tamanho)
        logging.info("Contratos no escopo: %s em %s blocos.", len(ids), len(blocos))
        return blocos

    @task(max_active_tis_per_dag=4)
    def ingest_contracts(contrato_ids: list[str]) -> dict[str, int]:
        api = ClienteContratosGov()
        try:
            run_id = str(get_current_context()["run_id"])
        except RuntimeError:
            # Fora de uma DagRun, write_raw gera o identificador do arquivo.
            run_id = None

        total = 0
        vazios = 0
        repetidas = 0
        for contrato_id in contrato_ids:
            registros = api.listar_subrecurso(contrato_id, "garantias")
            if not registros:
                vazios += 1
                logging.info("Contrato %s: nenhuma garantia.", contrato_id)
                continue

            # O upsert do warehouse recusa a mesma chave duas vezes no lote.
            # Cópias idênticas são descartadas; divergências interrompem a task.
            unicos: dict[str, dict] = {}
            for registro in registros:
                if str(registro.get("contrato_id")) != contrato_id:
                    raise RuntimeError(
                        f"Contrato {contrato_id}: garantia com contrato_id "
                        "divergente da URL."
                    )
                garantia_id = registro.get("id")
                if garantia_id is None:
                    raise RuntimeError(f"Contrato {contrato_id}: garantia sem id.")
                if unicos.setdefault(str(garantia_id), registro) != registro:
                    raise RuntimeError(
                        f"Contrato {contrato_id}: id de garantia {garantia_id!r} "
                        "repetido no lote com conteúdo diferente."
                    )

            lote = list(unicos.values())
            descartadas = len(registros) - len(lote)
            if descartadas:
                repetidas += descartadas
                logging.warning(
                    "Contrato %s: %s garantia(s) idêntica(s) repetida(s) "
                    "na resposta, descartada(s) antes da escrita.",
                    contrato_id,
                    descartadas,
                )

            write_raw(
                SISTEMA,
                ENTIDADE,
                lote,
                primary_key=PK,
                run_id=f"{run_id}__contrato_{contrato_id}" if run_id else None,
            )
            total += len(lote)
            logging.info("Contrato %s: %s garantias gravadas.", contrato_id, len(lote))

        return {
            "garantias": total,
            "contratos_vazios": vazios,
            "linhas_repetidas": repetidas,
        }

    @task
    def validate(results: Any) -> int:
        total = sum(resultado["garantias"] for resultado in results)
        vazios = sum(resultado["contratos_vazios"] for resultado in results)
        repetidas = sum(resultado["linhas_repetidas"] for resultado in results)
        logging.info(
            "Garantias ingeridas: %s em %s blocos; contratos sem garantia: %s; "
            "linhas repetidas descartadas: %s.",
            total,
            len(results),
            vazios,
            repetidas,
        )
        return total

    blocos = get_contract_blocks()
    validate(ingest_contracts.expand(contrato_ids=blocos))


contrato_garantia_dag()
