import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from airflow.sdk import dag, task
from batching import chunked
from cliente_senado_federal import ClienteSenadoFederal
from landing_zone import write_raw

if TYPE_CHECKING:
    from parlamentares_controle import Candidato

SISTEMA = "senado_federal"
ENTIDADE = "senadores_historico"
FONTE = "senado"
BLOCK_SIZE = 50

default_args = {
    "owner": "senado_federal",
    "queue": "senado_federal",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="senadores_historico_ingest_dag",
    schedule="@weekly",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere, na estrutura bruta da API, o histórico de filiações "
        "partidárias de senadores, controlando incrementalmente quem precisa "
        "de nova extração (portado de data-application-mir: "
        "parlamentares_controle_historico_dag), para "
        "senado_federal.raw_senadores_historico."
    ),
    tags=["sistema:senado_federal", "dominio:parlamentares"],
)
def senadores_historico_ingest_dag() -> None:
    @task
    def sync_atuais() -> list[int]:
        api = ClienteSenadoFederal()
        atuais = api.get_senadores_atuais()
        if not atuais:
            raise RuntimeError(
                "Falha ao obter snapshot atual do Senado (vazio inesperado). "
                "Execução interrompida para evitar fechamento indevido de "
                "mandatos."
            )
        ids = sorted(
            {
                int(item.get("IdentificacaoParlamentar", {}).get("CodigoParlamentar"))
                for item in atuais
                if isinstance(item, dict)
                and item.get("IdentificacaoParlamentar", {}).get("CodigoParlamentar")
            }
        )
        logging.info(
            "[senadores_historico_ingest_dag] %s senador(es) em exercício.", len(ids)
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
            conn_str, SISTEMA, "raw_senadores_historico", ids_atuais
        )
        blocks = chunked(candidatos, BLOCK_SIZE)
        logging.info(
            "[senadores_historico_ingest_dag] %s candidato(s) elegível(eis) em "
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

        api = ClienteSenadoFederal()
        conn_str = get_postgres_conn("postgres_dw")
        resultados: list[dict[str, Any]] = []
        for candidato in bloco:
            senador_id = candidato["parlamentar_id"]
            filiacoes = api.get_filiacoes_senador(senador_id)
            sucesso = filiacoes is not None
            if filiacoes:
                for item in filiacoes:
                    item["parlamentar_id"] = int(senador_id)
                    item["fonte"] = FONTE
                # Evita duplicar filiações já gravadas numa extração anterior
                # deste senador (ver docstring de limpar_historico_existente).
                limpar_historico_existente(
                    conn_str, SISTEMA, f"raw_{ENTIDADE}", senador_id
                )
                write_raw(SISTEMA, ENTIDADE, filiacoes, primary_key=None)
            resultados.append(
                {
                    "parlamentar_id": senador_id,
                    "status_anterior": candidato["status"],
                    "sucesso": sucesso,
                    "registros": len(filiacoes) if filiacoes else 0,
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
            "[senadores_historico_ingest_dag] total=%s filiações, senadores "
            "processados=%s",
            total,
            len(resultados),
        )

    ids_atuais = sync_atuais()
    blocos = get_candidato_blocks(ids_atuais)  # ty: ignore[invalid-argument-type]
    resultados = fetch_and_store_bloco.expand(bloco=blocos)
    fechar_e_registrar(resultados)  # ty: ignore[invalid-argument-type]


senadores_historico_ingest_dag()
