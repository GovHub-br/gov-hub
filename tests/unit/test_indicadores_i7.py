"""Testes do indicador I7 — Completude e Qualidade dos Dados (ADR-0022).

Dados sintéticos — o próprio módulo já documenta que os números não são
comparáveis por regressão a nenhum CSV real (ver "AVISO DE VALIDAÇÃO" em
``i7_completude.py``). Cada teste cobre uma das faixas/heurísticas da
fórmula documentada no módulo.
"""

import pytest

from indicadores.i7_completude import (
    _esta_ausente,
    completude_tabela,
    consolidar_i7,
)

pytestmark = pytest.mark.unit


class TestEstaAusente:
    @pytest.mark.parametrize(
        "valor", [None, "", "   ", "SEM INFORMACAO", "sem informação", "-8", "-9"]
    )
    def test_marcadores_de_ausencia(self, valor) -> None:
        assert _esta_ausente(valor) is True

    @pytest.mark.parametrize("valor", [0, "0", "NAO", "SIM", "x"])
    def test_zero_e_nao_sim_sao_preenchidos(self, valor) -> None:
        """DEFINIÇÃO do módulo: zeros e NAO/SIM são PREENCHIDOS, não ausentes."""
        assert _esta_ausente(valor) is False


class TestCompletudeTabela:
    def test_tabela_vazia_nao_gera_linhas(self) -> None:
        cols, resumo = completude_tabela("TEDs", "tab_vazia", [])
        assert cols == []
        assert resumo is None

    def test_coluna_totalmente_preenchida_fica_na_faixa_ok(self) -> None:
        linhas = [{"a": "x"}, {"a": "y"}]
        cols, _ = completude_tabela("TEDs", "tab", linhas)
        assert cols[0]["pct_ausente"] == 0.0
        assert cols[0]["faixa"] == "OK"
        assert cols[0]["tipo_ausencia_sugerido"] == "completo"

    def test_faixas_conforme_a_formula_do_docstring(self) -> None:
        """OK <10% ausente, ATENCAO 10-50%, CRITICO >50%."""
        linhas = [
            {"critica": None, "estrutural": None, "ok": "x"},
            {"critica": None, "estrutural": None, "ok": "y"},
            {"critica": "z", "estrutural": None, "ok": "w"},
        ]
        # critica: 2/3 ≈ 66,7% ausente (>50%, CRITICO)
        # estrutural: 3/3 = 100% ausente (CRITICO + estrutural_suspeita)
        # ok: 0% ausente (OK)
        cols, resumo = completude_tabela("TEDs", "tab", linhas)

        por_coluna = {c["coluna"]: c for c in cols}
        assert por_coluna["critica"]["faixa"] == "CRITICO"
        assert por_coluna["critica"]["tipo_ausencia_sugerido"] == "dado_faltante"
        assert por_coluna["estrutural"]["faixa"] == "CRITICO"
        assert por_coluna["estrutural"]["tipo_ausencia_sugerido"] == "estrutural_suspeita"
        assert por_coluna["ok"]["faixa"] == "OK"

        # `resumo` só é None para tabela vazia (coberto acima); aqui há linhas.
        assert resumo is not None
        assert resumo["n_registros"] == 3
        assert resumo["n_colunas"] == 3
        assert resumo["n_colunas_criticas"] == 2  # critica E estrutural passam de 50%
        assert resumo["n_colunas_estruturais_suspeitas"] == 1


class TestConsolidarI7:
    def test_separa_saidas_por_pasta_ted_e_convenios(self) -> None:
        linhas_colunas: list[dict] = []
        linhas_tabelas: list[dict] = []
        for pasta, nome, linhas in [
            ("TEDs", "planos_acao_ted", [{"a": "x"}, {"a": None}]),
            ("Convênios", "convenio", [{"b": "x"}]),
        ]:
            cols, resumo = completude_tabela(pasta, nome, linhas)
            assert resumo is not None  # nenhuma das tabelas deste caso é vazia
            linhas_colunas.extend(cols)
            linhas_tabelas.append(resumo)

        saidas = consolidar_i7(linhas_colunas, linhas_tabelas)

        assert {linha["arquivo"] for linha in saidas["i7_completude_arquivos_ted"]} == {
            "planos_acao_ted"
        }
        assert {
            linha["arquivo"] for linha in saidas["i7_completude_arquivos_convenios"]
        } == {"convenio"}
        assert len(saidas["i7_completude_colunas"]) == 2
        assert len(saidas["i7_completude_arquivos"]) == 2

    def test_colunas_ordenadas_por_pct_ausente_decrescente(self) -> None:
        linhas_colunas = [
            {"pasta": "TEDs", "arquivo": "t", "coluna": "baixo", "pct_ausente": 10.0},
            {"pasta": "TEDs", "arquivo": "t", "coluna": "alto", "pct_ausente": 90.0},
        ]
        saidas = consolidar_i7(linhas_colunas, linhas_tabelas=[])
        colunas_em_ordem = [c["coluna"] for c in saidas["i7_completude_colunas"]]
        assert colunas_em_ordem == ["alto", "baixo"]
