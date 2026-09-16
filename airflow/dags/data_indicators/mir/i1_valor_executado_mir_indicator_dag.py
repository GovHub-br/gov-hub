"""I1 — Valor Executado por Instrumento (ADR-0022).

Lê os modelos já materializados pelo `mir_transform_dag` (TED, convênios e
emendas), aplica a metodologia da equipe de BI (`helpers/indicadores/
i1_valor_executado.py`) e grava as seis saídas do indicador em
`003_gld_indicadores`.

É a base dos demais: I2 e I9 leem a saída daqui em vez de reprocessar as
mesmas fontes, para que os indicadores nunca divirjam sobre qual é o universo
de instrumentos considerado.
"""

import logging
from datetime import datetime, timedelta

from airflow.sdk import dag, task

from cliente_postgres import ClientPostgresDB
from indicadores.i1_valor_executado import calcular_i1
from postgres_helpers import get_postgres_conn

DAG_ID = "i1_valor_executado_mir_indicator_dag"
CONEXAO = "postgres_dw"
SCHEMA_SAIDA = "003_gld_indicadores"

# Modelo materializado pelo dbt -> nome do argumento de `calcular_i1`.
FONTES = {
    "planos": ("002_slv_transferencias", "planos_acao_ted"),
    "resumo": ("003_gld_transferencias", "ted_resumo_orcamentario"),
    "pf": ("002_slv_transferencias", "pf_unificado_planos_acao"),
    "nc": ("002_slv_transferencias", "nc_plano_acao"),
    "ne": ("003_gld_transferencias", "ted_empenhos_plano_acao"),
    "gold_convenios": ("003_gld_convenios", "resumo_convenios"),
    "instrumentos_emendas": ("002_slv_convenios", "instrumentos_emendas"),
}

default_args = {
    "owner": "mir",
    "queue": "mir",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id=DAG_ID,
    # Depois do mir_transform_dag (06:00), que materializa todas as fontes.
    schedule="0 7 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Calcula o indicador I1 (valor executado por instrumento) sobre os "
        "modelos de TED, convênios e emendas e grava as seis saídas em "
        "003_gld_indicadores."
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
def i1_valor_executado_mir_dag() -> None:
    @task
    def calcular_e_gravar_i1() -> dict[str, int]:
        db = ClientPostgresDB(get_postgres_conn(CONEXAO))

        fontes = {
            argumento: db.fetch_table(schema, tabela)
            for argumento, (schema, tabela) in FONTES.items()
        }
        for argumento, linhas in fontes.items():
            logging.info("[I1] %s: %s linhas lidas", argumento, len(linhas))

        saidas = calcular_i1(**fontes)

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
            logging.info("[I1] %s.%s: %s linhas", SCHEMA_SAIDA, tabela, len(linhas))

        return gravadas

    calcular_e_gravar_i1()


i1_valor_executado_mir_dag()
