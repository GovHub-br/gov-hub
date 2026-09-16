"""I2 — Concentração Institucional dos Executores (ADR-0022).

Diferente do I1 e do I3, este indicador não reprocessa os modelos dbt: ele lê
a **saída do I1**, já gravada em `003_gld_indicadores`. É decisão da equipe de
BI, para que os dois indicadores nunca divirjam sobre quem está no universo
considerado — e é por isso que esta DAG roda depois da do I1.
"""

import logging
from datetime import datetime, timedelta

from airflow.sdk import dag, task

from cliente_postgres import ClientPostgresDB
from indicadores.i2_concentracao_executores import calcular_i2
from postgres_helpers import get_postgres_conn

DAG_ID = "i2_concentracao_executores_mir_indicator_dag"
CONEXAO = "postgres_dw"
SCHEMA_SAIDA = "003_gld_indicadores"

# Saídas do I1 -> nome do argumento de `calcular_i2`.
FONTES = {
    "teds_i1": (SCHEMA_SAIDA, "i1_ted_por_instrumento"),
    "convenios_i1": (SCHEMA_SAIDA, "i1_convenios_por_instrumento"),
}

default_args = {
    "owner": "mir",
    "queue": "mir",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id=DAG_ID,
    # Depois do i1_valor_executado_mir_indicator_dag (07:00), que grava as
    # tabelas lidas aqui.
    schedule="0 8 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Calcula o indicador I2 (concentração institucional dos executores, "
        "índice HHI) sobre a saída do I1 e grava as seis saídas em "
        "003_gld_indicadores."
    ),
    tags=[
        "orgao:mir",
        "dominio:indicadores",
        "camada:gold",
        "sistema:transferegov_ted",
        "sistema:siconv",
    ],
)
def i2_concentracao_executores_mir_dag() -> None:
    @task
    def calcular_e_gravar_i2() -> dict[str, int]:
        db = ClientPostgresDB(get_postgres_conn(CONEXAO))

        fontes = {
            argumento: db.fetch_table(schema, tabela)
            for argumento, (schema, tabela) in FONTES.items()
        }
        for argumento, linhas in fontes.items():
            logging.info("[I2] %s: %s linhas lidas", argumento, len(linhas))

        saidas = calcular_i2(**fontes)

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
            logging.info("[I2] %s.%s: %s linhas", SCHEMA_SAIDA, tabela, len(linhas))

        return gravadas

    calcular_e_gravar_i2()


i2_concentracao_executores_mir_dag()
