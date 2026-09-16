import json
import logging
from datetime import datetime, timedelta
from typing import TypedDict

from airflow.models import Variable
from airflow.sdk import dag, task

from cliente_email import (
    extract_csv_from_zip,
    fetch_email_with_zip,
    open_mailbox,
    resolve_email_date_range,
)
from email_ingest_params import date_range_params
from landing_zone import write_raw

SISTEMA = "tesouro_gerencial"
ENTIDADE = "nc_tesouro_pre_2026"

COLUMN_MAPPING = {
    0: "programa_governo",
    1: "programa_governo_descricao",
    2: "acao_governo",
    3: "acao_governo_descricao",
    4: "nc",
    5: "nc_transferencia",
    6: "nc_fonte_recursos",
    7: "nc_fonte_recursos_descricao",
    8: "ptres",
    9: "nc_evento",
    10: "nc_evento_descricao",
    11: "nc_ug_responsavel",
    12: "nc_ug_responsavel_descricao",
    13: "nc_natureza_despesa",
    14: "nc_natureza_despesa_descricao",
    15: "nc_plano_interno",
    16: "nc_plano_interno_descricao1",
    17: "nc_plano_interno_descricao2",
    18: "favorecido_doc",
    19: "favorecido_doc_descricao",
    20: "favorecido_municipio",
    21: "favorecido_municipio_descricao",
    22: "nc_valor_linha",
    23: "movimento_liquido_moeda_origem",
}

# Sem chave natural na fonte (o relatório não traz um id de linha). Chave
# composta por todas as colunas de código + os dois valores financeiros, que
# juntos distinguem as linhas do relatório — mesmo critério do 9-col key de
# ne_tesouro. As colunas "_descricao*" ficam de fora por serem redundantes com
# o código correspondente.
PRIMARY_KEY = [
    "nc",
    "nc_transferencia",
    "nc_fonte_recursos",
    "ptres",
    "nc_evento",
    "nc_ug_responsavel",
    "nc_natureza_despesa",
    "nc_plano_interno",
    "favorecido_doc",
    "favorecido_municipio",
    "nc_valor_linha",
    "movimento_liquido_moeda_origem",
]


# O relatório sai em dois e-mails separados, com layouts de cabeçalho
# diferentes apesar de terem as mesmas 24 colunas de dado — portado de
# data-application-mir (nc_tesouro_ingest_2025_mir_dag.py):
#   - "enviadas": o CSV já sai com o cabeçalho no formato esperado pela
#     origem, então column_mapping é aplicado por posição (header=None).
#   - "recebidas": o CSV vem com o cabeçalho "humano" (nomes em português,
#     sem tratamento), então column_mapping fica None (header=0, mantém o
#     nome real de cada coluna) — o mapeamento para o schema alvo acontece
#     depois, por posição, só se a contagem de colunas bater com as 24
#     esperadas (ver fallback em `fetch_and_store`).
# Usar o mesmo column_mapping posicional (header=None) para as duas, como uma
# versão anterior desta DAG fazia, faz a própria linha de cabeçalho do CSV
# "recebidas" ser lida como se fosse a primeira linha de dado (SKIPROWS pula
# só o preâmbulo do relatório, não o cabeçalho) — daí colunas com o próprio
# nome do cabeçalho como valor (ex.: nc_valor_linha = "NC - Valor Linha").
class EmailConfig(TypedDict):
    subject: str
    column_mapping: dict[int, str] | None
    skiprows: int


EMAIL_CONFIGS: dict[str, EmailConfig] = {
    "enviadas": {
        "subject": "notas_credito_mir_ate_2025",
        "column_mapping": COLUMN_MAPPING,
        "skiprows": 6,
    },
    "recebidas": {
        "subject": "notas_credito_recebidas_ate_2025",
        "column_mapping": None,
        "skiprows": 6,
    },
}

