"""Testes do indicador I2 — Concentração Institucional dos Executores (ADR-0022).

Dados sintéticos, não regressão contra a BI (removida — ver git log). Cada
teste cobre uma das decisões metodológicas documentadas no módulo, não os
números absolutos de nenhuma execução real.
"""

import pytest

from indicadores.i2_concentracao_executores import (
    _hhi_por_grupo,
    _tipo_institucional,
    agregar_convenio_por_executor,
    agregar_ted_por_executor,
    calcular_i2,
    calcular_ted_localizacao_institucional,
)

pytestmark = pytest.mark.unit


class TestTipoInstitucional:
    def test_universidade_federal_por_correspondencia_exata(self) -> None:
        """Decisão 3: correspondência exata, não prefixo.

        UNIRIO está no conjunto (é universidade federal de verdade, mesmo
        sem começar por "UF") — é UNIRIO que o classificador por prefixo
        (`sigla.startswith("UF")`) erraria, não o exato.
        """
        assert _tipo_institucional("UFPR") == "Universidade Federal"
        assert _tipo_institucional("UNIRIO") == "Universidade Federal"
        # Prefixo "UF" sem estar cadastrada: não vira Universidade Federal.
        assert _tipo_institucional("UFXPTO") == "Outro"

    def test_instituto_federal(self) -> None:
        assert _tipo_institucional("IFBA") == "Instituto Federal"

    def test_sigla_desconhecida_vira_outro(self) -> None:
        assert _tipo_institucional("XYZ") == "Outro"


class TestLocalizacaoInstitucionalTed:
    def test_uf_sede_vem_do_dicionario_por_sigla(self) -> None:
        """Decisão 1: UF é a sede do executor, não o território atendido."""
        teds = [{"sigla_executor": "UFBA", "nome_executor": "UFBA"}]
        loc = calcular_ted_localizacao_institucional(teds)
        assert loc[0]["uf_sede"] == "BA"

    def test_sigla_nao_mapeada_vira_nao_mapeado(self) -> None:
        teds = [{"sigla_executor": "ZZZ", "nome_executor": "Desconhecido"}]
        loc = calcular_ted_localizacao_institucional(teds)
        assert loc[0]["uf_sede"] == "NAO_MAPEADO"

    def test_sigla_vazia_corrigida_via_nome_do_executor(self) -> None:
        """Decisão 4: correção por nome quando a sigla vem vazia."""
        teds = [{"sigla_executor": "", "nome_executor": "Universidade Federal do Parana"}]
        loc = calcular_ted_localizacao_institucional(teds)
        assert loc[0]["sigla_executor"] == "UFPR"

    def test_sigla_vazia_sem_correcao_conhecida_vira_sem_sigla(self) -> None:
        teds = [{"sigla_executor": "", "nome_executor": "Orgao Qualquer"}]
        loc = calcular_ted_localizacao_institucional(teds)
        assert loc[0]["sigla_executor"] == "SEM_SIGLA"


class TestHhi:
    def test_dois_executores_iguais_da_hhi_cinco_mil(self) -> None:
        """HHI = soma dos shares² — dois executores com 50% cada: 50² + 50² = 5000."""
        linhas = [{"chave": "A", "valor": 50.0}, {"chave": "B", "valor": 50.0}]
        assert _hhi_por_grupo(linhas, "chave", "valor") == 5000.0

    def test_monopolio_da_hhi_dez_mil(self) -> None:
        linhas = [{"chave": "A", "valor": 100.0}]
        assert _hhi_por_grupo(linhas, "chave", "valor") == 10000.0

    def test_total_zero_nao_divide_por_zero(self) -> None:
        linhas = [{"chave": "A", "valor": 0.0}]
        assert _hhi_por_grupo(linhas, "chave", "valor") == 0.0


class TestAgregarTedPorExecutor:
    def test_hhi_usa_vl_firmado_nao_empenhado(self) -> None:
        """Decisão 2: TED usa vl_firmado (maioria tem empenho zero)."""
        loc = [
            {
                "sigla_executor": "A",
                "nome_executor": "A",
                "uf_sede": "DF",
                "tipo_institucional": "Outro",
                "vl_firmado": 100.0,
            }
        ]
        agregado = agregar_ted_por_executor(loc)
        assert agregado[0]["vl_firmado"] == 100.0
        assert agregado[0]["share_pct"] == 100.0


class TestAgregarConvenioPorExecutor:
    def test_reporta_n_ufs_distintas_em_vez_de_uf_unica(self) -> None:
        """Decisão 6: um convenente pode executar em mais de uma UF."""
        loc = [
            {
                "convenente": "OSC X",
                "categoria_convenente": "OSC",
                "uf_execucao": "SP",
                "empenhado_liquido": 10.0,
            },
            {
                "convenente": "OSC X",
                "categoria_convenente": "OSC",
                "uf_execucao": "RJ",
                "empenhado_liquido": 20.0,
            },
        ]
        agregado = agregar_convenio_por_executor(loc)
        assert agregado[0]["n_ufs_distintas"] == 2
        assert agregado[0]["empenhado_liquido"] == 30.0


class TestCalcularI2:
    def test_orquestracao_produz_as_seis_saidas(self) -> None:
        teds_i1 = [
            {
                "id_plano_acao": "1",
                "sigla_executor": "UNB",
                "nome_executor": "UNB",
                "programa_governo": "",
                "origem": "orcamento_regular",
                "ano": "2024",
                "vl_firmado": 100.0,
            }
        ]
        convenios_i1 = [
            {
                "nr_convenio": "1",
                "convenente": "OSC X",
                "categoria_convenente": "OSC",
                "uf_execucao": "SP",
                "municipio_execucao": "São Paulo",
                "instrumento": "TERMO DE FOMENTO",
                "origem": "orcamento_regular",
                "ano": "2024",
                "empenhado_liquido": 50.0,
            }
        ]
        saidas = calcular_i2(teds_i1, convenios_i1)
        assert set(saidas) == {
            "i2_ted_localizacao_institucional",
            "i2_executores_concentracao",
            "i2_resumo",
            "i2_convenio_localizacao_institucional",
            "i2_convenio_concentracao",
            "i2_resumo_convenio",
        }
        assert saidas["i2_resumo"][0]["n_teds"] == 1
        assert saidas["i2_resumo_convenio"][0]["n_convenentes_distintos"] == 1
