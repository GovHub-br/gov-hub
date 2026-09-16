import csv
import json
import logging
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any

import chardet
from airflow.models import Variable
from airflow.sdk import dag, task

from cliente_email import fetch_email_with_zip, resolve_email_date_range
from email_ingest_params import date_range_params
from landing_zone import write_raw

SISTEMA = "tesouro_gerencial"
ENTIDADE = "ne_tesouro_ppa"

# Colunas fixas (posições 0-31), sempre presentes, mapeadas por posição. A
# posição 31 é o marcador do pivô ("Item Informação Código") no cabeçalho,
# mas nos dados carrega o "Grupo Despesa Nome".
FIXED_COLUMNS: list[str] = [
    "programa_governo",  # 0
    "programa_governo_descricao",  # 1
    "acao_governo",  # 2
    "acao_governo_descricao",  # 3
    "emissao_mes",  # 4
    "emissao_dia",  # 5
    "ne_ccor",  # 6
    "ug_responsavel_codigo",  # 7
    "ug_responsavel_nome",  # 8
    "ne_num_processo",  # 9
    "ne_info_complementar",  # 10
    "ne_ccor_descricao",  # 11
    "doc_observacao",  # 12
    "natureza_despesa",  # 13
    "natureza_despesa_descricao",  # 14
    "ne_ccor_favorecido",  # 15
    "ne_ccor_favorecido_descricao",  # 16
    "ne_ccor_ano_emissao",  # 17
    "ptres",  # 18
    "fonte_recursos_detalhada",  # 19
    "fonte_recursos_detalhada_descricao",  # 20
    "plano_orcamentario_codigo_uo",  # 21
    "plano_orcamentario_codigo_funcao",  # 22
    "plano_orcamentario_codigo_subfuncao",  # 23
    "plano_orcamentario_codigo_programa",  # 24
    "plano_orcamentario_codigo_acao",  # 25
    "plano_orcamentario_codigo_po",  # 26
    "plano_orcamentario_nome",  # 27
    "resultado_eof_codigo",  # 28
    "resultado_eof_nome",  # 29
    "grupo_despesa",  # 30
    "grupo_despesa_desc",  # 31
]
FIXED_WIDTH = len(FIXED_COLUMNS)

# Colunas financeiras (posições 32+), pivotadas pelo Tesouro (uma por "Item
# Informação"). Mapeadas por CÓDIGO, não por posição: o Tesouro só emite a
# coluna de um item quando há valor para ele no período, então qualquer uma
# pode faltar (ex.: sem "restos a pagar pagos" o cabeçalho vem com 37 colunas
# em vez de 38). A ausente vira None no registro. Portado de
# data-application-mir (ne_ppa_tesouro_mir_ingest_dag.py) — a versão anterior
# desta DAG exigia exatamente 38 colunas em posições fixas e quebrava a
# execução inteira sempre que o Tesouro omitia uma coluna sem dado no período.
FINANCIAL_COLUMNS_BY_CODE: dict[str, str] = {
    "13": "dotacao_atualizada",
    "29": "despesas_empenhadas",
    "31": "despesas_liquidadas",
    "34": "despesas_pagas",
    "50": "restos_a_pagar_inscritos",
    "52": "restos_a_pagar_pagos",
}

# Âncora na última posição fixa (31) para detectar desalinhamento da parte fixa.
ITEM_INFO_HEADER = "Item Informação Código"

# Schema canônico completo. Todo registro sai com todas essas chaves (None nas
# financeiras ausentes) para ficar homogêneo — um registro com menos chaves
# gravaria colunas desalinhadas ou perderia valores no write_raw.
TARGET_COLUMNS: list[str] = FIXED_COLUMNS + list(FINANCIAL_COLUMNS_BY_CODE.values())

HEADER_MARKER = '"Programa Governo Código"'
SUB_HEADER_LINES = 2