default_args = {
    "owner": "mir",
    "queue": "mir",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id="nc_tesouro_pre_2026_mir_ingest_dag",
    # Escalonado (00:15) em relação às demais DAGs de tesouro_gerencial/mir
    # que buscam por e-mail: rodar todas juntas em @daily (00:00) faz cada
    # uma logar no IMAP ao mesmo tempo, o que já estourou o [OVERQUOTA] do
    # provedor em produção no repositório antigo — portado de
    # data-application-mir (nc_tesouro_ingest_2025_mir_dag.py).
    schedule="15 0 * * *",
    start_date=datetime(2023, 12, 1),
    catchup=False,
    default_args=default_args,
    params=date_range_params(),
    description=(
        "Processa os anexos ZIP de notas de crédito (enviadas e recebidas) "
        "até 2025 recebidos por e-mail e grava em "
        "tesouro_gerencial.raw_nc_tesouro_pre_2026, um anexo por vez."
    ),
    tags=["sistema:tesouro_gerencial", "dominio:orcamento_financeiro", "orgao:mir"],
)
def nc_tesouro_pre_2026_mir_dag() -> None:
    @task
    def fetch_and_store(params: dict | None = None) -> dict:
        creds = json.loads(Variable.get("email_credentials"))
        start_date, end_date = resolve_email_date_range(
            (params or {}).get("data_inicial"), (params or {}).get("data_final")
        )

        total = 0
        # Uma única sessão IMAP para as duas buscas (enviadas + recebidas):
        # dois logins em sequência já foram o suficiente para estourar o
        # [OVERQUOTA] do provedor em produção — portado de
        # data-application-mir (nc_tesouro_ingest_2025_mir_dag.py).
        with open_mailbox(
            creds["imap_server"], creds["email"], creds["password"]
        ) as mailbox:
            for email_type, config in EMAIL_CONFIGS.items():
                zip_payloads = fetch_email_with_zip(
                    creds["imap_server"],
                    creds["email"],
                    creds["password"],
                    creds["sender_email"],
                    # Assunto como critério IMAP nativo SUBJECT (substring,
                    # filtrado no servidor), como no repositório antigo
                    # (nc_tesouro_ingest_2025_mir_dag.py). Sem ele o
                    # fetch(bulk=True) baixaria TODAS as mensagens do remetente
                    # na janela — duas vezes, uma por config —, agravando o
                    # [OVERQUOTA] do provedor. Não usamos `subject_suffix`
                    # (endswith no cliente) porque ele deixa de casar assuntos
                    # com qualquer sufixo depois do token (ex.: "..._2025.zip"),
                    # o que causaria ingestão zero em silêncio.
                    config["subject"],
                    start_date=start_date,
                    end_date=end_date,
                    mailbox=mailbox,
                )
                if not zip_payloads:
                    logging.warning(
                        "[nc_tesouro_pre_2026_mir_ingest_dag] Nenhum anexo ZIP "
                        "encontrado para '%s'.",
                        email_type,
                    )
                    continue

                for idx, payload in enumerate(zip_payloads, start=1):
                    df = extract_csv_from_zip(
                        payload, config["column_mapping"], config["skiprows"]
                    )
                    if df is None:
                        logging.warning(
                            "[nc_tesouro_pre_2026_mir_ingest_dag] Anexo %s de '%s' "
                            "ignorado (CSV inválido).",
                            idx,
                            email_type,
                        )
                        continue

                    # "recebidas" chega sem column_mapping (cabeçalho humano,
                    # já lido como header real por extract_csv_from_zip). Só
                    # remapeamos para o schema alvo se a contagem de colunas
                    # bater com as 24 esperadas — do contrário o layout mudou e
                    # remapear por posição gravaria dado errado em silêncio.
                    if config["column_mapping"] is None and not df.empty:
                        if len(df.columns) == len(COLUMN_MAPPING):
                            df.columns = list(COLUMN_MAPPING.values())
                        else:
                            logging.warning(
                                "[nc_tesouro_pre_2026_mir_ingest_dag] '%s': "
                                "cabeçalho com %s coluna(s), esperava %s — "
                                "mantendo nomes originais do CSV.",
                                email_type,
                                len(df.columns),
                                len(COLUMN_MAPPING),
                            )

                    registros = df.to_dict(orient="records")
                    write_raw(SISTEMA, ENTIDADE, registros, primary_key=PRIMARY_KEY)
                    total += len(registros)
                    logging.info(
                        "[nc_tesouro_pre_2026_mir_ingest_dag] '%s' anexo %s: %s registros",
                        email_type,
                        idx,
                        len(registros),
                    )

        logging.info("[nc_tesouro_pre_2026_mir_ingest_dag] total=%s", total)
        return {ENTIDADE: total}

    fetch_and_store()


nc_tesouro_pre_2026_mir_dag()
