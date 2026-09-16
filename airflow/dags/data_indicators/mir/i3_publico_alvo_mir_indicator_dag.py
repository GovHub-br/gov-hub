"""I3 — Instrumentos com Público-Alvo Racializado (ADR-0022).

Lê os mesmos modelos do I1 — e não a saída dele: a classificação depende do
texto de objeto e justificativa do instrumento, que a saída do I1 não carrega.
Por não depender do I1, roda no mesmo horário dele.

A classificação normaliza o texto (remoção de diacríticos) e o confronta com
listas de termos por grupo (pessoas negras, quilombolas, indígenas, povos de
terreiro, ciganos) — a regra que motivou a categoria do ADR-0022, por não ser
expressável de forma revisável em SQL.
"""

import logging
from datetime import datetime, timedelta

from airflow.sdk import dag, task

from cliente_postgres import ClientPostgresDB
from indicadores.i3_publico_alvo import calcular_i3
from postgres_helpers import get_postgres_conn

DAG_ID = "i3_publico_alvo_mir_indicator_dag"
CONEXAO = "postgres_dw"
SCHEMA_SAIDA = "003_gld_indicadores"

# Modelo materializado pelo dbt -> nome do argumento de `calcular_i3`.
FONTES = {
    "planos": ("002_slv_transferencias", "planos_acao_ted"),
    "resumo": ("003_gld_transferencias", "ted_resumo_orcamentario"),
    "instrumentos_emendas": ("002_slv_convenios", "instrumentos_emendas"),
    "gold_convenios": ("003_gld_convenios", "resumo_convenios"),
}

default_args = {
    "owner": "mir",
    "queue": "mir",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id=DAG_ID,
    # Depois do mir_transform_dag (06:00). Mesmo horário do I1: lê as mesmas
    # fontes, sem depender da saída dele.
    schedule="0 7 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Calcula o indicador I3 (instrumentos com público-alvo racializado) "
        "classificando o texto dos instrumentos de TED e convênios, e grava "
        "as quatro saídas em 003_gld_indicadores."
    ),
    tags=[
        "orgao:mir",
        "dominio:indicadores",
        "camada:gold",
        "sistema:transferegov_ted",
        "sistema:siconv",
        "sistema:transferegov_emendas",
    ],
)
def i3_publico_alvo_mir_dag() -> None:
    @task
    def calcular_e_gravar_i3() -> dict[str, int]:
        db = ClientPostgresDB(get_postgres_conn(CONEXAO))

        fontes = {
            argumento: db.fetch_table(schema, tabela)
            for argumento, (schema, tabela) in FONTES.items()
        }
        for argumento, linhas in fontes.items():
            logging.info("[I3] %s: %s linhas lidas", argumento, len(linhas))

        saidas = calcular_i3(**fontes)

        dt_calculo = datetime.now().isoformat()
        gravadas = {}
        for tabela, linhas in saidas.items():
            for linha in linhas:
                linha["dt_calculo"] = dt_calculo
            # O indicador é recalculado inteiro: substitui a tabela em vez de
            # fazer upsert, senão uma agregação que deixou de existir na fonte
            # continuaria publicada (ADR-0022).
            db.drop_table_if_exists(tabela, schema=SCHEMA_SAIDA)
            db.insert_data(linhas, tabela, schema=SCHEMA_SAIDA)
            gravadas[tabela] = len(linhas)
            logging.info("[I3] %s.%s: %s linhas", SCHEMA_SAIDA, tabela, len(linhas))

        return gravadas

    calcular_e_gravar_i3()


i3_publico_alvo_mir_dag()
