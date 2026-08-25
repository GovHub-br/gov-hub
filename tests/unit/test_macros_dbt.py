"""Testes do macro dbt `chave_conformada` (ADR-0017).

O macro é Jinja puro que monta uma expressão SQL, então dá para exercitá-lo sem
dbt e sem banco: basta emular o `return()` do dbt, que não existe no Jinja
padrão — no dbt ele interrompe o macro levantando uma exceção com o valor.
"""

from __future__ import annotations

from pathlib import Path

import jinja2
import pytest

MACRO = (
    Path(__file__).resolve().parents[2]
    / "airflow"
    / "dags"
    / "dbt"
    / "gov_bricks"
    / "macros"
    / "chave_conformada.sql"
)

CHAVES = {
    "co_uasg": {"normalizacao": "digitos", "tamanho": 6, "classificacao": "publico"},
    "co_natureza_despesa": {
        "normalizacao": "digitos",
        "tamanho": 8,
        "classificacao": "publico",
    },
    "nu_ni": {"normalizacao": "digitos", "tamanho": None, "classificacao": "publico"},
    "no_orgao": {"normalizacao": "texto", "tamanho": None, "classificacao": "publico"},
}


class _Retorno(Exception):
    """Equivalente ao MacroReturn do dbt: carrega o valor do `return()`."""

    def __init__(self, valor: str) -> None:
        self.valor = valor


class _ErroCompilacao(Exception):
    pass


class _PacoteGovBricks:
    """O namespace de pacote que o dbt injeta no contexto de um modelo.

    A chamada dentro do macro é qualificada (`gov_bricks.chaves_conformadas()`)
    porque quem o executa é um modelo de outro pacote — emular isso aqui é o que
    mantém o teste fiel ao que o dbt faz de verdade.
    """

    @staticmethod
    def chaves_conformadas() -> dict:
        return CHAVES


class _Excecoes:
    @staticmethod
    def raise_compiler_error(mensagem: str) -> None:
        raise _ErroCompilacao(mensagem)


def _render(chave: str, coluna: str) -> str:
    """Renderiza o macro e devolve a expressão SQL que ele produz."""

    def _return(valor: str) -> None:
        raise _Retorno(valor)

    ambiente = jinja2.Environment()
    modulo = jinja2.Template.from_code(
        ambiente,
        ambiente.compile(MACRO.read_text(encoding="utf-8")),
        {
            "gov_bricks": _PacoteGovBricks,
            "exceptions": _Excecoes,
            "return": _return,
        },
    ).make_module()

    # getattr porque o macro só existe no módulo depois que o Jinja compila o
    # template — não há atributo estático para a análise de tipo enxergar.
    macro = getattr(modulo, "chave_conformada")
    try:
        macro(chave, coluna)
    except _Retorno as retorno:
        return str(retorno.valor)
    raise AssertionError("o macro não chamou return()")


def test_normalizacao_digitos_remove_nao_digitos() -> None:
    sql = _render("co_uasg", "codigounidadegestora")
    assert (
        "regexp_replace(cast(codigounidadegestora as varchar), '[^0-9]', '', 'g')" in sql
    )
    # String vazia precisa virar NULL, não '000000': uma chave vazia preenchida
    # com zeros casaria com outra chave vazia em um join.
    assert "nullif(" in sql


def test_chave_com_tamanho_completa_com_zeros_a_esquerda() -> None:
    assert "lpad(" in _render("co_uasg", "codigounidadegestora")


def test_chave_com_tamanho_nunca_trunca_valor_mais_longo() -> None:
    """Regressão: lpad(x, N) TRUNCA quando x é mais longo que N.

    co_natureza_despesa declara 8 dígitos e o compras_gov entrega 8, mas nada
    impede outra origem de trazer mais — e truncar produziria um join
    silenciosamente errado em vez de simplesmente não casar.
    """
    sql = _render("co_natureza_despesa", "codigonaturezadespesa")
    assert "greatest(length(" in sql, "o alvo do lpad precisa respeitar o valor"
    assert "lpad(" in sql
    # O alvo é o maior entre o tamanho declarado e o comprimento real.
    assert ", 8)" in sql


def test_chave_sem_tamanho_nao_recebe_lpad() -> None:
    sql = _render("nu_ni", "nifornecedor")
    assert "lpad(" not in sql
    assert "regexp_replace" in sql


def test_normalizacao_texto_normaliza_caixa_e_espacos() -> None:
    sql = _render("no_orgao", "nomeorgao")
    assert "upper(trim(" in sql
    assert "lpad(" not in sql


def test_chave_desconhecida_falha_na_compilacao() -> None:
    with pytest.raises(_ErroCompilacao, match="Chave conformada desconhecida"):
        _render("co_inexistente", "coluna")
