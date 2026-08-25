"""Testes do catálogo de publicação (ADR-0019, ADR-0020).

O catálogo do repositório é a fixture destes testes de propósito: é ele que o
CI precisa manter válido, e um teste que só exercita catálogos sintéticos não
percebe quando o catálogo de verdade quebra.
"""

from pathlib import Path

import pytest

from scripts.publicacao import bundle as bundle_mod
from scripts.publicacao import dbt_meta, validacao
from scripts.publicacao.catalogo import (
    Acesso,
    Dataset,
    Nivel,
    Publicacao,
    carregar,
    mais_restritiva,
)

pytestmark = pytest.mark.unit

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def catalogo():
    return carregar()


class TestVocabularioDeNiveis:
    def test_niveis_sao_cumulativos(self, catalogo) -> None:
        """Um nível mais alto vê tudo o que o anterior vê — senão a ordem mente."""
        ordenados = catalogo.acesso.ordenados()
        for menor, maior in zip(ordenados, ordenados[1:]):
            vistas_menor = set(catalogo.acesso.nivel(menor).ve_classificacoes)
            vistas_maior = set(catalogo.acesso.nivel(maior).ve_classificacoes)
            assert vistas_menor < vistas_maior, f"{maior} não contém {menor}"

    def test_alcanca_e_assimetrico(self, catalogo) -> None:
        assert catalogo.acesso.alcanca("interno", "publico")
        assert not catalogo.acesso.alcanca("publico", "interno")

    def test_nome_do_papel_segue_o_padrao(self, catalogo) -> None:
        assert catalogo.acesso.papel("ipea", "publico") == "gh_ipea_publico"
        assert catalogo.acesso.filtro_recorte("ipea") == "gh_ipea_recorte_orgao"

    def test_nivel_inexistente_falha_com_mensagem_util(self, catalogo) -> None:
        with pytest.raises(Exception) as erro:
            catalogo.acesso.nivel("confidencial")
        assert "publico" in str(erro.value)


class TestCatalogoDoRepositorio:
    def test_carrega_o_orgao_publicador(self, catalogo) -> None:
        assert "mgi" in catalogo.orgaos
        mgi = catalogo.orgao("mgi")
        assert mgi.database
        assert mgi.datasets and mgi.dashboards and mgi.consumidores

    def test_validacao_nao_tem_erro(self, catalogo) -> None:
        problemas = validacao.validar(catalogo)
        erros = [p for p in problemas if p.nivel == "erro"]
        assert not erros, "\n".join(str(p) for p in erros)

    def test_planos_de_acesso_estao_sincronizados(self, catalogo) -> None:
        """O plano é artefato derivado: no disco tem que bater com o catálogo."""
        assert validacao.planos_dessincronizados(catalogo) == []

    def test_todo_consumidor_tem_papel_previsivel(self, catalogo) -> None:
        mgi = catalogo.orgao("mgi")
        for id_consumidor, consumidor in mgi.consumidores.items():
            esperado = f"gh_{id_consumidor}_{consumidor.nivel}"
            assert catalogo.acesso.papel(id_consumidor, consumidor.nivel) == esperado


class TestBundleVersionado:
    def test_bundle_do_mgi_e_legivel(self) -> None:
        lido = bundle_mod.carregar(RAIZ / "airflow/dags/superset/mgi/contratacoes")
        assert lido is not None
        assert lido.ilegiveis == {}
        assert lido.tipo == "assets"
        assert [d.tabela for d in lido.datasets] == ["contratos_por_orgao"]
        assert lido.dashboards and lido.graficos

    def test_dataset_publicado_e_virtual(self) -> None:
        """`select *` deixaria coluna nova chegar à dashboard sem revisão."""
        lido = bundle_mod.carregar(RAIZ / "airflow/dags/superset/mgi/contratacoes")
        assert lido is not None
        dataset = lido.dataset("contratos_por_orgao")
        assert dataset is not None and dataset.virtual
        assert "select *" not in (dataset.sql or "").lower()

    def test_todo_grafico_le_um_dataset_do_proprio_bundle(self) -> None:
        lido = bundle_mod.carregar(RAIZ / "airflow/dags/superset/mgi/contratacoes")
        assert lido is not None
        uuids = {d.uuid for d in lido.datasets}
        for grafico in lido.graficos:
            assert grafico.dataset_uuid in uuids, grafico.nome

    def test_bundle_inexistente_devolve_none(self, tmp_path: Path) -> None:
        assert bundle_mod.carregar(tmp_path / "nao-existe") is None


