import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from airflow.sdk import dag, task
from batching import chunked
from cliente_camara_deputados import ClienteCamaraDeputados
from landing_zone import write_raw

if TYPE_CHECKING:
    from parlamentares_controle import Candidato

SISTEMA = "camara_deputados"
ENTIDADE = "deputados_historico"
BLOCK_SIZE = 50

default_args = {
    "owner": "camara_deputados",
    "queue": "camara_deputados",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="deputados_historico_ingest_dag",
    schedule="@weekly",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere o histórico de mandato (filiação, situação, condição "
        "eleitoral) de deputados, controlando incrementalmente quem precisa "
        "de nova extração (portado de data-application-mir: "
        "parlamentares_controle_historico_dag), para "
        "camara_deputados.raw_deputados_historico."
    ),
    tags=["sistema:camara_deputados", "dominio:parlamentares"],
)
def deputados_historico_ingest_dag() -> None:
    @task
    def sync_atuais() -> list[int]:
        api = ClienteCamaraDeputados()
        atuais = api.get_deputados_atuais()
        if atuais is None:
            raise RuntimeError(
                "Falha ao obter snapshot atual de deputados. Execução "
                "interrompida para evitar fechamento indevido de mandatos."
            )
        ids = sorted(
            {int(d["id"]) for d in atuais if isinstance(d, dict) and d.get("id")}
        )
        logging.info(
            "[deputados_historico_ingest_dag] %s deputado(s) em exercício.", len(ids)
        )
        return ids

    @task
    def get_candidato_blocks(ids_atuais: list[int]) -> "list[list[Candidato]]":
        # Import local: parlamentares_controle usa psycopg2 direto (não passa
        # por landing_zone), então fica de fora do topo do módulo por ADR-0021
        # — um deployment object_storage pode não ter driver de banco.
        from parlamentares_controle import preparar_candidatos
        from postgres_helpers import get_postgres_conn

        conn_str = get_postgres_conn("postgres_dw")
        candidatos = preparar_candidatos(
            conn_str, SISTEMA, "raw_deputados_historico", ids_atuais
        )
        blocks = chunked(candidatos, BLOCK_SIZE)
        logging.info(
            "[deputados_historico_ingest_dag] %s candidato(s) elegível(eis) em "
            "%s bloco(s) de até %s.",
            len(candidatos),
            len(blocks),
            BLOCK_SIZE,
        )
        return blocks

    @task(max_active_tis_per_dag=4)
    def fetch_and_store_bloco(bloco: list[dict]) -> list[dict[str, Any]]:
        from parlamentares_controle import limpar_historico_existente
        from postgres_helpers import get_postgres_conn

        api = ClienteCamaraDeputados()
        conn_str = get_postgres_conn("postgres_dw")
        resultados: list[dict[str, Any]] = []
        for candidato in bloco:
            deputado_id = candidato["parlamentar_id"]
            historico = api.get_historico_deputado(deputado_id)
            sucesso = historico is not None
            if historico:
                for item in historico:
                    item["parlamentar_id"] = int(deputado_id)
                # Evita duplicar eventos já gravados numa extração anterior
                # deste deputado (ver docstring de limpar_historico_existente).
                limpar_historico_existente(
                    conn_str, SISTEMA, f"raw_{ENTIDADE}", deputado_id
                )
                write_raw(SISTEMA, ENTIDADE, historico, primary_key=None)
            resultados.append(
                {
                    "parlamentar_id": deputado_id,
                    "status_anterior": candidato["status"],
                    "sucesso": sucesso,
                    "registros": len(historico) if historico else 0,
                }
            )
        return resultados

    @task
    def fechar_e_registrar(blocos_resultados: list[list[dict[str, Any]]]) -> None:
        from parlamentares_controle import fechar_apos_extracao
        from postgres_helpers import get_postgres_conn

        resultados = [r for bloco in blocos_resultados for r in bloco]
        conn_str = get_postgres_conn("postgres_dw")
        fechar_apos_extracao(conn_str, SISTEMA, resultados)
        total = sum(r["registros"] for r in resultados)
        logging.info(
            "[deputados_historico_ingest_dag] total=%s eventos, deputados "
            "processados=%s",
            total,
            len(resultados),
        )

    ids_atuais = sync_atuais()
    blocos = get_candidato_blocks(ids_atuais)  # ty: ignore[invalid-argument-type]
    resultados = fetch_and_store_bloco.expand(bloco=blocos)
    fechar_e_registrar(resultados)  # ty: ignore[invalid-argument-type]


deputados_historico_ingest_dag()
