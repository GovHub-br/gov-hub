"""Testes do indicador I3 — Instrumentos com Público-Alvo Racializado (ADR-0022).

Dados sintéticos, não regressão contra a BI (removida — ver git log; o
módulo nunca teve essa regressão mesmo na origem, por falta do texto de
entrada no ambiente de porte — ver "AVISO DE VALIDAÇÃO" no módulo). Cada
teste cobre uma das decisões metodológicas documentadas.
"""

import pytest

from indicadores.i3_publico_alvo import (
    calcular_i3,
    classificar,
    montar_instrumentos_convenio,
    montar_instrumentos_ted,
    normalizar,
)

pytestmark = pytest.mark.unit


class TestNormalizar:
    def test_remove_acentos_e_minusculiza(self) -> None:
        assert normalizar("Ação Indígena") == "acao indigena"

    def test_texto_vazio_ou_none_nao_quebra(self) -> None:
        assert normalizar("") == ""
        # A assinatura promete `str`, mas o corpo trata None (`texto or ""`)
        # de propósito: `classificar` passa `p.get("tx_objeto...", "")` direto,
        # e uma coluna nula no banco chega aqui como None, não "".
        assert normalizar(None) == ""  # ty: ignore[invalid-argument-type]


class TestClassificar:
    @pytest.mark.parametrize(
        "texto, categoria",
        [
            ("atendimento a população negra", "pessoas_negras"),
            ("comunidade quilombola do Vale", "quilombolas"),
            ("povos indígenas do Xingu", "indigenas"),
            ("povos de terreiro e matriz africana", "terreiro"),
            # Decisão 1: categoria real, majoritariamente via a sigla SQPT.
            ("Secretaria de Políticas para Ciganos", "ciganos"),
        ],
    )
    def test_categoria_especifica_detectada_por_palavra_chave(
        self, texto: str, categoria: str
    ) -> None:
        resultado = classificar(texto)
        assert resultado[categoria] == 1
        assert resultado["leitura_estrita"] == 1
        assert resultado["leitura_ampla"] == 1

    def test_racial_generico_sozinho_nao_ativa_leitura_estrita(self) -> None:
        """Decisão 2: estrita exige categoria nomeada; genérico só entra na ampla."""
        resultado = classificar("política de igualdade racial")
        assert resultado["racial_generico"] == 1
        assert resultado["leitura_estrita"] == 0
        assert resultado["leitura_ampla"] == 1

    def test_texto_sem_mencao_racial_zera_as_duas_leituras(self) -> None:
        resultado = classificar("construção de escola municipal")
        assert resultado["leitura_estrita"] == 0
        assert resultado["leitura_ampla"] == 0

    def test_subcategoria_mulheres_negras_nao_altera_leitura_estrita(self) -> None:
        """Decisão 6: subcategoria é informativa, subconjunto de pessoas_negras."""
        resultado = classificar("apoio a mulheres negras empreendedoras")
        assert resultado["mulheres_negras"] == 1
        assert resultado["pessoas_negras"] == 1
        assert resultado["leitura_estrita"] == 1

    def test_junta_varios_textos_antes_de_classificar(self) -> None:
        """classificar(*textos) — objeto e justificativa juntos (TED)."""
        resultado = classificar("projeto educacional", "voltado a quilombolas")
        assert resultado["quilombolas"] == 1


class TestMontarInstrumentosTed:
    def test_exclui_situacao_rejeitado(self) -> None:
        """Decisão 4: mesmo universo do I1 — exclui REJEITADO."""
        planos = [
            {"id_plano_acao": "1", "tx_situacao_plano_acao": "APROVADO"},
            {"id_plano_acao": "2", "tx_situacao_plano_acao": "REJEITADO"},
        ]
        instrumentos = montar_instrumentos_ted(planos, resumo=[], instrumentos_emendas=[])
        assert [i["id_instrumento"] for i in instrumentos] == ["1"]

    def test_trunca_tx_objeto_em_200_caracteres(self) -> None:
        planos = [
            {
                "id_plano_acao": "1",
                "tx_situacao_plano_acao": "APROVADO",
                "tx_objeto_plano_acao": "x" * 300,
            }
        ]
        instrumentos = montar_instrumentos_ted(planos, resumo=[], instrumentos_emendas=[])
        assert len(instrumentos[0]["tx_objeto"]) == 200


class TestMontarInstrumentosConvenio:
    def test_exclui_convenio_anterior_ao_corte(self) -> None:
        """Decisão 4: mesmo corte de ano (>=2023) do I1."""
        linhas = [
            {"nr_convenio": "1", "data_assinatura": "2022-01-01", "objeto": "x"},
            {"nr_convenio": "2", "data_assinatura": "2023-01-01", "objeto": "x"},
        ]
        instrumentos = montar_instrumentos_convenio(linhas)
        assert [i["id_instrumento"] for i in instrumentos] == ["2"]

    def test_programa_governo_vazio_por_nao_estar_disponivel(self) -> None:
        """Decisão 5: convênios não têm programa de governo estruturado."""
        linhas = [{"nr_convenio": "1", "data_assinatura": "2024-01-01", "objeto": "x"}]
        instrumentos = montar_instrumentos_convenio(linhas)
        assert instrumentos[0]["programa_governo"] == ""


class TestCalcularI3:
    def test_orquestracao_produz_as_quatro_saidas(self) -> None:
        planos = [
            {
                "id_plano_acao": "1",
                "tx_situacao_plano_acao": "APROVADO",
                "sq_instrumento": "S1",
                "tx_objeto_plano_acao": "atendimento a comunidades quilombolas",
                "aa_ano_plano_acao": "2024",
            }
        ]
        gold_convenios = [
            {
                "nr_convenio": "9",
                "data_assinatura": "2024-01-01",
                "objeto": "reforma de escola",
                "modalidade_instrumento": "TERMO DE FOMENTO",
                "nome_convenente": "OSC X",
            }
        ]

        saidas = calcular_i3(
            planos=planos,
            resumo=[],
            instrumentos_emendas=[],
            gold_convenios=gold_convenios,
        )

        assert set(saidas) == {
            "i3_publico_alvo_instrumentos",
            "i3_publico_alvo_resumo",
            "i3_ted_publico_alvo_grupos",
            "i3_convenio_publico_alvo_grupos",
        }
        assert len(saidas["i3_publico_alvo_instrumentos"]) == 2
        # 5 grupos (GRUPOS) x 1 instrumento TED.
        assert len(saidas["i3_ted_publico_alvo_grupos"]) == 5
