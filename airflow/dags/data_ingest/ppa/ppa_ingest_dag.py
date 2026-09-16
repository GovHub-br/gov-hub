import logging
import os
from datetime import datetime, timedelta
from typing import List

from airflow.sdk import dag, task

from cliente_ppa import ClientePPA
from landing_zone import write_raw
from tabelas_ppa import TABELAS_PPA

SISTEMA = "ppa"
# Mesmo valor do repositório antigo (data-application-mir/ppa_ingestao_dag.py):
# processa o CSV em lotes, em vez de materializar tudo em memória de uma vez.
TAMANHO_LOTE = 5000

# Prefixo comum das URLs dos dados abertos do PPA/SIOP.
_PREFIXO = (
    "https://www.gov.br/planejamento/pt-br/assuntos/planejamento/plano-plurianual/"
    "arquivos/lei-do-ppa-2024-2027/"
)

# Links diretos dos .zip. Todos precisam do sufixo /@@display-file/file (Plone):
# sem ele, a URL "nua" do zip de 2024 devolve a página HTML, não o arquivo.
URL_PPA_2024 = _PREFIXO + "ppa-2024-2027-dados-abertos.zip/@@display-file/file"
URL_PPA_2025 = (
    _PREFIXO + "revisao-ppa-2025/ppa2024-2027_atualizado_2025.zip/@@display-file/file"
)
URL_PPA_2026 = (
    _PREFIXO + "revisao-2026/dados-abertos_ppa_2024_2027-revisao_2026.zip"
    "/@@display-file/file"
)

# Cada revisão contribui apenas os CSVs do seu próprio ano (ver tabelas_ppa.py).
ZIPS_PPA = [
    (2024, URL_PPA_2024),
    (2025, URL_PPA_2025),
    (2026, URL_PPA_2026),
]

default_args = {
    "owner": "mpo",
    "queue": "mpo",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="ppa_ingest_dag",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Baixa os 3 zips de dados abertos do PPA/SIOP (revisões 2024, 2025, 2026) "
        "e grava as 31 entidades em ppa.raw_<entidade>, uma tabela por entidade "
        "empilhando as revisões via ano_ppa."
    ),
    tags=["sistema:ppa", "dominio:planejamento_orcamentario"],
)
def ppa_ingest_dag() -> None:
    @task
    def baixar_ppa(ano: int, url: str) -> str:
        cliente = ClientePPA(ano_ppa=ano, url=url)
        return cliente.baixar_zip()

    @task
    def ingerir_tabela(
        zip_path: str,
        ano: int,
        nome_tabela: str,
        arquivo: str,
        primary_key: List[str],
        skip_rows: int,
    ) -> dict:
        cliente = ClientePPA(ano_ppa=ano)
        cliente.zip_path = zip_path

        # Lê e grava em lotes de TAMANHO_LOTE, deduplicando cada lote por
        # id_hash antes do write_raw: sem isso, um CSV com duas linhas iguais
        # no mesmo lote faz o upsert do backend `warehouse` falhar com
        # "ON CONFLICT DO UPDATE command cannot affect row a second time"
        # (a mesma proteção que o repositório antigo já tinha).
        lote: list[dict] = []
        total = 0
        for registro in cliente.ler_csv(arquivo, skip_rows=skip_rows):
            lote.append(registro)
            if len(lote) >= TAMANHO_LOTE:
                unicos = list({r["id_hash"]: r for r in lote}.values())
                write_raw(SISTEMA, nome_tabela, unicos, primary_key=primary_key)
                total += len(unicos)
                lote = []

        if lote:
            unicos = list({r["id_hash"]: r for r in lote}.values())
            write_raw(SISTEMA, nome_tabela, unicos, primary_key=primary_key)
            total += len(unicos)

        logging.info(
            "[ppa_ingest_dag] %s: %s registros (ano %s)", nome_tabela, total, ano
        )
        return {nome_tabela: total}

    @task
    def deletar_zip(zip_path: str) -> None:
        if os.path.exists(zip_path):
            os.remove(zip_path)
            logging.info("[ppa_ingest_dag] Arquivo %s deletado", zip_path)
        else:
            logging.warning("[ppa_ingest_dag] Arquivo %s não encontrado", zip_path)

    # Encadeia as 3 revisões em sequência (um zip em disco por vez):
    # baixar_ppa_{ano} -> ingerir_{tabela}_{ano} (em série) -> deletar_zip_{ano}.
    fim_revisao_anterior = None
    for ano, url in ZIPS_PPA:
        path_zip = baixar_ppa.override(task_id=f"baixar_ppa_{ano}")(ano=ano, url=url)

        if fim_revisao_anterior is not None:
            fim_revisao_anterior >> path_zip

        ultima_task = path_zip
        for tabela in TABELAS_PPA:
            arquivo = tabela["arquivos"].get(ano)
            if not arquivo:
                continue
            task_ingestao = ingerir_tabela.override(
                task_id=f"ingerir_{tabela['nome_tabela']}_{ano}"
            )(
                zip_path=path_zip,  # ty: ignore[invalid-argument-type]
                ano=ano,
                nome_tabela=tabela["nome_tabela"],
                arquivo=arquivo,
                primary_key=tabela["primary_key"],
                skip_rows=tabela["skip_rows"],
            )
            ultima_task >> task_ingestao
            ultima_task = task_ingestao

        limpeza = deletar_zip.override(task_id=f"deletar_zip_{ano}")(
            path_zip  # ty: ignore[invalid-argument-type]
        )
        ultima_task >> limpeza
        fim_revisao_anterior = limpeza


ppa_ingest_dag()
