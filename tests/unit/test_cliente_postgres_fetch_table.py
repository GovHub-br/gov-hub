"""Testes de `ClientPostgresDB.fetch_table` e da citação de identificadores.

A citação existe porque os schemas do ADR-0010 começam com dígito
(`003_gld_transferencias`): sem aspas o Postgres nem faz o parse do comando.
Ela precisa, ao mesmo tempo, deixar intactos os nomes que já funcionavam sem
aspas — citar `raw_contratos` como `"raw_contratos"` seria inofensivo, mas
citar um nome com maiúscula deixaria de casar com a tabela que o Postgres
gravou em minúsculo.
"""

from unittest.mock import MagicMock, patch

import pytest

from cliente_postgres import ClientPostgresDB

pytestmark = pytest.mark.unit


def _mock_connect(columns: list[str], rows: list[tuple]) -> MagicMock:
    cursor = MagicMock()
    cursor.description = [(col,) for col in columns]
    cursor.fetchall.return_value = rows
    cursor.__enter__.return_value = cursor

    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


def test_fetch_table_retorna_lista_de_dicts_com_nome_das_colunas() -> None:
    conn = _mock_connect(["id_plano_acao", "empenhado"], [(1, 10.5), (2, None)])

    with patch("cliente_postgres.psycopg2.connect", return_value=conn):
        linhas = ClientPostgresDB("dsn").fetch_table(
            "002_slv_transferencias", "planos_acao_ted"
        )

    assert linhas == [
        {"id_plano_acao": 1, "empenhado": 10.5},
        {"id_plano_acao": 2, "empenhado": None},
    ]
    conn.cursor.return_value.execute.assert_called_once_with(
        'SELECT * FROM "002_slv_transferencias".planos_acao_ted'
    )
    conn.close.assert_called_once()


def test_fetch_table_tabela_vazia_retorna_lista_vazia() -> None:
    conn = _mock_connect(["id"], [])

    with patch("cliente_postgres.psycopg2.connect", return_value=conn):
        assert ClientPostgresDB("dsn").fetch_table("siconv", "raw_convenio") == []


class TestCitacaoDeIdentificadores:
    @pytest.mark.parametrize(
        "nome", ["siconv", "raw_convenio", "_interno", "tabela_2026"]
    )
    def test_nome_ja_valido_sem_aspas_fica_intacto(self, nome: str) -> None:
        """Não citar o que já funcionava preserva as tabelas existentes."""
        assert ClientPostgresDB._ident(nome) == nome

    @pytest.mark.parametrize(
        "nome, esperado",
        [
            ("003_gld_indicadores", '"003_gld_indicadores"'),
            ("002_slv_transferencias", '"002_slv_transferencias"'),
            ("Tabela", '"Tabela"'),
        ],
    )
    def test_nome_que_exige_aspas_e_citado(self, nome: str, esperado: str) -> None:
        assert ClientPostgresDB._ident(nome) == esperado

    @pytest.mark.parametrize("nome", ["bad;drop", "t--x", 'a"b', ""])
    def test_nome_hostil_vira_identificador_inerte(self, nome: str) -> None:
        """Citado, o nome vira um identificador que não existe — não SQL.

        É o que substitui a validação por regex: em vez de recusar o nome,
        a citação o neutraliza, sem recusar junto os schemas do ADR-0010.
        """
        citado = ClientPostgresDB._ident(nome)
        assert citado.startswith('"') and citado.endswith('"')
        # Uma aspa interna é escapada dobrando, então nunca fecha o
        # identificador no meio e deixa o resto virar comando.
        assert citado[1:-1].replace('""', "").count('"') == 0
