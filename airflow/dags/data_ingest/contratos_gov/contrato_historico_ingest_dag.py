"""Ingestão semanal do histórico dos contratos do Contratos.gov.br.

O endpoint ``GET /api/contrato/{contrato_id}/historico`` não tem paginação nem
filtro por período. A carga precisa, portanto, consultar todos os contratos já
ingeridos nas entidades ``contrato_ativo`` e ``contrato_inativo``; o recorte
temporal fica para a Bronze/Silver, que dispõe de ``alterado_em``.

Cada contrato é consultado uma vez e os contratos são processados em blocos,
porque expandir milhares de IDs diretamente criaria uma task instance por ID e
estouraria ``core.max_map_length``. ``INGEST_MAX_CONTRATOS`` limita somente o
compose local: a carga completa não deve ser executada na máquina do
desenvolvedor e a primeira execução completa acontece em homologação.

O vínculo ``contrato_id`` é sempre derivado da URL. O cliente compara esse
valor com o que vier no payload antes de injetá-lo, evitando gravar histórico
de um contrato sob outro ID. No backend ``warehouse``, ``id`` faz o upsert; em
``object_storage``, a raw é append-only e a Silver deduplica por ``dt_ingest``.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from airflow.sdk import Variable, dag, task
from batching import chunked, limit_local
from cliente_contratos_gov import ClienteContratosGov
from landing_zone import distinct_raw_rows, write_raw

SISTEMA = "contratos_gov"
ENTIDADES_CONTRATO = ("contrato_ativo", "contrato_inativo")
PK = ["id"]
BLOCK_SIZE = 50
VARIAVEL_ESCOPO = "contratos_gov_escopo_orgaos"
ESCOPO_PADRAO = ["46000"]

default_args = {
    "owner": "mgi",
    "queue": "mgi",
    "retries": 3,
    "retry_delay": timedelta(minutes=10),
}


def _validar_historico(contrato_id: str, registros: list[dict[str, Any]]) -> None:
    ids: set[Any] = set()
    duplicados: set[Any] = set()
    for indice, registro in enumerate(registros):
        registro_id = registro.get("id")
        if registro_id is None:
            raise RuntimeError(
                f"[/api/contrato/{contrato_id}/historico] Registro {indice} "
                "sem id; o histórico não será gravado."
            )
        if registro_id in ids:
            duplicados.add(registro_id)
        ids.add(registro_id)

    if duplicados:
        raise RuntimeError(
            f"[/api/contrato/{contrato_id}/historico] IDs duplicados na resposta: "
            f"{sorted(duplicados)!r}; o histórico não será gravado."
        )


@dag(
    dag_id="contrato_historico_ingest_dag",
    schedule="0 12 * * 6",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere o histórico dos contratos da API Contratos.gov.br para "
        "contratos_gov.raw_contrato_historico. Varredura semanal em blocos de contratos."
    ),
    tags=["sistema:contratos_gov", "dominio:contratacoes"],
)
def contrato_historico_dag() -> None:
    @task
    def get_contract_blocks() -> list[list[str]]:
        escopo = Variable.get(
            VARIAVEL_ESCOPO,
            default=ESCOPO_PADRAO,
            deserialize_json=True,
        )
        if not isinstance(escopo, list) or not all(
            isinstance(codigo, (str, int)) for codigo in escopo
        ):
            raise RuntimeError(
                f"Variable '{VARIAVEL_ESCOPO}' deve ser uma lista de códigos de órgão."
            )
        escopo_codigos = {str(codigo) for codigo in escopo}
        ids: set[str] = set()
        for entidade in ENTIDADES_CONTRATO:
            try:
                linhas = distinct_raw_rows(SISTEMA, entidade, ["id", "orgao_codigo"])
            except Exception as exc:
                raise RuntimeError(
                    f"Entidade '{entidade}' ainda não está na zona raw. "
                    "Execute contrato_ativo_ingest_dag e "
                    "contrato_inativo_ingest_dag antes de "
                    "contrato_historico_ingest_dag."
                ) from exc
            ids.update(
                str(contrato_id)
                for contrato_id, orgao_codigo in linhas
                if str(orgao_codigo) in escopo_codigos
            )

        if not ids:
            raise RuntimeError(
                "As entidades 'contrato_ativo' e 'contrato_inativo' estão na raw, "
                "mas não há nenhum contrato para consultar. Execute as DAGs de "
                "cabeçalho antes de contrato_historico_ingest_dag."
            )

        contratos = limit_local(sorted(ids), "INGEST_MAX_CONTRATOS", "contratos")
        blocos = chunked(contratos, BLOCK_SIZE)
        logging.info(
            "Total de contratos a consultar: %s em %s blocos de até %s",
            len(contratos),
            len(blocos),
            BLOCK_SIZE,
        )
        return blocos

    @task(max_active_tis_per_dag=4)
    def ingest_contracts(contrato_ids: list[str]) -> dict[str, int]:
        api = ClienteContratosGov()
        historicos = 0

        for contrato_id in contrato_ids:
            registros = api.listar_subrecurso(contrato_id, "historico")
            if not registros:
                raise RuntimeError(
                    f"[/api/contrato/{contrato_id}/historico] Resposta vazia "
                    "para contrato existente na raw; esse contrato não será gravado."
                )
            _validar_historico(contrato_id, registros)
            write_raw(SISTEMA, "contrato_historico", registros, primary_key=PK)
            historicos += len(registros)

        return {"historicos": historicos}

    @task
    def validate(results: Any) -> int:
        total = sum(resultado["historicos"] for resultado in results)
        logging.info(
            "Histórico de contratos total: registros=%s blocos=%s",
            total,
            len(results),
        )
        return total

    blocos = get_contract_blocks()
    resultados = ingest_contracts.expand(contrato_ids=blocos)
    validate(resultados)


contrato_historico_dag()
