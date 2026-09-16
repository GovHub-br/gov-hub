import csv
import io
import json
import logging
import zipfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import chardet
import pandas as pd
from airflow.models import Variable
from airflow.sdk import dag, task

from cliente_email import fetch_email_with_zip, resolve_email_date_range
from email_ingest_params import date_range_params
from landing_zone import write_raw

# Empenhos de emendas parlamentares do SIAFI, extraídos do mesmo tipo de
# relatório do Tesouro Gerencial de ne_tesouro_mir_ingest_dag.py, mas por
# e-mail e assunto distintos, e com um parser próprio: o relatório concatena
# múltiplos sub-relatórios (um por "Ano Lançamento"), cada um com seu próprio
# cabeçalho e número de colunas financeiras diferente — não dá para usar o
# COLUMN_MAPPING posicional de ne_tesouro_mir_ingest_dag.py.
#
# Portado de data-application-mir (dags/data_ingest/tesouro_gerencial/mir/
# ne_tesouro_emendas_mir_ingest_dag.py). O parser mapeia colunas pelo NOME do
# cabeçalho (não pela posição), e por isso é resiliente à mudança de largura
# entre sub-relatórios.
#
# O relatório traz DOIS graos na mesma tabela:
#   - Empenho: cada linha é uma movimentação contábil de uma NE (ne_ccor
#     real, ne_ccor_ano_emissao com o ano).
#   - Dotação (itens 9/13): orçamento no grão da classificação
#     (programa/ação/localizador/natureza/modalidade/fonte/ptres), sem
#     empenho — ne_ccor = '-9' em todas as linhas.
# Como ne_ccor é constante ('-9') nas linhas de dotação, a chave precisa
# incluir a classificação orçamentária para identificá-las sem colisão; para
# as linhas de empenho essas colunas são função do próprio empenho, então não
# alteram a deduplicação.

SISTEMA = "tesouro_gerencial"
ENTIDADE = "ne_tesouro_emendas"
EMAIL_SUBJECT = "notas_de_empenhos_emendas_parlamentares"

TARGET_COLUMNS: List[str] = [
    "emissao_mes",
    "emissao_dia",
    "programa_governo",
    "programa_governo_descricao",
    "acao_governo",
    "acao_governo_descricao",
    "autor_emendas_orcamento",
    "autor_emendas_orcamento_descricao",
    "localizador_gasto",
    "localizador_gasto_descricao",
    "regiao_pt",
    "uf_pt",
    "uf_pt_descricao",
    "municipio_pt",
    "ne_ccor",
    "ne_num_processo",
    "ne_info_complementar",
    "ne_ccor_descricao",
    "doc_observacao",
    "grupo_despesa",
    "grupo_despesa_descricao",
    "natureza_despesa",
    "natureza_despesa_descricao",
    "modalidade_aplicacao",
    "modalidade_aplicacao_descricao",
    "ne_ccor_favorecido",
    "ne_ccor_favorecido_descricao",
    "ne_ccor_ano_emissao",
    "ptres",
    "fonte_recursos_detalhada",
    "fonte_recursos_detalhada_descricao",
    "dotacao_inicial",
    "dotacao_atualizada",
    "despesas_empenhadas",
    "despesas_liquidadas",
    "despesas_pagas",
    "restos_a_pagar_inscritos",
    "restos_a_pagar_pagos",
]

HEADER_TO_CANONICAL: Dict[str, str] = {
    "Emissão - Mês": "emissao_mes",
    "Emissão - Dia": "emissao_dia",
    "Programa Governo": "programa_governo",
    "Ação Governo": "acao_governo",
    "Autor Emendas Orçamento": "autor_emendas_orcamento",
    "Localizador Gasto": "localizador_gasto",
    "Região PT": "regiao_pt",
    "UF PT": "uf_pt",
    "Município PT": "municipio_pt",
    "NE CCor": "ne_ccor",
    "NE - Núm. Processo": "ne_num_processo",
    "NE - Informação Complementar": "ne_info_complementar",
    "NE CCor - Descrição": "ne_ccor_descricao",
    "Doc - Observação": "doc_observacao",
    "Grupo Despesa": "grupo_despesa",
    "Natureza Despesa": "natureza_despesa",
    "Modalidade Aplicação": "modalidade_aplicacao",
    "NE CCor - Favorecido": "ne_ccor_favorecido",
    "NE CCor - Ano Emissão": "ne_ccor_ano_emissao",
    "PTRES": "ptres",
    # Header diz "Item Informação" mas a coluna traz o código da fonte de
    # recursos (ex.: 1000000000 = RECURSOS LIVRES DA UNIAO).
    "Item Informação": "fonte_recursos_detalhada",
}

