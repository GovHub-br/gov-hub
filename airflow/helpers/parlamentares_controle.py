"""Controle de estado para ingestão incremental de histórico de parlamentares.

Portado de data-application-mir
(``airflow_lappis/dags/data_ingest/dados_abertos/mir/parlamentares_controle_historico_dag.py``),
que mantinha uma única tabela de controle (``dados_abertos.parlamentares_controle``)
compartilhada entre Câmara e Senado. O gov-bricks separa cada sistema em seu
próprio pacote (ADR-0004/0009), então aqui a mesma lógica fica parametrizada
por ``schema`` e roda uma vez por sistema — uma tabela
``<schema>.controle_historico`` por chamador (``deputados_historico_ingest_dag``,
``senadores_historico_ingest_dag``).

Sem este controle, uma DAG de histórico reprocessaria toda semana **todos** os
parlamentares já conhecidos na raw, o que é caro contra a API pública e, com o
universo de IDs grande o bastante, estoura o limite de mapeamento do Airflow
(``unmappable_return_value_length``) ao tentar `.expand()` sobre a lista
inteira. Este módulo resolve a parte de "quem precisa ser reprocessado"; o
chunking em blocos na DAG (``batching.chunked``) resolve o tamanho do
`.expand()` independentemente de quantos candidatos sobrarem — inclusive no
bootstrap, quando o universo inteiro vira candidato de uma vez.
"""

import logging
from datetime import datetime
from typing import TypedDict

import psycopg2
import psycopg2.extras

TABELA_CONTROLE = "controle_historico"


class Candidato(TypedDict):
    parlamentar_id: str
    status: str