# O relatório mistura dois graos:
#   - Empenho: uma linha por movimentação contábil de uma NE real
#     (ne_ccor != '-9').
#   - Dotação: orçamento no grão da classificação orçamentária, sem
#     empenho associado — ne_ccor = '-9' em todas as linhas, e um mesmo
#     ne_ccor real ainda pode repetir em várias linhas (uma por
#     favorecido/valor). Por isso a chave inclui a classificação
#     orçamentária e os próprios valores financeiros, que são o que de
#     fato distingue linhas de uma mesma NE ou dotação.
#
# Nota: os valores financeiros fazem parte desta chave e, na prática, só um
# vem preenchido por linha (os demais ficam NULL) — ou seja, a chave admite
# colunas NULL. Por isso ela vai só como `conflict_fields` (UNIQUE INDEX, que
# aceita nulo) na chamada a `write_raw` abaixo, nunca como `primary_key`
# (que materializaria PRIMARY KEY — NOT NULL em toda coluna — e derrubaria o
# insert assim que um lote trouxesse alguma dessas colunas vazia, como
# aconteceu em produção em 2026-09-14: ver `mudanca.md`).
CONFLICT_FIELDS = [
    "ne_ccor",
    "natureza_despesa",
    "doc_observacao",
    "ne_ccor_ano_emissao",
    "emissao_dia",
    "emissao_mes",
    "ne_ccor_favorecido",
    "fonte_recursos_detalhada",
    "ptres",
    "plano_orcamentario_codigo_po",
    "grupo_despesa",
    "dotacao_atualizada",
    "despesas_empenhadas",
    "despesas_liquidadas",
    "despesas_pagas",
    "restos_a_pagar_inscritos",
    "restos_a_pagar_pagos",
]

EMAIL_SUBJECT = "notas_empenho_ppa_mir"

