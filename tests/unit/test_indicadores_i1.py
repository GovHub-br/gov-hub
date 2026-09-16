"""Testes do indicador I1 — Valor Executado por Instrumento (ADR-0022).

Dados sintéticos, não regressão contra a BI (removida — ver git log). Cada
teste cobre uma das decisões metodológicas documentadas no módulo, não os
números absolutos de nenhuma execução real.
"""

import pytest

from indicadores.i1_valor_executado import (
    agregar_convenios_por_municipio,
    agregar_convenios_por_uf,
    agregar_teds_por_executor,
    calcular_carteira,
    calcular_convenios,
    calcular_i1,
    calcular_teds,
    classificar_etapa_cadeia,
)

pytestmark = pytest.mark.unit


class TestCalcularTeds:
    def test_exclui_situacao_rejeitado(self) -> None:
        """Decisão 4: todos os planos exceto REJEITADO."""
        planos = [
            {"id_plano_acao": "1", "tx_situacao_plano_acao": "APROVADO"},
            {"id_plano_acao": "2", "tx_situacao_plano_acao": "REJEITADO"},
        ]
        teds = calcular_teds(planos, resumo=[], instrumentos_emendas=[])
        assert [t["id_plano_acao"] for t in teds] == ["1"]

    def test_empenhado_liquido_soma_varias_linhas_do_mesmo_plano(self) -> None:
        """Decisão 5: várias linhas do resumo por plano se somam, não deduplicam."""
        planos = [{"id_plano_acao": "1", "tx_situacao_plano_acao": "APROVADO"}]
        resumo = [
            {"plano_acao": "1", "empenhado": 100.0, "empenho_anulado": 0.0},
            {"plano_acao": "1", "empenhado": 50.0, "empenho_anulado": 10.0},
        ]
        teds = calcular_teds(planos, resumo, instrumentos_emendas=[])
        assert teds[0]["empenhado_bruto"] == 150.0
        assert teds[0]["empenho_anulado"] == 10.0
        assert teds[0]["empenhado_liquido"] == 140.0

    def test_origem_emenda_quando_sq_instrumento_esta_em_instrumentos_emendas(
        self,
    ) -> None:
        """Decisão 6: origem marcada no grão de instrumento, não de plano."""
        planos = [
            {
                "id_plano_acao": "1",
                "sq_instrumento": "S1",
                "tx_situacao_plano_acao": "APROVADO",
            }
        ]
        instrumentos_emendas = [{"tipo_instrumento": "TED", "numero_instrumento": "S1"}]
        teds = calcular_teds(planos, resumo=[], instrumentos_emendas=instrumentos_emendas)
        assert teds[0]["origem"] == "emenda"

    def test_forma_execucao_2n_junta_flags_ativas(self) -> None:
        planos = [
            {
                "id_plano_acao": "1",
                "tx_situacao_plano_acao": "APROVADO",
                "in_forma_execucao_direta": "SIM",
                "in_forma_execucao_descentralizada": "SIM",
                "in_forma_execucao_particulares": "NAO",
            }
        ]
        teds = calcular_teds(planos, resumo=[], instrumentos_emendas=[])
        assert teds[0]["forma_execucao_2n"] == "direta; descentralizada"


class TestClassificarEtapaCadeia:
    """Definição B: universo é descentralizada OU aparece em nc_plano_acao."""

    def test_fora_do_universo_nao_entra_no_resultado(self) -> None:
        planos = [{"id_plano_acao": "1", "in_forma_execucao_descentralizada": "NAO"}]
        etapas = classificar_etapa_cadeia(planos, pf=[], nc=[], ne=[])
        assert etapas == {}

    @pytest.mark.parametrize(
        "tem_pf, tem_nc, tem_ne, esperado",
        [
            (True, True, True, "S4_cadeia_plena"),
            (True, True, False, "S3_ate_NC"),
            (True, False, False, "S2_ate_PF"),
            (False, True, False, "S3_NC_sem_PF"),
            (False, False, False, "S1_so_plano"),
        ],
    )
    def test_estagio_no_funil(
        self, tem_pf: bool, tem_nc: bool, tem_ne: bool, esperado: str
    ) -> None:
        planos = [{"id_plano_acao": "1", "in_forma_execucao_descentralizada": "SIM"}]
        pf = [{"id_plano_acao": "1"}] if tem_pf else []
        nc = [{"id_plano_acao": "1"}] if tem_nc else []
        ne = [{"plano_acao": "1"}] if tem_ne else []
        etapas = classificar_etapa_cadeia(planos, pf, nc, ne)
        assert etapas["1"] == esperado


class TestAgregarTedsPorExecutor:
    def test_share_pct_proporcional_ao_empenhado_liquido(self) -> None:
        teds = [
            {
                "sigla_executor": "A",
                "nome_executor": "Exec A",
                "vl_firmado": 100.0,
                "empenhado_liquido": 75.0,
                "pago": 0.0,
            },
            {
                "sigla_executor": "B",
                "nome_executor": "Exec B",
                "vl_firmado": 100.0,
                "empenhado_liquido": 25.0,
                "pago": 0.0,
            },
        ]
        agregado = agregar_teds_por_executor(teds)
        por_sigla = {a["sigla_executor"]: a for a in agregado}
        assert por_sigla["A"]["share_pct"] == 75.0
        assert por_sigla["B"]["share_pct"] == 25.0

    def test_n_sem_empenho_conta_empenhado_liquido_zero(self) -> None:
        teds = [
            {
                "sigla_executor": "A",
                "nome_executor": "Exec A",
                "vl_firmado": 10.0,
                "empenhado_liquido": 0.0,
                "pago": 0.0,
            }
        ]
        assert agregar_teds_por_executor(teds)[0]["n_sem_empenho"] == 1


