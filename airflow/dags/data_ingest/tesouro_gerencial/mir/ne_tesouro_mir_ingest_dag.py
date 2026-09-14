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
ENTIDADE = "ne_tesouro"

COLUMN_MAPPING = {
    0: "programa_governo",
    1: "programa_governo_descricao",
    2: "acao_governo",
    3: "acao_governo_descricao",
    4: "emissao_mes",
    5: "emissao_dia",
    6: "ne_ccor",
    7: "ne_num_processo",
    8: "ne_info_complementar",
    9: "ne_ccor_descricao",
    10: "doc_observacao",
    11: "natureza_despesa",
    12: "natureza_despesa_descricao",
    13: "ne_ccor_favorecido",
    14: "ne_ccor_favorecido_descricao",
    15: "ne_ccor_ano_emissao",
    16: "ptres",
    17: "fonte_recursos_detalhada",
    18: "fonte_recursos_detalhada_descricao",
    19: "despesas_empenhadas",
    20: "despesas_liquidadas",
    21: "despesas_pagas",
    22: "restos_a_pagar_inscritos",
    23: "restos_a_pagar_pagos",
}

PRIMARY_KEY = [
    "ne_ccor",
    "natureza_despesa",
    "doc_observacao",
    "ne_ccor_ano_emissao",
    "emissao_dia",
    "emissao_mes",
    "despesas_empenhadas",
    "despesas_liquidadas",
    "despesas_pagas",
]

EMAIL_SUBJECT_SUFFIX = "notas_de_empenho_ano_atual"
SKIPROWS = 8
OPTIONAL_COLUMNS = ["restos_a_pagar_inscritos", "restos_a_pagar_pagos"]

default_args = {
    "owner": "mir",
    "queue": "mir",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="ne_tesouro_mir_ingest_dag",
    # Escalonado (00:00) em relação às demais DAGs de tesouro_gerencial/mir
    # que buscam por e-mail — evita que todas loguem no IMAP ao mesmo tempo,
    # o que já estourou o [OVERQUOTA] do provedor em produção no
    # repositório antigo — portado de data-application-mir
    # (ne_tesouro_mir_ingest_dag.py).
    schedule="0 0 * * *",
    start_date=datetime(2023, 12, 1),
    catchup=False,
    default_args=default_args,
    params=date_range_params(),
    description=(
        "Processa cada anexo ZIP de notas de empenho do ano corrente recebido "
        "por e-mail e grava em tesouro_gerencial.raw_ne_tesouro, um anexo por vez."
    ),
    tags=["sistema:tesouro_gerencial", "dominio:orcamento_financeiro", "orgao:mir"],
)
def ne_tesouro_mir_dag() -> None:
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
            logging.warning("[ne_tesouro_mir_ingest_dag] Nenhum anexo ZIP encontrado.")
            return {ENTIDADE: 0}

        total = 0
        for idx, payload in enumerate(zip_payloads, start=1):
            df = extract_csv_from_zip(payload, COLUMN_MAPPING, SKIPROWS)
            if df is None:
                logging.warning(
                    "[ne_tesouro_mir_ingest_dag] Anexo %s ignorado (CSV inválido).", idx
                )
                continue

            for coluna in OPTIONAL_COLUMNS:
                if coluna not in df.columns:
                    df[coluna] = None

            df = df[df["ne_ccor_ano_emissao"].astype(str).str.startswith("20")]
            registros = df.to_dict(orient="records")
            write_raw(SISTEMA, ENTIDADE, registros, primary_key=PRIMARY_KEY)
            total += len(registros)
            logging.info(
                "[ne_tesouro_mir_ingest_dag] anexo %s: %s registros", idx, len(registros)
            )

        logging.info("[ne_tesouro_mir_ingest_dag] total=%s", total)
        return {ENTIDADE: total}

    fetch_and_store()


ne_tesouro_mir_dag()
