import logging
import os
from datetime import datetime, timedelta
from typing import List

from airflow.sdk import dag, task

from cliente_siconv import ClienteSiconv
from landing_zone import truncate_raw_warehouse, write_raw
from tabelas_siconv import TABELAS_SICONV

SISTEMA = "siconv"
# Mesmo valor do repositório antigo (sincov_ingest_dag.py): processa o CSV em
# lotes, em vez de materializar tudo em memória de uma vez — o zip nacional do
# SICONV tem tabelas grandes o bastante para estourar a memória do worker.
TAMANHO_LOTE = 5000

default_args = {
    "owner": "mir",
    # Fila dedicada do time (AGENTS.md §5): os workers consomem uma fila cada,
    # em isolamento estrito — sem `queue` a task cairia na fila `default` e
    # rodaria no worker compartilhado, não no worker do MIR.
    "queue": "mir",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="siconv_ingest_dag",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Baixa o zip nacional de dados abertos do SICONV (repositorio.dados."
        "gov.br) e grava as 16 entidades em siconv.raw_<entidade>. Fonte 100% "
        "nacional/genérica, sem filtro de órgão."
    ),
    tags=["sistema:siconv", "dominio:convenios"],
)
def siconv_ingest_dag() -> None:
    @task
    def baixar_siconv() -> str:
        cliente = ClienteSiconv()
        return cliente.baixar_zip()

    @task
    def ingerir_tabela(
        zip_path: str,
        nome_tabela: str,
        nome_csv: str,
        primary_key: List[str],
        skip_rows: int,
        colunas: List[str],
        truncate_before_insert: bool = False,
    ) -> dict:
        cliente = ClienteSiconv(zip_path=zip_path)

        if truncate_before_insert:
            truncate_raw_warehouse(SISTEMA, nome_tabela)

        # Lê e grava em lotes de TAMANHO_LOTE, deduplicando cada lote por
        # linha inteira (mesmo critério do repositório antigo) — evita tanto
        # OOM em tabelas grandes quanto o "ON CONFLICT DO UPDATE command
        # cannot affect row a second time" quando o lote upserta pela mesma
        # chave duas vezes.
        gerador = cliente.ler_csv(
            nome_csv, skip_rows=skip_rows, colunas_esperadas=colunas
        )
        lote: list[dict] = []
        total = 0
        for registro in gerador:
            lote.append(registro)
            if len(lote) >= TAMANHO_LOTE:
                unicos = [dict(t) for t in {tuple(r.items()) for r in lote}]
                # `primary_key or None`: as entidades sem chave (ver
                # tabelas_siconv.py) chegam com a lista vazia — write_raw
                # recebe None, que grava sem tentar upsert.
                write_raw(SISTEMA, nome_tabela, unicos, primary_key=primary_key or None)
                total += len(unicos)
                logging.info(
                    "[siconv_ingest_dag] %s: %s registros processados...",
                    nome_tabela,
                    total,
                )
                lote = []

        if lote:
            unicos = [dict(t) for t in {tuple(r.items()) for r in lote}]
            write_raw(SISTEMA, nome_tabela, unicos, primary_key=primary_key or None)
            total += len(unicos)

        logging.info("[siconv_ingest_dag] %s: %s registros", nome_tabela, total)
        return {nome_tabela: total}

    @task
    def deletar_zip(zip_path: str) -> None:
        if os.path.exists(zip_path):
            os.remove(zip_path)
            logging.info("[siconv_ingest_dag] Arquivo %s deletado", zip_path)
        else:
            logging.warning("[siconv_ingest_dag] Arquivo %s não encontrado", zip_path)

    path_zip = baixar_siconv()

    ultima_task = path_zip
    for tabela in TABELAS_SICONV:
        task_atual = ingerir_tabela.override(task_id=f"ingerir_{tabela['nome_tabela']}")(
            # path_zip é o XComArg de baixar_siconv(), não um str real neste
            # ponto do código — só em tempo de execução. Mesma limitação de
            # tipagem do TaskFlow em toda DAG que encadeia saída de task.
            zip_path=path_zip,  # ty: ignore[invalid-argument-type]
            nome_tabela=tabela["nome_tabela"],
            nome_csv=tabela["nome_csv"],
            primary_key=tabela["primary_key"],
            skip_rows=tabela["skip_rows"],
            colunas=tabela["colunas"],
            truncate_before_insert=tabela.get("truncate_before_insert", False),
        )
        ultima_task >> task_atual
        ultima_task = task_atual

    ultima_task >> deletar_zip(path_zip)  # ty: ignore[invalid-argument-type]


siconv_ingest_dag()
