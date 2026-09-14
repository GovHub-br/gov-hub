import json
import logging
from datetime import datetime, timedelta

from airflow.models import Variable
from airflow.sdk import dag, task

from cliente_email import (
    extract_csv_from_zip,
    fetch_email_with_zip,
    resolve_email_date_range,
)
from email_ingest_params import date_range_params
from landing_zone import write_raw

SISTEMA = "tesouro_gerencial"
ENTIDADE = "programacao_acao_ptres"

COLUMN_MAPPING = {
    0: "programa_governo",
    1: "programa_governo_descricao",
    2: "plano_orcamentario",
    3: "plano_orcamentario_descricao_1",
    4: "plano_orcamentario_descricao_2",
    5: "plano_orcamentario_descricao_3",
    6: "plano_orcamentario_descricao_4",
    7: "plano_orcamentario_descricao_5",
    8: "plano_orcamentario_descricao_6",
    9: "acao_governo",
    10: "acao_governo_descricao",
    11: "ptres",
    12: "natureza_despesa",
    13: "natureza_despesa_descricao",
    14: "dotacao_inicial",
    15: "dotacao_suplementar",
    16: "dotacao_atualizada",
}

# Sem chave natural na fonte. Chave composta pelas colunas de código (sem as
# "_descricao*", redundantes) mais as três colunas de dotação, que juntas
# distinguem as linhas do relatório — mesmo critério do 9-col key de
# ne_tesouro.
PRIMARY_KEY = [
    "programa_governo",
    "plano_orcamentario",
    "acao_governo",
    "ptres",
    "natureza_despesa",
    "dotacao_inicial",
    "dotacao_suplementar",
    "dotacao_atualizada",
]

EMAIL_SUBJECT_SUFFIX = "programacao_acao_por_ptres_mir"
SKIPROWS = 5

default_args = {
    "owner": "mir",
    "queue": "mir",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="programacao_acao_ptres_mir_ingest_dag",
    # Escalonado (00:30) em relação às demais DAGs de tesouro_gerencial/mir
    # que buscam por e-mail — evita que todas loguem no IMAP ao mesmo tempo
    # em @daily (00:00), o que já estourou o [OVERQUOTA] do provedor em
    # produção no repositório antigo — portado de data-application-mir
    # (programacao_acao_ptres_ingest_dag.py).
    schedule="30 0 * * *",
    start_date=datetime(2023, 12, 1),
    catchup=False,
    default_args=default_args,
    params=date_range_params(),
    description=(
        "Processa cada anexo ZIP de programação de ação por PTRES recebido "
        "por e-mail e grava em tesouro_gerencial.raw_programacao_acao_ptres, "
        "um anexo por vez."
    ),
    tags=["sistema:tesouro_gerencial", "dominio:orcamento_financeiro", "orgao:mir"],
)
def programacao_acao_ptres_mir_dag() -> None:
    @task
    def fetch_and_store(params: dict | None = None) -> dict:
        creds = json.loads(Variable.get("email_credentials"))
        start_date, end_date = resolve_email_date_range(
            (params or {}).get("data_inicial"), (params or {}).get("data_final")
        )

        zip_payloads = fetch_email_with_zip(
            creds["imap_server"],
            creds["email"],
            creds["password"],
            creds["sender_email"],
            None,
            start_date=start_date,
            end_date=end_date,
            subject_suffix=EMAIL_SUBJECT_SUFFIX,
        )
        if not zip_payloads:
            logging.warning(
                "[programacao_acao_ptres_mir_ingest_dag] Nenhum anexo ZIP encontrado."
            )
            return {ENTIDADE: 0}

        total = 0
        for idx, payload in enumerate(zip_payloads, start=1):
            df = extract_csv_from_zip(payload, COLUMN_MAPPING, SKIPROWS)
            if df is None:
                logging.warning(
                    "[programacao_acao_ptres_mir_ingest_dag] Anexo %s ignorado "
                    "(CSV inválido).",
                    idx,
                )
                continue

            registros = df.to_dict(orient="records")
            write_raw(SISTEMA, ENTIDADE, registros, primary_key=PRIMARY_KEY)
            total += len(registros)
            logging.info(
                "[programacao_acao_ptres_mir_ingest_dag] anexo %s: %s registros",
                idx,
                len(registros),
            )

        logging.info("[programacao_acao_ptres_mir_ingest_dag] total=%s", total)
        return {ENTIDADE: total}

    fetch_and_store()


programacao_acao_ptres_mir_dag()
