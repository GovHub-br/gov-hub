"""I9 — Municípios Atendidos, Convênios/Fomentos (ADR-0022).

Só existe para convênios e fomentos: no TED, o único campo de município
disponível registra a sede do executor, não o local de execução — medir
cobertura territorial por ele concentraria tudo artificialmente em Brasília
(decisão da equipe de BI).

Como o I2, lê a **saída do I1** em vez de reprocessar os modelos dbt, para
não divergir do universo que o I1 considerou. Roda, por isso, depois dele.
"""

import logging
from datetime import datetime, timedelta

from airflow.sdk import dag, task

from cliente_postgres import ClientPostgresDB
from indicadores.i9_municipios_atendidos import calcular_i9
from postgres_helpers import get_postgres_conn

DAG_ID = "i9_municipios_atendidos_mir_indicator_dag"
CONEXAO = "postgres_dw"
SCHEMA_SAIDA = "003_gld_indicadores"

# Saída do I1 lida por este indicador.
FONTE = (SCHEMA_SAIDA, "i1_convenios_por_municipio")

default_args = {
    "owner": "mir",
    "queue": "mir",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id=DAG_ID,
    # Depois do i1_valor_executado_mir_indicator_dag (07:00), que grava a
    # tabela lida aqui.
    schedule="0 8 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Calcula o indicador I9 (municípios atendidos e cobertura territorial "
        "de convênios/fomentos) sobre a saída do I1 e grava as duas saídas em "
        "003_gld_indicadores."
    ),
    tags=[
        "orgao:mir",
        "dominio:indicadores",
        "camada:gold",
        "sistema:siconv",
    ],
)
def i9_municipios_atendidos_mir_dag() -> None:
    @task
    def calcular_e_gravar_i9() -> dict[str, int]:
        db = ClientPostgresDB(get_postgres_conn(CONEXAO))

        schema, tabela = FONTE
        convenios_por_municipio = db.fetch_table(schema, tabela)
        logging.info("[I9] %s: %s linhas lidas", tabela, len(convenios_por_municipio))

        saidas = calcular_i9(convenios_por_municipio)

        dt_calculo = datetime.now().isoformat()
        gravadas = {}
        for tabela_saida, linhas in saidas.items():
            for linha in linhas:
                linha["dt_calculo"] = dt_calculo
            # O indicador é recalculado inteiro: substitui a tabela em vez de
            # fazer upsert, senão uma agregação que deixou de existir na fonte
            # continuaria publicada (ADR-0022).
            db.drop_table_if_exists(tabela_saida, schema=SCHEMA_SAIDA)
            db.insert_data(linhas, tabela_saida, schema=SCHEMA_SAIDA)
            gravadas[tabela_saida] = len(linhas)
            logging.info("[I9] %s.%s: %s linhas", SCHEMA_SAIDA, tabela_saida, len(linhas))

        return gravadas

    calcular_e_gravar_i9()


i9_municipios_atendidos_mir_dag()