class TestCalcularConvenios:
    def test_exclui_convenio_anterior_ao_corte(self) -> None:
        """Decisão 3: universo dos convênios é ano >= 2023."""
        linhas = [
            {"nr_convenio": "1", "data_assinatura": "2022-05-01"},
            {"nr_convenio": "2", "data_assinatura": "2023-05-01"},
        ]
        convenios = calcular_convenios(linhas)
        assert [c["nr_convenio"] for c in convenios] == ["2"]

    def test_usa_inicio_vigencia_quando_falta_data_assinatura(self) -> None:
        linhas = [{"nr_convenio": "1", "inicio_vigencia": "2024-01-01"}]
        convenios = calcular_convenios(linhas)
        assert convenios[0]["ano"] == 2024
        assert convenios[0]["ano_fonte"] == "inicio_vigencia"

    def test_exclui_situacao_cancelada(self) -> None:
        linhas = [
            {
                "nr_convenio": "1",
                "data_assinatura": "2024-01-01",
                "situacao_atual": "Cancelado",
            }
        ]
        assert calcular_convenios(linhas) == []

    def test_empenhado_zero_permanece_marcado_sem_empenho(self) -> None:
        """Decisão 3: empenhado zero fica na contagem, não é excluído."""
        linhas = [
            {
                "nr_convenio": "1",
                "data_assinatura": "2024-01-01",
                "valor_empenhado": 0,
            }
        ]
        convenios = calcular_convenios(linhas)
        assert len(convenios) == 1
        assert convenios[0]["sem_empenho"] == 1

    def test_origem_emenda_quando_parlamentares_preenchido(self) -> None:
        linhas = [
            {
                "nr_convenio": "1",
                "data_assinatura": "2024-01-01",
                "parlamentares": "Dep. Fulano",
            }
        ]
        assert calcular_convenios(linhas)[0]["origem"] == "emenda"


class TestAgregacaoTerritorial:
    def test_convenio_sem_uf_vira_nao_informado(self) -> None:
        convenios = [
            {
                "uf_execucao": "",
                "municipio_execucao": "",
                "empenhado_liquido": 10.0,
                "sem_empenho": 0,
                "origem": "orcamento_regular",
                "vl_firmado": 10.0,
                "pago": 0.0,
            }
        ]
        agregado = agregar_convenios_por_uf(convenios)
        assert agregado[0]["uf_execucao"] == "NAO_INFORMADO"

    def test_municipio_e_uf_desambiguam_homonimos(self) -> None:
        """Docstring de _agregar_territorio: município e UF saem separados."""
        convenios = [
            {
                "uf_execucao": "SP",
                "municipio_execucao": "Bom Jesus",
                "empenhado_liquido": 10.0,
                "sem_empenho": 0,
                "origem": "orcamento_regular",
                "vl_firmado": 10.0,
                "pago": 0.0,
            },
            {
                "uf_execucao": "PI",
                "municipio_execucao": "Bom Jesus",
                "empenhado_liquido": 20.0,
                "sem_empenho": 0,
                "origem": "orcamento_regular",
                "vl_firmado": 20.0,
                "pago": 0.0,
            },
        ]
        agregado = agregar_convenios_por_municipio(convenios)
        assert len(agregado) == 2
        assert {(a["municipio_execucao"], a["uf_execucao"]) for a in agregado} == {
            ("Bom Jesus", "SP"),
            ("Bom Jesus", "PI"),
        }


class TestCalcularCarteira:
    def test_agrupa_teds_e_convenios_por_instrumento_e_origem(self) -> None:
        teds = [
            {
                "instrumento": "TED",
                "origem": "orcamento_regular",
                "vl_firmado": 10.0,
                "empenhado_liquido": 10.0,
                "pago": 0.0,
            }
        ]
        convenios = [
            {
                "instrumento": "TERMO DE FOMENTO",
                "origem": "emenda",
                "vl_firmado": 5.0,
                "empenhado_liquido": 5.0,
                "pago": 0.0,
            }
        ]
        carteira = calcular_carteira(teds, convenios)
        assert {(c["instrumento"], c["origem"]) for c in carteira} == {
            ("TED", "orcamento_regular"),
            ("TERMO DE FOMENTO", "emenda"),
        }


class TestCalcularI1:
    def test_orquestracao_produz_as_seis_saidas(self) -> None:
        planos = [
            {
                "id_plano_acao": "1",
                "sq_instrumento": "S1",
                "tx_situacao_plano_acao": "APROVADO",
                "sigla_unidade_descentralizada": "UNB",
                "unidade_descentralizada": "Universidade de Brasília",
                "aa_ano_plano_acao": "2024",
                "vl_total_plano_acao": 100.0,
            }
        ]
        gold_convenios = [
            {
                "nr_convenio": "9",
                "data_assinatura": "2024-01-01",
                "modalidade_instrumento": "TERMO DE FOMENTO",
                "nome_convenente": "Associação X",
                "categoria_convenente": "OSC",
                "uf_execucao": "SP",
                "municipio_execucao": "São Paulo",
                "valor_empenhado": 50.0,
            }
        ]

        saidas = calcular_i1(
            planos=planos,
            resumo=[],
            instrumentos_emendas=[],
            gold_convenios=gold_convenios,
            pf=[],
            nc=[],
            ne=[],
        )

        assert set(saidas) == {
            "i1_ted_por_instrumento",
            "i1_ted_por_executor",
            "i1_convenios_por_instrumento",
            "i1_convenios_por_uf",
            "i1_convenios_por_municipio",
            "i1_valor_por_instrumento",
        }
        assert len(saidas["i1_ted_por_instrumento"]) == 1
        assert len(saidas["i1_convenios_por_instrumento"]) == 1
