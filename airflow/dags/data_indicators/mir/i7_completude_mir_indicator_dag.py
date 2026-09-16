"""I7 — Completude e Qualidade dos Dados (ADR-0022).

Mede o preenchimento coluna a coluna do dado como ele chega da fonte, antes de
qualquer tratamento. No repositório de origem isso eram os modelos `bronze/`
do dbt; aqui a camada equivalente é a **zona raw**, que o ADR-0021 deixou de
materializar como modelo — por isso as fontes abaixo são tabelas
`<sistema>.raw_<entidade>`, e não modelos dbt como nos demais indicadores.

Duas diferenças de contagem em relação à origem, ambas por mudança real do
layout do dado, não por omissão:

- `nc_tesouro_mir` era um modelo único que unia dois relatórios do Tesouro; na
  ingestão nova cada um tem sua própria entidade (`raw_nc_tesouro_pre_2026` e
  `raw_nc_tesouro_pos_2026`), então TEDs passa de 9 para 10 tabelas;
- `tg_emendas` e `tg_emendas_dotacao` eram dois modelos sobre a mesma fonte,
  separados pelo grão (`ne_ccor = '-9'` ou não). A ingestão nova grava os dois
  grãos em `raw_ne_tesouro_emendas`, então Emendas passa de 14 para 13.

Requer `RAW_BACKEND=warehouse` (ADR-0021): no backend de object storage a raw
são arquivos Parquet, e não existe tabela a ler aqui.
"""

import logging
from datetime import datetime, timedelta

from airflow.sdk import dag, task

from cliente_postgres import ClientPostgresDB
from indicadores.i7_completude import completude_tabela, consolidar_i7
from postgres_helpers import get_postgres_conn

DAG_ID = "i7_completude_mir_indicator_dag"
CONEXAO = "postgres_dw"
SCHEMA_SAIDA = "003_gld_indicadores"

_ENTIDADES_SICONV = (
    "convenio",
    "cronograma_desembolso",
    "desbloqueio",
    "desembolso",
    "empenho",
    "historico_situacao",
    "ingresso_contrapartida",
    "licitacao",
    "meta_crono_fisico",
    "pagamento",
    "pagamento_tributo",
    "proposta",
    "prorroga_oficio",
    "solicitacao_alteracao",
    "solicitacao_rendimento_aplicacao",
    "termo_aditivo",
)

# "Pasta" do relatório da BI -> tabelas da zona raw que a compõem. Diferente da
# origem, uma pasta pode cruzar mais de um sistema: o dado de TED vem tanto do
# Transferegov quanto do Tesouro Gerencial.
FONTES = {
    "TEDs": [
        ("transferegov_ted", "raw_programas"),
        ("transferegov_ted", "raw_planos_acao"),
        ("transferegov_ted", "raw_notas_de_credito"),
        ("transferegov_ted", "raw_programacao_financeira"),
        ("tesouro_gerencial", "raw_programacao_acao_ptres"),
        ("tesouro_gerencial", "raw_ne_tesouro"),
        ("tesouro_gerencial", "raw_ne_tesouro_ppa"),
        ("tesouro_gerencial", "raw_pf_tesouro"),
        ("tesouro_gerencial", "raw_nc_tesouro_pre_2026"),
        ("tesouro_gerencial", "raw_nc_tesouro_pos_2026"),
    ],
    "Convênios": [("siconv", f"raw_{entidade}") for entidade in _ENTIDADES_SICONV],
    "Emendas": [
        ("tesouro_gerencial", "raw_ne_tesouro_emendas"),
        ("transferegov_emendas", "raw_documentos_habeis_especiais"),
        ("transferegov_emendas", "raw_empenhos_especiais"),
        ("transferegov_emendas", "raw_executor_especial"),
        ("transferegov_emendas", "raw_finalidades_especiais"),
        ("transferegov_emendas", "raw_historico_pagamentos_especiais"),
        ("transferegov_emendas", "raw_metas_especiais"),
        ("transferegov_emendas", "raw_ordens_bancarias_especiais"),
        ("transferegov_emendas", "raw_plano_trabalho_especial"),
        ("transferegov_emendas", "raw_planos_acao_especiais"),
        ("transferegov_emendas", "raw_programas_especiais"),
        ("transferegov_emendas", "raw_relatorio_gestao_especial"),
        ("transferegov_emendas", "raw_relatorios_gestao_novo_especial"),
    ],
}

default_args = {
    "owner": "mir",
    "queue": "mir",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id=DAG_ID,
    # Não depende do mir_transform_dag: lê a raw, que a ingestão alimenta.
    # Mantido no mesmo horário dos demais indicadores por conveniência
    # operacional, não por dependência.
    schedule="0 7 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Calcula o indicador I7 (completude e qualidade) varrendo coluna a "
        "coluna as tabelas da zona raw de TED, convênios e emendas, e grava "
        "as saídas em 003_gld_indicadores."
    ),
    tags=[
        "orgao:mir",
        "dominio:indicadores",
        "camada:gold",
        "sistema:transferegov_ted",
        "sistema:tesouro_gerencial",
        "sistema:siconv",
        "sistema:transferegov_emendas",
    ],
)
def i7_completude_mir_dag() -> None:
    @task
    def calcular_e_gravar_i7() -> dict[str, int]:
        db = ClientPostgresDB(get_postgres_conn(CONEXAO))

        # Uma tabela por vez, descartando as linhas brutas antes de ler a
        # próxima: algumas entidades do SICONV têm milhões de linhas, e
        # acumular todas antes de calcular derrubou o worker por memória na
        # primeira execução real da origem. Só o agregado (poucas linhas por
        # tabela) fica retido.
        linhas_colunas: list[dict] = []
        linhas_tabelas: list[dict] = []
        for pasta, tabelas in FONTES.items():
            for schema, nome_tabela in tabelas:
                linhas = db.fetch_table(schema, nome_tabela)
                logging.info(
                    "[I7] %s/%s.%s: %s linhas lidas",
                    pasta,
                    schema,
                    nome_tabela,
                    len(linhas),
                )

                cols, resumo = completude_tabela(pasta, nome_tabela, linhas)
                del linhas  # libera antes de ler a próxima tabela
                if resumo is None:
                    continue
                linhas_colunas.extend(cols)
                linhas_tabelas.append(resumo)

        saidas = consolidar_i7(linhas_colunas, linhas_tabelas)

        dt_calculo = datetime.now().isoformat()
        gravadas = {}
        for tabela, linhas_saida in saidas.items():
            for linha in linhas_saida:
                linha["dt_calculo"] = dt_calculo
            # O indicador é recalculado inteiro: substitui a tabela em vez de
            # fazer upsert, senão uma agregação que deixou de existir na fonte
            # continuaria publicada (ADR-0022).
            db.drop_table_if_exists(tabela, schema=SCHEMA_SAIDA)
            db.insert_data(linhas_saida, tabela, schema=SCHEMA_SAIDA)
            gravadas[tabela] = len(linhas_saida)
            logging.info("[I7] %s.%s: %s linhas", SCHEMA_SAIDA, tabela, len(linhas_saida))

        return gravadas

    calcular_e_gravar_i7()


i7_completude_mir_dag()