def _tabela_existe(cursor, schema: str, tabela: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
        )
        """,
        (schema, tabela),
    )
    return bool(cursor.fetchone()[0])


def _ids_do_historico(cursor, schema: str, tabela: str) -> set[int]:
    """IDs já presentes na tabela de histórico — só para o bootstrap inicial,
    para não perder o rastro de quem já tinha histórico extraído antes deste
    controle existir."""
    if not _tabela_existe(cursor, schema, tabela):
        return set()
    cursor.execute(f"""
        SELECT DISTINCT CAST(parlamentar_id::text AS BIGINT)
          FROM {schema}.{tabela}
         WHERE parlamentar_id IS NOT NULL
           AND parlamentar_id::text ~ '^[0-9]+$'
        """)
    return {int(row[0]) for row in cursor.fetchall()}


def preparar_candidatos(
    conn_str: str,
    schema: str,
    tabela_historico: str,
    ids_atuais: list[int],
) -> list[Candidato]:
    """Sincroniza a tabela de controle e devolve quem precisa de nova extração.

    Elegível: status ATIVO cujo último histórico tem mais de 7 dias (ou nunca
    foi extraído), ou status PENDENTE_FECHAMENTO (saiu do mandato desde a
    última execução — processado uma última vez antes de virar INATIVO).
    """
    create_sql = f"""
        CREATE SCHEMA IF NOT EXISTS {schema};
        CREATE TABLE IF NOT EXISTS {schema}.{TABELA_CONTROLE} (
            parlamentar_id BIGINT PRIMARY KEY,
            status TEXT NOT NULL,
            first_seen_at TIMESTAMP NOT NULL,
            last_seen_at TIMESTAMP NOT NULL,
            last_historico_at TIMESTAMP NULL,
            updated_at TIMESTAMP NOT NULL
        );
    """
    now = datetime.now()
    ids_atuais_set = {int(i) for i in ids_atuais}

    conn = psycopg2.connect(conn_str)
    try:
        with conn.cursor() as cursor:
            cursor.execute(create_sql)

            cursor.execute(f"SELECT COUNT(*) FROM {schema}.{TABELA_CONTROLE}")
            vazio = cursor.fetchone()[0] == 0

            if vazio:
                universo = (
                    _ids_do_historico(cursor, schema, tabela_historico) | ids_atuais_set
                )
                if universo:
                    valores = [
                        (
                            pid,
                            "ATIVO" if pid in ids_atuais_set else "INATIVO",
                            now,
                            now,
                            now,
                        )
                        for pid in universo
                    ]
                    psycopg2.extras.execute_values(
                        cursor,
                        f"""
                        INSERT INTO {schema}.{TABELA_CONTROLE}
                            (parlamentar_id, status, first_seen_at, last_seen_at,
                             updated_at)
                        VALUES %s
                        ON CONFLICT (parlamentar_id) DO NOTHING
                        """,
                        valores,
                    )
                    logging.info(
                        "[parlamentares_controle] %s: bootstrap com universo=%s, "
                        "atuais=%s",
                        schema,
                        len(universo),
                        len(ids_atuais_set),
                    )

            if ids_atuais_set:
                valores = [(pid, "ATIVO", now, now, now) for pid in ids_atuais_set]
                psycopg2.extras.execute_values(
                    cursor,
                    f"""
                    INSERT INTO {schema}.{TABELA_CONTROLE}
                        (parlamentar_id, status, first_seen_at, last_seen_at,
                         updated_at)
                    VALUES %s
                    ON CONFLICT (parlamentar_id) DO UPDATE SET
                        status = 'ATIVO',
                        last_seen_at = EXCLUDED.last_seen_at,
                        updated_at = EXCLUDED.updated_at
                    """,
                    valores,
                )
                cursor.execute(
                    f"""
                    UPDATE {schema}.{TABELA_CONTROLE}
                       SET status = 'PENDENTE_FECHAMENTO', updated_at = %s
                     WHERE status = 'ATIVO'
                       AND parlamentar_id NOT IN %s
                    """,
                    (now, tuple(ids_atuais_set)),
                )
            else:
                logging.warning(
                    "[parlamentares_controle] %s: snapshot de atuais vazio; "
                    "fechamento ignorado nesta execução.",
                    schema,
                )

            cursor.execute(f"""
                SELECT parlamentar_id, status
                  FROM {schema}.{TABELA_CONTROLE}
                 WHERE (status = 'ATIVO'
                        AND (last_historico_at IS NULL
                             OR last_historico_at <= NOW() - INTERVAL '7 days'))
                    OR status = 'PENDENTE_FECHAMENTO'
                 ORDER BY
                     CASE WHEN status = 'PENDENTE_FECHAMENTO' THEN 0 ELSE 1 END,
                     COALESCE(last_historico_at, TIMESTAMP '1900-01-01') ASC,
                     parlamentar_id ASC
                """)
            candidatos: list[Candidato] = [
                {"parlamentar_id": str(row[0]), "status": row[1]}
                for row in cursor.fetchall()
            ]
        conn.commit()
    finally:
        conn.close()

    logging.info(
        "[parlamentares_controle] %s: %s candidato(s) elegível(eis) para histórico.",
        schema,
        len(candidatos),
    )
    return candidatos


def limpar_historico_existente(
    conn_str: str,
    schema: str,
    tabela_historico: str,
    parlamentar_id: str,
) -> None:
    """Remove o histórico já gravado de um parlamentar antes do lote novo.

    Sem isso, reprocessar alguém ATIVO (regra dos 7 dias) soma ao histórico
    já existente em vez de substituí-lo — cada evento apareceria duplicado a
    cada nova extração. Portado de data-application-mir
    (parlamentares_controle_historico_dag.py, ``_clean_existing_historico``).

    ``parlamentar_id`` é comparado como texto de propósito: a tabela de
    histórico é gravada por ``write_raw`` na zona raw, onde toda coluna é
    TEXT — um ``WHERE`` com o id como inteiro nunca encontraria a linha
    (bug real que o repositório antigo teve e corrigiu, commit
    "converte parlamentar_id para text antes do DELETE").
    """
    if not _tabela_existe_conectando(conn_str, schema, tabela_historico):
        return

    conn = psycopg2.connect(conn_str)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"DELETE FROM {schema}.{tabela_historico} WHERE parlamentar_id = %s",
                (str(parlamentar_id),),
            )
        conn.commit()
    finally:
        conn.close()


def _tabela_existe_conectando(conn_str: str, schema: str, tabela: str) -> bool:
    conn = psycopg2.connect(conn_str)
    try:
        with conn.cursor() as cursor:
            return _tabela_existe(cursor, schema, tabela)
    finally:
        conn.close()


def fechar_apos_extracao(
    conn_str: str,
    schema: str,
    resultados: list[dict],
) -> None:
    """Atualiza status/last_historico_at de quem teve o histórico extraído.

    ``resultados`` é uma lista de dicts com ``parlamentar_id``,
    ``status_anterior`` e ``sucesso``: quem falhou mantém o status (tenta de
    novo na próxima execução); quem tinha status PENDENTE_FECHAMENTO e teve
    sucesso fecha definitivamente como INATIVO.
    """
    now = datetime.now()
    atualizacoes = [
        (
            "INATIVO" if r["status_anterior"] == "PENDENTE_FECHAMENTO" else "ATIVO",
            now,
            now,
            int(r["parlamentar_id"]),
        )
        for r in resultados
        if r["sucesso"]
    ]
    if not atualizacoes:
        return

    conn = psycopg2.connect(conn_str)
    try:
        with conn.cursor() as cursor:
            psycopg2.extras.execute_batch(
                cursor,
                f"""
                UPDATE {schema}.{TABELA_CONTROLE}
                   SET status = %s, last_historico_at = %s, updated_at = %s
                 WHERE parlamentar_id = %s
                """,
                atualizacoes,
            )
        conn.commit()
    finally:
        conn.close()
