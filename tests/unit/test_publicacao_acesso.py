"""Testes do plano de acesso gerado (ADR-0020).

O plano é o que a DAG de publicação executa: se ele estiver errado, o erro
chega ao Superset como papel a mais ou recorte a menos.
"""

import pytest
import yaml

from scripts.publicacao import acesso as acesso_mod
from scripts.publicacao.catalogo import (
    Acesso,
    CatalogoPublicacao,
    Consumidor,
    Dashboard,
    Dataset,
    Nivel,
    Publicacao,
    Relatorio,
    carregar,
)

pytestmark = pytest.mark.unit


def _catalogo_sintetico(abrangencia_ipea: str = "proprio") -> CatalogoPublicacao:
    acesso = Acesso(
        niveis={
            "publico": Nivel("publico", "Público", "…", ("publico",)),
            "interno": Nivel("interno", "Interno", "…", ("publico", "interno")),
        },
        prefixo_papel="gh",
        papel_herda="Gamma",
        chave_recorte="co_orgao",
        sufixo_recorte="recorte_orgao",
    )
    dataset = Dataset(
        id="contratos_por_orgao",
        modelo="gold/contratacoes/contratos_por_orgao",
        descricao="…",
        nivel="publico",
        recorte=True,
    )
    publicacao = Publicacao(
        orgao="mgi",
        nome="MGI",
        owner="@GovHub-br/mgi",
        database="gov_bricks_mgi",
        datasets={dataset.id: dataset},
        dashboards={
            "contratacoes": Dashboard(
                id="contratacoes",
                titulo="Contratações",
                descricao="…",
                bundle="contratacoes",
                nivel="publico",
                datasets=("contratos_por_orgao",),
            )
        },
        relatorios={
            "mensal": Relatorio(
                id="mensal",
                titulo="Mensal",
                descricao="…",
                dag="mensal_mgi_report_dag",
                dataset="contratos_por_orgao",
                formato="csv",
                destinos=("storage", "email"),
                nivel="publico",
                destinatarios_variavel="destinatarios_mensal",
            )
        },
        consumidores={
            "mgi": Consumidor(
                id="mgi",
                nome="MGI",
                nivel="interno",
                codigo_orgao="48000",
                abrangencia="total",
                dashboards=("contratacoes",),
                relatorios=("mensal",),
            ),
            "ipea": Consumidor(
                id="ipea",
                nome="Ipea",
                nivel="publico",
                codigo_orgao="25206",
                abrangencia=abrangencia_ipea,
                dashboards=("contratacoes",),
                relatorios=("mensal",),
            ),
        },
    )
    return CatalogoPublicacao(acesso=acesso, orgaos={"mgi": publicacao})


class TestPlanoDeAcesso:
    def test_um_papel_por_consumidor(self) -> None:
        plano = acesso_mod.montar(_catalogo_sintetico(), "mgi")
        assert [p.nome for p in plano.papeis] == ["gh_ipea_publico", "gh_mgi_interno"]

    def test_papel_recebe_os_datasets_das_dashboards_dele(self) -> None:
        plano = acesso_mod.montar(_catalogo_sintetico(), "mgi")
        papel = next(p for p in plano.papeis if p.nome == "gh_ipea_publico")
        assert papel.datasets == ("003_gld_contratacoes.contratos_por_orgao",)
        assert papel.dashboards == ("contratacoes",)

    def test_abrangencia_propria_gera_recorte_por_orgao(self) -> None:
        plano = acesso_mod.montar(_catalogo_sintetico(), "mgi")
        assert [r.papel for r in plano.recortes] == ["gh_ipea_publico"]
        assert plano.recortes[0].clausula == "co_orgao = '25206'"

    def test_abrangencia_total_nao_gera_recorte(self) -> None:
        plano = acesso_mod.montar(_catalogo_sintetico(abrangencia_ipea="total"), "mgi")
        assert plano.recortes == ()

    def test_relatorio_entrega_com_o_mesmo_recorte_da_dashboard(self) -> None:
        """Relatório não pode ser a porta dos fundos do controle de acesso."""
        plano = acesso_mod.montar(_catalogo_sintetico(), "mgi")
        entregas = {e.consumidor: e.clausula for e in plano.relatorios[0].entregas}
        assert entregas == {"ipea": "co_orgao = '25206'", "mgi": None}

    def test_consumidor_sem_o_relatorio_nao_recebe_entrega(self) -> None:
        catalogo = _catalogo_sintetico()
        publicacao = catalogo.orgao("mgi")
        publicacao.consumidores["ipea"] = Consumidor(
            id="ipea",
            nome="Ipea",
            nivel="publico",
            codigo_orgao="25206",
            abrangencia="proprio",
            dashboards=("contratacoes",),
            relatorios=(),
        )
        plano = acesso_mod.montar(catalogo, "mgi")
        assert [e.consumidor for e in plano.relatorios[0].entregas] == ["mgi"]


class TestRenderizacao:
    def test_render_e_deterministico(self) -> None:
        catalogo = _catalogo_sintetico()
        plano = acesso_mod.montar(catalogo, "mgi")
        assert acesso_mod.renderizar(plano) == acesso_mod.renderizar(plano)

    def test_render_avisa_que_o_arquivo_e_gerado(self) -> None:
        plano = acesso_mod.montar(_catalogo_sintetico(), "mgi")
        assert "Não edite à mão" in acesso_mod.renderizar(plano)

    def test_render_produz_yaml_legivel_pela_dag(self) -> None:
        plano = acesso_mod.montar(_catalogo_sintetico(), "mgi")
        documento = yaml.safe_load(acesso_mod.renderizar(plano))
        assert documento["database"] == "gov_bricks_mgi"
        assert documento["bundles"] == ["contratacoes"]
        assert {p["nome"] for p in documento["papeis"]} == {
            "gh_ipea_publico",
            "gh_mgi_interno",
        }
        assert documento["recortes"][0]["clausula"] == "co_orgao = '25206'"


class TestMatriz:
    def test_matriz_mostra_papel_recorte_e_relatorio(self) -> None:
        texto = acesso_mod.render_matriz(carregar())
        assert "gh_ipea_publico" in texto
        assert "co_orgao = '25206'" in texto
        assert "contratacoes_mensal" in texto
        assert "todas (abrangência total)" in texto
