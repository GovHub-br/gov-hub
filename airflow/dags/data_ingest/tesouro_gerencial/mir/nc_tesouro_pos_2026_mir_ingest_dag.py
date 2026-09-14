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
ENTIDADE = "nc_tesouro_pos_2026"

COLUMN_MAPPING = {
    0: "emissao_dia",
    1: "nc",
    2: "emitente_codigo",
    3: "emitente_nome",
    4: "ptres",
    5: "fonte_codigo",
    6: "fonte_nome",
    7: "gnd_codigo",
    8: "gnd_nome",
    9: "pi_codigo",
    10: "pi_nome",
    11: "descricao",
    12: "ugr_codigo",
    13: "ugr_nome",
    14: "tipo_nc",
    15: "nc_item_detalhamento",
    16: "favorecido_codigo",
    17: "favorecido_nome",
    18: "ro",
    19: "nc_transferencia",
    20: "dc",
    21: "item_total",
    22: "total_lista",
    23: "valor_celula",
    24: "esfera_orcamentaria_codigo",
    25: "esfera_orcamentaria_nome",
    26: "emissao_ano",
    27: "emissao_mes",
}

PRIMARY_KEY = [
    "nc",
    "emissao_dia",
    "emissao_mes",
    "emissao_ano",
    "ptres",
    "ugr_codigo",
    "valor_celula",
    "dc",
]

EMAIL_SUBJECT = "notas_credito_mir_apos_2026"
SKIPROWS = 3
DELIMITER = "\t"
# O relatório é um TSV lido com header=None (COLUMN_MAPPING posicional): uma
# única linha com um tab a mais levanta ParserError e derruba a DAG inteira.
# Restaura o comportamento do repositório antigo
# (nc_tesouro_ingest_2026_mir_dag.py:27, que fazia
# `pd.read_csv = partial(pd.read_csv, sep='\t', on_bad_lines='skip')`), agora
# como parâmetro explícito só desta DAG — o monkey-patch global valia para todo
# o processo do worker, inclusive para as outras DAGs.
ON_BAD_LINES = "skip"

default_args = {
    "owner": "mir",
    "queue": "mir",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="nc_tesouro_pos_2026_mir_ingest_dag",
    # Escalonado (00:20) em relação às demais DAGs de tesouro_gerencial/mir
    # que buscam por e-mail — evita que todas loguem no IMAP ao mesmo tempo
    # em @daily (00:00), o que já estourou o [OVERQUOTA] do provedor em
    # produção no repositório antigo — portado de data-application-mir
    # (nc_tesouro_ingest_2026_mir_dag.py).
    schedule="20 0 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    params=date_range_params(),
    description=(
        "Processa cada anexo ZIP de notas de crédito a partir de 2026 recebido "
        "por e-mail e grava em tesouro_gerencial.raw_nc_tesouro_pos_2026, um "
        "anexo por vez."
    ),
    tags=["sistema:tesouro_gerencial", "dominio:orcamento_financeiro", "orgao:mir"],
)
def nc_tesouro_pos_2026_mir_dag() -> None:
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
            # Assunto como critério IMAP nativo SUBJECT (substring, filtrado no
            # servidor), como no repositório antigo
            # (nc_tesouro_ingest_2026_mir_dag.py). Sem ele, o fetch(bulk=True)
            # baixaria TODAS as mensagens do remetente na janela, com anexos —
            # agravando o [OVERQUOTA] do provedor que o escalonamento de
            # horários destas DAGs existe para evitar. Não usamos
            # `subject_suffix` (endswith no cliente) porque ele deixa de casar
            # assuntos com qualquer sufixo depois do token (ex.: "..._2026.zip"),
            # o que causaria ingestão zero em silêncio.
            EMAIL_SUBJECT,
            start_date=start_date,
            end_date=end_date,
        )
        if not zip_payloads:
            logging.warning(
                "[nc_tesouro_pos_2026_mir_ingest_dag] Nenhum anexo ZIP encontrado."
            )
            return {ENTIDADE: 0}

        total = 0
        for idx, payload in enumerate(zip_payloads, start=1):
            df = extract_csv_from_zip(
                payload, COLUMN_MAPPING, SKIPROWS, DELIMITER, ON_BAD_LINES
            )
            if df is None:
                logging.warning(
                    "[nc_tesouro_pos_2026_mir_ingest_dag] Anexo %s ignorado "
                    "(CSV inválido).",
                    idx,
                )
                continue

            registros = df.to_dict(orient="records")
            write_raw(SISTEMA, ENTIDADE, registros, primary_key=PRIMARY_KEY)
            total += len(registros)
            logging.info(
                "[nc_tesouro_pos_2026_mir_ingest_dag] anexo %s: %s registros",
                idx,
                len(registros),
            )

        logging.info("[nc_tesouro_pos_2026_mir_ingest_dag] total=%s", total)
        return {ENTIDADE: total}

    fetch_and_store()


nc_tesouro_pos_2026_mir_dag()