class TestClassificacaoDosModelos:
    def test_le_a_classificacao_declarada_no_schema_yml(self) -> None:
        modelo = dbt_meta.carregar_modelo("mgi", "gold/contratacoes/contratos_por_orgao")
        assert modelo is not None
        assert modelo.classificacao_de("co_orgao") == "publico"
        assert modelo.classificacao_de("nu_cpf") == "pessoal"

    def test_coluna_nao_documentada_nao_vira_publica_por_omissao(self) -> None:
        modelo = dbt_meta.carregar_modelo("mgi", "gold/contratacoes/contratos_por_orgao")
        assert modelo is not None
        assert modelo.classificacao_de("coluna_que_ninguem_documentou") is None

    def test_encontra_modelo_em_pacote_importado(self) -> None:
        """A Silver vem do pacote do sistema, não do projeto do órgão."""
        modelo = dbt_meta.carregar_modelo("mgi", "silver/contratacoes/contratos")
        assert modelo is not None and modelo.projeto == "compras_gov"

    def test_modelo_inexistente_devolve_none(self) -> None:
        assert dbt_meta.carregar_modelo("mgi", "gold/nada/inexistente") is None

    def test_mais_restritiva_vence(self) -> None:
        assert mais_restritiva(["publico", "pessoal", "interno"]) == "pessoal"
        assert mais_restritiva([]) == "publico"


class TestColunaAcimaDoNivel:
    """A verificação que dá sentido ao nível declarado (ADR-0020)."""

    def _cenario(self, colunas: tuple[str, ...], nivel: str):
        acesso = Acesso(
            niveis={
                "publico": Nivel("publico", "Público", "…", ("publico",)),
                "pessoal": Nivel(
                    "pessoal", "Pessoal", "…", ("publico", "interno", "pessoal")
                ),
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
            nivel=nivel,
            recorte=True,
        )
        publicacao = Publicacao(
            orgao="mgi",
            nome="MGI",
            owner="@GovHub-br/mgi",
            database="gov_bricks_mgi",
            datasets={dataset.id: dataset},
        )
        lido = bundle_mod.Bundle(
            id="contratacoes",
            caminho=Path("."),
            versao="1.0.0",
            tipo="assets",
            datasets=(
                bundle_mod.DatasetBundle(
                    arquivo=Path("dataset.yaml"),
                    tabela=dataset.id,
                    schema="003_gld_contratacoes",
                    uuid="uuid-dataset",
                    database_uuid="uuid-db",
                    colunas=colunas,
                    sql="select …",
                ),
            ),
        )
        from scripts.publicacao.catalogo import CatalogoPublicacao

        catalogo = CatalogoPublicacao(acesso=acesso, orgaos={"mgi": publicacao})
        return validacao._validar_colunas_expostas(
            catalogo, publicacao, dataset, lido, "teste", None
        )

    def test_coluna_pessoal_em_dataset_publico_e_erro(self) -> None:
        problemas = self._cenario(("co_orgao", "nu_cpf"), nivel="publico")
        erros = [p for p in problemas if p.nivel == "erro"]
        assert erros and "nu_cpf" in erros[0].mensagem

    def test_mesma_coluna_e_aceita_quando_o_nivel_comporta(self) -> None:
        problemas = self._cenario(("co_orgao", "nu_cpf"), nivel="pessoal")
        assert [p for p in problemas if p.nivel == "erro"] == []

    def test_coluna_sem_classificacao_vale_como_pessoal(self) -> None:
        problemas = self._cenario(("co_orgao", "coluna_nova"), nivel="publico")
        erros = [p for p in problemas if p.nivel == "erro"]
        assert erros and "coluna_nova" in erros[0].mensagem

    def test_recorte_sem_a_coluna_de_recorte_e_erro(self) -> None:
        """Recorte declarado sobre coluna ausente seria um filtro que não filtra."""
        problemas = self._cenario(("co_uasg", "nu_ni"), nivel="publico")
        assert any("recorte" in p.mensagem for p in problemas if p.nivel == "erro")
