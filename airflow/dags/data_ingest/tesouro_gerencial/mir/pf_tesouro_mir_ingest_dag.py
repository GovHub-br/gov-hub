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
ENTIDADE = "pf_tesouro"

COLUMN_MAPPING = {
    0: "emissao_mes",
    1: "emissao_dia",
    2: "ug_emitente",
    3: "ug_emitente_descricao",
    4: "ug_favorecido",
    5: "ug_favorecido_descricao",
    6: "pf_evento",
    7: "pf_evento_descricao",
    8: "pf",
    9: "pf_inscricao",
    10: "pf_acao",
    11: "pf_acao_descricao",
    12: "pf_fonte_recursos",
    13: "pf_fonte_recursos_descricao",
    14: "doc_observacao",
    15: "pf_valor_linha",
}

# Sem chave natural na fonte. Chave composta pelas colunas de código (sem as
# "_descricao*", redundantes) mais o valor financeiro da linha, que juntos
# distinguem as linhas do relatório — mesmo critério do 9-col key de
# ne_tesouro.
PRIMARY_KEY = [
    "emissao_mes",
    "emissao_dia",
    "ug_emitente",
    "ug_favorecido",
    "pf_evento",
    "pf",
    "pf_inscricao",
    "pf_acao",
    "pf_fonte_recursos",
    "doc_observacao",
    "pf_valor_linha",
]

EMAIL_SUBJECT = "programacoes_financeiras"
SKIPROWS = 7

default_args = {
    "owner": "mir",
    "queue": "mir",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="pf_tesouro_mir_ingest_dag",
    # Escalonado (00:25) em relação às demais DAGs de tesouro_gerencial/mir
    # que buscam por e-mail — evita que todas loguem no IMAP ao mesmo tempo
    # em @daily (00:00), o que já estourou o [OVERQUOTA] do provedor em
    # produção no repositório antigo — portado de data-application-mir
    # (pf_tesouro_mir_ingest_dag.py).
    schedule="25 0 * * *",
    start_date=datetime(2023, 12, 1),
    catchup=False,
    default_args=default_args,
    params=date_range_params(),
    description=(
        "Processa cada anexo ZIP de programações financeiras recebido por "
        "e-mail e grava em tesouro_gerencial.raw_pf_tesouro, um anexo por vez."
    ),
    tags=["sistema:tesouro_gerencial", "dominio:orcamento_financeiro", "orgao:mir"],
)
def pf_tesouro_mir_dag() -> None:
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
            # Assunto como critério IMAP nativo SUBJECT (substring, filtrado
            # no servidor) — mesmo padrão de nc_tesouro_pos_2026_mir_ingest_dag.py.
            # Sem ele, o fetch(bulk=True) baixa TODAS as mensagens do
            # remetente na janela, com anexos — risco de [OVERQUOTA] do
            # provedor (ver mudanca.md, incidente de 2026-09-14).
            EMAIL_SUBJECT,
            start_date=start_date,
            end_date=end_date,
        )
        if not zip_payloads:
            logging.warning("[pf_tesouro_mir_ingest_dag] Nenhum anexo ZIP encontrado.")
            return {ENTIDADE: 0}

        total = 0
        for idx, payload in enumerate(zip_payloads, start=1):
            df = extract_csv_from_zip(payload, COLUMN_MAPPING, SKIPROWS)
            if df is None:
                logging.warning(
                    "[pf_tesouro_mir_ingest_dag] Anexo %s ignorado (CSV inválido).",
                    idx,
                )
                continue

            registros = df.to_dict(orient="records")
            write_raw(SISTEMA, ENTIDADE, registros, primary_key=PRIMARY_KEY)
            total += len(registros)
            logging.info(
                "[pf_tesouro_mir_ingest_dag] anexo %s: %s registros", idx, len(registros)
            )

        logging.info("[pf_tesouro_mir_ingest_dag] total=%s", total)
        return {ENTIDADE: total}

    fetch_and_store()


pf_tesouro_mir_dag()