HEADERS_WITH_DESCRICAO = {
    "Programa Governo",
    "Ação Governo",
    "Autor Emendas Orçamento",
    "Localizador Gasto",
    "UF PT",
    "Grupo Despesa",
    "Natureza Despesa",
    "Modalidade Aplicação",
    "NE CCor - Favorecido",
    "Item Informação",
}

ITEM_CODE_TO_CANONICAL = {
    "9": "dotacao_inicial",
    "13": "dotacao_atualizada",
    "29": "despesas_empenhadas",
    "31": "despesas_liquidadas",
    "34": "despesas_pagas",
    "50": "restos_a_pagar_inscritos",
    "52": "restos_a_pagar_pagos",
}

HEADER_MARKER = '"Emissão - Mês"'
SUB_HEADER_LINES = 2

UNIQUE_KEY = [
    "ne_ccor",
    "emissao_mes",
    "emissao_dia",
    "doc_observacao",
    "ptres",
    "natureza_despesa",
    "modalidade_aplicacao",
    "localizador_gasto",
    "fonte_recursos_detalhada",
]

default_args = {
    "owner": "mir",
    "queue": "mir",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def _build_column_map(header_row: List[str]) -> Dict[str, int]:
    col_map: Dict[str, int] = {}
    for pos, raw in enumerate(header_row):
        name = raw.strip()
        if name in HEADER_TO_CANONICAL:
            canonical = HEADER_TO_CANONICAL[name]
            col_map[canonical] = pos
            if name in HEADERS_WITH_DESCRICAO:
                col_map[f"{canonical}_descricao"] = pos + 1
        elif name in ITEM_CODE_TO_CANONICAL:
            col_map[ITEM_CODE_TO_CANONICAL[name]] = pos
    return col_map


def parse_tesouro_emendas_csv(
    csv_data: str,
    column_mapping: Optional[Dict[int, str]] = None,
    skiprows: int = 0,
    delimiter: Optional[str] = None,
) -> pd.DataFrame:
    """Parser do relatório do Tesouro Gerencial de empenhos de emendas.

    O arquivo concatena múltiplos sub-relatórios (um por "Ano Lançamento"),
    cada um com seu próprio cabeçalho e número de colunas financeiras
    diferente. O parser detecta cada sub-relatório pelo cabeçalho repetido e
    mapeia colunas pelo nome (não por posição).

    `column_mapping`, `skiprows` e `delimiter` são ignorados — existem só
    para que `_extract_emendas_from_zip` possa chamar esta função com a
    mesma assinatura de `cliente_email.format_csv`.
    """
    del column_mapping, skiprows, delimiter

    lines = csv_data.splitlines()
    header_indices = [
        i for i, line in enumerate(lines) if line.lstrip().startswith(HEADER_MARKER)
    ]
    if not header_indices:
        raise ValueError(
            "Nenhum cabeçalho de empenhos de emendas encontrado no CSV — "
            f"esperava linhas começando com {HEADER_MARKER}."
        )

    sub_report_ranges = [
        (start, header_indices[idx + 1] if idx + 1 < len(header_indices) else len(lines))
        for idx, start in enumerate(header_indices)
    ]

    records: List[Dict[str, Any]] = []
    for sub_idx, (h_start, h_end) in enumerate(sub_report_ranges, start=1):
        header_row = next(csv.reader([lines[h_start]]))
        col_map = _build_column_map(header_row)
        expected_width = len(header_row)
        data_start = h_start + 1 + SUB_HEADER_LINES

        ne_pos = col_map.get("ne_ccor")
        if ne_pos is None:
            logging.warning(
                "[ne_tesouro_emendas_mir_ingest_dag] Sub-relatório %s: cabeçalho "
                "sem coluna 'NE CCor'; ignorando.",
                sub_idx,
            )
            continue

        kept = 0
        for line in lines[data_start:h_end]:
            if not line.strip():
                continue
            try:
                row = next(csv.reader([line]))
            except csv.Error:
                continue
            if len(row) != expected_width:
                continue
            if ne_pos >= len(row) or not row[ne_pos].strip():
                continue

            record: Dict[str, Any] = {}
            for canonical, pos in col_map.items():
                if pos < len(row):
                    value = row[pos].strip()
                    record[canonical] = value if value else None
            records.append(record)
            kept += 1

        logging.info(
            "[ne_tesouro_emendas_mir_ingest_dag] Sub-relatório %s: %s colunas, "
            "%s linhas.",
            sub_idx,
            expected_width,
            kept,
        )

    df = pd.DataFrame(records, columns=TARGET_COLUMNS)
    logging.info(
        "[ne_tesouro_emendas_mir_ingest_dag] Parser concluído: %s linhas no schema "
        "canônico.",
        len(df),
    )
    return df


def _extract_emendas_from_zip(zip_payload: bytes) -> Optional[pd.DataFrame]:
    """Extrai e faz o parse de múltiplos sub-relatórios do primeiro CSV no ZIP.

    Réplica local do laço de `cliente_email.extract_csv_from_zip`, chamando
    `parse_tesouro_emendas_csv` no lugar de `format_csv` diretamente — evita
    o monkey-patch de `cliente_email.format_csv` (global, não seguro sob
    execução concorrente e incompatível com a assinatura tipada de
    `format_csv` verificada pelo `ty`).
    """
    with zipfile.ZipFile(io.BytesIO(zip_payload)) as zip_file:
        for file_name in zip_file.namelist():
            if not file_name.lower().endswith(".csv"):
                continue
            raw_data = zip_file.read(file_name)
            if not raw_data.strip():
                logging.warning("CSV vazio no anexo ZIP: %s", file_name)
                continue
            encoding = chardet.detect(raw_data)["encoding"]
            decoded_data = raw_data.decode(encoding or "utf-8", errors="replace")
            if not decoded_data.strip():
                logging.warning("CSV vazio no anexo ZIP: %s", file_name)
                continue
            return parse_tesouro_emendas_csv(decoded_data)
    return None


@dag(
    dag_id="ne_tesouro_emendas_mir_ingest_dag",
    # Escalonado (00:10) em relação às demais DAGs de tesouro_gerencial/mir
    # que buscam por e-mail — evita que todas loguem no IMAP ao mesmo tempo
    # em @daily (00:00), o que já estourou o [OVERQUOTA] do provedor em
    # produção no repositório antigo — portado de data-application-mir
    # (ne_tesouro_emendas_mir_ingest_dag.py).
    schedule="10 0 * * *",
    start_date=datetime(2023, 12, 1),
    catchup=False,
    default_args=default_args,
    params=date_range_params(),
    description=(
        "Processa cada anexo ZIP de empenhos de emendas parlamentares recebido "
        "por e-mail e grava em tesouro_gerencial.raw_ne_tesouro_emendas, um "
        "anexo por vez."
    ),
    tags=["sistema:tesouro_gerencial", "dominio:emendas_parlamentares", "orgao:mir"],
)
def ne_tesouro_emendas_mir_dag() -> None:
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
            # (ne_tesouro_emendas_mir_ingest_dag.py). Sem ele, o fetch(bulk=True)
            # baixaria TODAS as mensagens do remetente na janela, com anexos —
            # agravando o [OVERQUOTA] do provedor que o escalonamento de
            # horários destas DAGs existe para evitar. Não usamos
            # `subject_suffix` (endswith no cliente) porque ele deixa de casar
            # assuntos com qualquer sufixo depois do token (ex.: "....zip"), o
            # que causaria ingestão zero em silêncio.
            EMAIL_SUBJECT,
            start_date=start_date,
            end_date=end_date,
        )
        if not zip_payloads:
            logging.warning(
                "[ne_tesouro_emendas_mir_ingest_dag] Nenhum anexo ZIP encontrado."
            )
            return {ENTIDADE: 0}

        dataframes: List[pd.DataFrame] = []
        for idx, payload in enumerate(zip_payloads, start=1):
            df = _extract_emendas_from_zip(payload)
            if df is None or df.empty:
                logging.warning(
                    "[ne_tesouro_emendas_mir_ingest_dag] Anexo %s ignorado (CSV "
                    "inválido ou vazio).",
                    idx,
                )
                continue
            dataframes.append(df)

        if not dataframes:
            logging.warning(
                "[ne_tesouro_emendas_mir_ingest_dag] Nenhum anexo processado com "
                "sucesso."
            )
            return {ENTIDADE: 0}

        df = pd.concat(dataframes, ignore_index=True)

        # Mantém dois graos: empenhos (ne_ccor_ano_emissao com o ano) e linhas
        # de dotação (itens 9/13, sem empenho).
        is_empenho = df["ne_ccor_ano_emissao"].fillna("").str.startswith("20")
        has_dotacao = df["dotacao_inicial"].notna() | df["dotacao_atualizada"].notna()
        df = df[is_empenho | has_dotacao]

        # Protege o upsert contra chaves repetidas no mesmo lote (linhas
        # idênticas vindas de anexos distintos), que fariam o INSERT falhar.
        df = df.drop_duplicates(subset=UNIQUE_KEY, keep="last")

        registros = df.where(pd.notnull(df), None).to_dict(orient="records")
        write_raw(SISTEMA, ENTIDADE, registros, primary_key=UNIQUE_KEY)

        logging.info("[ne_tesouro_emendas_mir_ingest_dag] total=%s", len(registros))
        return {ENTIDADE: len(registros)}

    fetch_and_store()


ne_tesouro_emendas_mir_dag()