default_args = {
    "owner": "mir",
    "queue": "mir",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def _decode_csv(raw_data: bytes) -> str:
    encoding = chardet.detect(raw_data)["encoding"] or "utf-8"
    return raw_data.decode(encoding, errors="replace")


def _build_positional_columns(header_row: list[str]) -> list[str]:
    """Monta o mapa posição -> coluna alvo a partir do cabeçalho do relatório.

    As 32 colunas fixas vêm por posição; as financeiras (a partir de
    FIXED_WIDTH) são resolvidas pelo código "Item Informação" na própria
    linha de cabeçalho, pois qualquer uma pode faltar quando não há dado no
    período. Levanta ValueError se a parte fixa desalinhou ou se surgir um
    código financeiro desconhecido/duplicado.
    """
    anchor = header_row[FIXED_WIDTH - 1] if len(header_row) >= FIXED_WIDTH else None
    if anchor != ITEM_INFO_HEADER:
        raise ValueError(
            f"Layout do relatório mudou: esperava {FIXED_WIDTH} colunas fixas "
            f"terminando em '{ITEM_INFO_HEADER}' na posição {FIXED_WIDTH - 1}, "
            f"mas o cabeçalho tem {len(header_row)} colunas e a posição "
            f"{FIXED_WIDTH - 1} é '{anchor}'. Revise FIXED_COLUMNS antes de "
            "prosseguir."
        )

    financial_positions: list[str] = []
    seen_codes: set = set()
    for offset, code in enumerate(header_row[FIXED_WIDTH:]):
        target = FINANCIAL_COLUMNS_BY_CODE.get(code)
        if target is None:
            raise ValueError(
                f"Layout do relatório mudou: coluna financeira desconhecida na "
                f"posição {FIXED_WIDTH + offset} com código Item Informação "
                f"'{code}'. Códigos conhecidos: {sorted(FINANCIAL_COLUMNS_BY_CODE)}."
            )
        if code in seen_codes:
            raise ValueError(
                f"Layout do relatório mudou: código Item Informação '{code}' "
                "aparece duplicado no cabeçalho."
            )
        seen_codes.add(code)
        financial_positions.append(target)

    missing = [c for c in FINANCIAL_COLUMNS_BY_CODE if c not in seen_codes]
    if missing:
        logging.info(
            "[ne_tesouro_ppa_mir_ingest_dag] colunas financeiras ausentes neste "
            "relatório (sem dado no período): %s.",
            ", ".join(f"{c}->{FINANCIAL_COLUMNS_BY_CODE[c]}" for c in missing),
        )

    return FIXED_COLUMNS + financial_positions


def parse_ppa_csv(csv_data: str) -> list[dict[str, Any]]:
    """Parser do relatório "Notas de empenhos por programa PPA" do Tesouro.

    Lê sempre como texto (sem passar por pandas.read_csv, que inferiria
    tipos numéricos e comeria os zeros à esquerda de códigos como
    programa_governo "0032"). Mapeia as 32 colunas fixas por posição e as
    financeiras por código "Item Informação" (qualquer uma pode faltar no
    relatório), ignora a linha final "Total" e linhas cuja largura não bate
    com o cabeçalho.
    """
    lines = csv_data.splitlines()
    header_idx = next(
        (i for i, line in enumerate(lines) if line.lstrip().startswith(HEADER_MARKER)),
        None,
    )
    if header_idx is None:
        raise ValueError(
            f"Cabeçalho do relatório não encontrado — esperava uma linha "
            f"começando com {HEADER_MARKER}."
        )

    header_row = next(csv.reader([lines[header_idx]]))
    positional_columns = _build_positional_columns(header_row)
    expected_width = len(positional_columns)

    data_start = header_idx + 1 + SUB_HEADER_LINES
    records: list[dict[str, Any]] = []
    skipped = 0
    for line in lines[data_start:]:
        if not line.strip():
            continue
        try:
            row = next(csv.reader([line]))
        except csv.Error:
            skipped += 1
            continue
        if row and row[0] == "Total":
            continue
        if len(row) != expected_width:
            skipped += 1
            continue

        # Começa com o schema canônico completo: financeiras ausentes ficam
        # None, mantendo todos os registros com as mesmas chaves.
        record: dict[str, Any] = {name: None for name in TARGET_COLUMNS}
        for pos, name in enumerate(positional_columns):
            record[name] = row[pos].strip() or None
        records.append(record)

    if skipped:
        logging.warning(
            "[ne_tesouro_ppa_mir_ingest_dag] %s linha(s) descartada(s) por "
            "largura inválida.",
            skipped,
        )
    logging.info(
        "[ne_tesouro_ppa_mir_ingest_dag] parser concluído: %s linhas no "
        "schema canônico.",
        len(records),
    )
    return records


def _filter_and_dedupe(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Mantém os dois graos: empenho (ne_ccor real) e dotação (ne_ccor = '-9',
    # só dotacao_atualizada preenchida). Um filtro só por ano em
    # ne_ccor_ano_emissao descartaria toda a dotação, que traz '-9' nesse
    # campo também.
    kept = [
        r
        for r in records
        if (r.get("ne_ccor_ano_emissao") or "").startswith("20")
        or r.get("dotacao_atualizada") is not None
    ]

    # Protege o upsert contra chaves repetidas no mesmo lote, que fariam o
    # INSERT inteiro falhar.
    seen: dict[tuple[Any, ...], dict[str, Any]] = {}
    for r in kept:
        key = tuple(r.get(c) for c in CONFLICT_FIELDS)
        seen[key] = r
    return list(seen.values())


@dag(
    dag_id="ne_tesouro_ppa_mir_ingest_dag",
    # Escalonado (00:05) em relação às demais DAGs de tesouro_gerencial/mir
    # que buscam por e-mail — evita que todas loguem no IMAP ao mesmo tempo
    # em @daily (00:00), o que já estourou o [OVERQUOTA] do provedor em
    # produção no repositório antigo — portado de data-application-mir
    # (ne_ppa_tesouro_mir_ingest_dag.py).
    schedule="5 0 * * *",
    start_date=datetime(2023, 12, 1),
    catchup=False,
    default_args=default_args,
    params=date_range_params(),
    description=(
        "Processa cada anexo ZIP de notas de empenho por programa PPA "
        "recebido por e-mail e grava em tesouro_gerencial.raw_ne_tesouro_ppa, "
        "um anexo por vez."
    ),
    tags=["sistema:tesouro_gerencial", "dominio:orcamento_financeiro", "orgao:mir"],
)
def ne_tesouro_ppa_mir_dag() -> None:
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
            # remetente na janela, com anexos — foi o que estourou o
            # [OVERQUOTA] do provedor em 2026-09-14 (ver mudanca.md).
            EMAIL_SUBJECT,
            start_date=start_date,
            end_date=end_date,
        )
        if not zip_payloads:
            logging.warning(
                "[ne_tesouro_ppa_mir_ingest_dag] Nenhum anexo ZIP encontrado."
            )
            return {ENTIDADE: 0}

        total = 0
        for idx, payload in enumerate(zip_payloads, start=1):
            with zipfile.ZipFile(BytesIO(payload)) as zip_file:
                csv_names = [n for n in zip_file.namelist() if n.lower().endswith(".csv")]
                if not csv_names:
                    logging.warning(
                        "[ne_tesouro_ppa_mir_ingest_dag] Anexo %s ignorado "
                        "(sem CSV no ZIP).",
                        idx,
                    )
                    continue
                raw_data = zip_file.read(csv_names[0])

            if not raw_data.strip():
                logging.warning(
                    "[ne_tesouro_ppa_mir_ingest_dag] Anexo %s ignorado (CSV vazio).",
                    idx,
                )
                continue

            csv_data = _decode_csv(raw_data)
            registros = _filter_and_dedupe(parse_ppa_csv(csv_data))
            write_raw(
                SISTEMA,
                ENTIDADE,
                registros,
                primary_key=None,
                conflict_fields=CONFLICT_FIELDS,
            )
            total += len(registros)
            logging.info(
                "[ne_tesouro_ppa_mir_ingest_dag] anexo %s: %s registros",
                idx,
                len(registros),
            )

        logging.info("[ne_tesouro_ppa_mir_ingest_dag] total=%s", total)
        return {ENTIDADE: total}

    fetch_and_store()


ne_tesouro_ppa_mir_dag()
