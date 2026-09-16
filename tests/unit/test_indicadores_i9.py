"""Testes do indicador I9 — Municípios Atendidos, Convênios/Fomentos (ADR-0022).

Dados sintéticos, não regressão contra a BI (removida — ver git log). O
cadastro ``TOTAL_MUNICIPIOS_POR_UF`` continua vindo do IBGE (ver docstring do
módulo para a checagem cruzada) — só o insumo de teste deixou de ser o CSV
real.
"""

import pytest

from indicadores.i9_municipios_atendidos import (
    ROTULO_NAO_INFORMADO,
    TOTAL_MUNICIPIOS_BRASIL,
    TOTAL_MUNICIPIOS_POR_UF,
    calcular_cobertura_nacional,
    calcular_cobertura_uf,
    calcular_i9,
)

pytestmark = pytest.mark.unit


class TestCadastroIbge:
    def test_soma_dos_26_estados_bate_com_o_total_nacional(self) -> None:
        """Critério de aceite documentado no módulo: os 26 ESTADOS somam 5.570.

        O DF entra à parte (não é estado, é 1 unidade equivalente a
        município) — por isso o dicionário inteiro (27 chaves) soma 5.571,
        e é a soma sem o DF que precisa bater com TOTAL_MUNICIPIOS_BRASIL.
        """
        soma_sem_df = sum(
            total for uf, total in TOTAL_MUNICIPIOS_POR_UF.items() if uf != "DF"
        )
        assert soma_sem_df == TOTAL_MUNICIPIOS_BRASIL

    def test_distrito_federal_conta_como_um_municipio(self) -> None:
        """Brasília como unidade estatística equivalente, não zero."""
        assert TOTAL_MUNICIPIOS_POR_UF["DF"] == 1


class TestCoberturaNacional:
    def test_exclui_nao_informado_da_contagem(self) -> None:
        linhas = [
            {"municipio_execucao": "São Paulo", "n_instrumentos": 2},
            {"municipio_execucao": ROTULO_NAO_INFORMADO, "n_instrumentos": 1},
        ]
        cobertura = calcular_cobertura_nacional(linhas)[0]
        assert cobertura["municipios_atendidos"] == 1
        assert cobertura["n_instrumentos"] == 2

    def test_cobertura_pct_e_proporcional_ao_total_nacional(self) -> None:
        linhas = [{"municipio_execucao": "São Paulo", "n_instrumentos": 1}]
        cobertura = calcular_cobertura_nacional(linhas)[0]
        esperado = round(1 / TOTAL_MUNICIPIOS_BRASIL * 100, 2)
        assert cobertura["cobertura_pct"] == esperado


class TestCoberturaUf:
    def test_cobertura_pct_usa_o_total_de_municipios_da_uf(self) -> None:
        linhas = [
            {"uf_execucao": "AP", "municipio_execucao": "Macapá", "n_instrumentos": 1}
        ]
        cobertura = calcular_cobertura_uf(linhas)[0]
        assert cobertura["total_municipios_uf"] == TOTAL_MUNICIPIOS_POR_UF["AP"]
        esperado = round(1 / TOTAL_MUNICIPIOS_POR_UF["AP"] * 100, 2)
        assert cobertura["cobertura_pct"] == esperado

    def test_uf_desconhecida_nao_quebra_e_deixa_cobertura_vazia(self) -> None:
        linhas = [
            {"uf_execucao": "ZZ", "municipio_execucao": "Cidade X", "n_instrumentos": 1}
        ]
        cobertura = calcular_cobertura_uf(linhas)[0]
        assert cobertura["total_municipios_uf"] == 0
        assert cobertura["cobertura_pct"] == ""

    def test_ordenado_por_municipios_atendidos_decrescente(self) -> None:
        linhas = [
            {"uf_execucao": "AC", "municipio_execucao": "M1", "n_instrumentos": 1},
            {"uf_execucao": "SP", "municipio_execucao": "M2", "n_instrumentos": 1},
            {"uf_execucao": "SP", "municipio_execucao": "M3", "n_instrumentos": 1},
        ]
        cobertura = calcular_cobertura_uf(linhas)
        assert cobertura[0]["uf"] == "SP"
        assert cobertura[0]["municipios_atendidos"] == 2


class TestCalcularI9:
    def test_orquestracao_produz_as_duas_saidas(self) -> None:
        linhas = [
            {"uf_execucao": "SP", "municipio_execucao": "São Paulo", "n_instrumentos": 1}
        ]
        saidas = calcular_i9(linhas)
        assert set(saidas) == {
            "i9_convenio_cobertura_nacional",
            "i9_convenio_cobertura_uf",
        }
