"""Testes do cliente do Superset (ADR-0019, ADR-0020).

A publicação é idempotente por contrato: rodar a DAG duas vezes tem que levar
o Superset ao mesmo estado, e publicar uma dashboard nova não pode revogar
acesso concedido antes. As duas propriedades são verificadas aqui contra uma
sessão HTTP falsa.
"""

import io
import json
import zipfile
from pathlib import Path
from typing import cast

import pytest
import requests
import yaml

import cliente_superset as cs

pytestmark = pytest.mark.unit

RAIZ = Path(__file__).resolve().parents[2]
BUNDLE = RAIZ / "airflow" / "dags" / "superset" / "mgi" / "contratacoes"


class RespostaFalsa:
    def __init__(self, corpo, status_code: int = 200) -> None:
        self._corpo = corpo
        self.status_code = status_code
        self.text = json.dumps(corpo, ensure_ascii=False)
        self.content = self.text.encode()

    def json(self):
        return self._corpo


class SessaoFalsa:
    """Sessão HTTP de mentira que registra o que foi chamado."""

    def __init__(self, respostas: dict | None = None) -> None:
        # `chamadas` guarda só o que passou por `request` — a autenticação fica
        # em `autenticacao`, para que asserções sobre escrita não tropecem no
        # POST de login.
        self.chamadas: list[tuple[str, str, dict]] = []
        self.autenticacao: list[str] = []
        self.respostas = respostas or {}

    def post(self, url, **kwargs):
        self.autenticacao.append(url)
        return RespostaFalsa({"access_token": "token-de-teste"})

    def get(self, url, **kwargs):
        self.autenticacao.append(url)
        return RespostaFalsa({"result": "csrf-de-teste"})

    def request(self, metodo, url, **kwargs):
        self.chamadas.append((metodo, url, kwargs))
        for trecho, corpo in self.respostas.items():
            if trecho in url:
                valor = corpo(metodo) if callable(corpo) else corpo
                return RespostaFalsa(valor)
        return RespostaFalsa({})


def _cliente(respostas: dict | None = None) -> tuple[cs.ClienteSuperset, SessaoFalsa]:
    sessao = SessaoFalsa(respostas)
    cliente = cs.ClienteSuperset(
        base_url="http://superset:8088",
        usuario="admin",
        senha="admin",
        sessao=cast(requests.Session, sessao),
    )
    return cliente, sessao


class TestEmpacotamentoDoBundle:
    def test_todo_arquivo_fica_sob_uma_raiz_unica(self) -> None:
        nomes = zipfile.ZipFile(io.BytesIO(cs.montar_zip(BUNDLE))).namelist()
        assert nomes and all(nome.startswith("contratacoes/") for nome in nomes)
        assert "contratacoes/metadata.yaml" in nomes

    def test_uri_do_ambiente_substitui_o_placeholder(self) -> None:
        conteudo = cs.montar_zip(BUNDLE, uri="postgresql+psycopg2://u:p@h:5432/dw")
        arquivo = zipfile.ZipFile(io.BytesIO(conteudo)).read(
            "contratacoes/databases/gov_bricks_mgi.yaml"
        )
        assert yaml.safe_load(arquivo)["sqlalchemy_uri"] == (
            "postgresql+psycopg2://u:p@h:5432/dw"
        )

    def test_arquivo_versionado_nao_e_alterado(self) -> None:
        """A troca de URI acontece em memória — o repositório fica intacto."""
        antes = (BUNDLE / "databases" / "gov_bricks_mgi.yaml").read_bytes()
        cs.montar_zip(BUNDLE, uri="postgresql+psycopg2://outra:coisa@h:5432/dw")
        assert (BUNDLE / "databases" / "gov_bricks_mgi.yaml").read_bytes() == antes

    def test_bundle_inexistente_falha(self, tmp_path: Path) -> None:
        with pytest.raises(cs.ErroSuperset):
            cs.montar_zip(tmp_path / "nao-existe")

    def test_senha_vem_do_ambiente_e_nao_do_bundle(self, monkeypatch) -> None:
        monkeypatch.setenv("SUPERSET_DW_PASSWORD", "segredo")
        senhas = cs.senhas_do_bundle(BUNDLE)
        assert senhas == {"databases/gov_bricks_mgi.yaml": "segredo"}

    def test_sem_senha_no_ambiente_nada_e_enviado(self, monkeypatch) -> None:
        monkeypatch.delenv("SUPERSET_DW_PASSWORD", raising=False)
        assert cs.senhas_do_bundle(BUNDLE) == {}


class TestAutenticacao:
    def test_login_precede_o_csrf(self) -> None:
        cliente, sessao = _cliente()
        cliente.autenticar()
        urls = sessao.autenticacao
        assert urls[0].endswith("/api/v1/security/login")
        assert urls[1].endswith("/api/v1/security/csrf_token/")

    def test_toda_escrita_leva_token_e_csrf(self) -> None:
        cliente, sessao = _cliente()
        cliente.requisitar("POST", "/api/v1/security/roles/", json={"name": "gh_x"})
        cabecalhos = sessao.chamadas[-1][2]["headers"]
        assert cabecalhos["Authorization"] == "Bearer token-de-teste"
        assert cabecalhos["X-CSRFToken"] == "csrf-de-teste"

    def test_erro_http_vira_excecao_com_o_corpo(self) -> None:
        class SessaoQueFalha(SessaoFalsa):
            def request(self, metodo, url, **kwargs):
                return RespostaFalsa({"message": "sem permissão"}, status_code=403)

        cliente = cs.ClienteSuperset(
            "http://s:8088", "a", "b", sessao=cast(requests.Session, SessaoQueFalha())
        )
        with pytest.raises(cs.ErroSuperset) as erro:
            cliente.requisitar("GET", "/api/v1/dataset/")
        assert "403" in str(erro.value) and "sem permissão" in str(erro.value)


class TestPapeis:
    def test_papel_existente_nao_e_recriado(self) -> None:
        cliente, sessao = _cliente({"/security/roles/?q=": {"result": [{"id": 7}]}})
        assert cliente.garantir_papel("gh_ipea_publico") == 7
        assert not any(m == "POST" for m, _, _ in sessao.chamadas)

    def test_papel_ausente_e_criado(self) -> None:
        def por_metodo(metodo):
            return {"id": 9} if metodo == "POST" else {"result": []}

        cliente, sessao = _cliente({"/security/roles/": por_metodo})
        assert cliente.garantir_papel("gh_ipea_publico") == 9

    def test_concessao_preserva_permissoes_ja_existentes(self) -> None:
        """Publicar uma dashboard não pode revogar acesso concedido antes."""
        cliente, sessao = _cliente({"/roles/3/permissions/": {"result": [{"id": 10}]}})
        final = cliente.conceder_permissoes(3, [20])
        assert final == {10, 20}
        enviados = [k for m, u, k in sessao.chamadas if m == "POST"]
        assert enviados[-1]["json"] == {"permission_view_menu_ids": [10, 20]}

    def test_nada_e_enviado_quando_nao_ha_o_que_conceder(self) -> None:
        cliente, sessao = _cliente({"/roles/3/permissions/": {"result": [{"id": 10}]}})
        cliente.conceder_permissoes(3, [10])
        assert not any(m == "POST" for m, _, _ in sessao.chamadas)

    def test_permissao_do_dataset_usa_o_nome_do_superset(self) -> None:
        permissoes = {
            "result": [
                {
                    "id": 42,
                    "permission": {"name": "datasource_access"},
                    "view_menu": {"name": "[gov_bricks_mgi].[contratos_por_orgao](id:5)"},
                },
                {
                    "id": 43,
                    "permission": {"name": "can_read"},
                    "view_menu": {"name": "Dashboard"},
                },
            ]
        }
        cliente, sessao = _cliente({"/permissions-resources/": permissoes})
        assert (
            cliente.permissao_do_dataset("gov_bricks_mgi", "contratos_por_orgao", 5) == 42
        )
        assert cliente.permissao_do_dataset("gov_bricks_mgi", "outra", 5) is None


class TestRecorte:
    def test_recorte_novo_e_criado(self) -> None:
        def por_metodo(metodo):
            return {"id": 4} if metodo == "POST" else {"result": []}

        cliente, sessao = _cliente({"/rowlevelsecurity/": por_metodo})
        assert (
            cliente.garantir_recorte(
                "gh_ipea_recorte_orgao", "co_orgao = '25206'", [5], [7]
            )
            == 4
        )
        corpo = [k for m, _, k in sessao.chamadas if m == "POST"][-1]["json"]
        assert corpo["filter_type"] == "Regular"
        assert corpo["clause"] == "co_orgao = '25206'"
        assert corpo["tables"] == [5] and corpo["roles"] == [7]

    def test_recorte_existente_e_atualizado_no_lugar(self) -> None:
        cliente, sessao = _cliente({"/rowlevelsecurity/": {"result": [{"id": 11}]}})
        assert (
            cliente.garantir_recorte("gh_ipea_recorte_orgao", "co_orgao = '1'", [5], [7])
            == 11
        )
        metodos = [m for m, _, _ in sessao.chamadas]
        assert "PUT" in metodos and "POST" not in metodos


class TestDataset:
    def test_id_do_dataset_filtra_por_tabela_e_schema(self) -> None:
        cliente, sessao = _cliente({"/api/v1/dataset/": {"result": [{"id": 5}]}})
        assert cliente.id_do_dataset("contratos_por_orgao", "003_gld_contratacoes") == 5
        url = [u for m, u, _ in sessao.chamadas if "/dataset/" in u][-1]
        assert "table_name" in url and "003_gld_contratacoes" in url

    def test_dataset_ausente_devolve_none(self) -> None:
        cliente, sessao = _cliente({"/api/v1/dataset/": {"result": []}})
        assert cliente.id_do_dataset("nao_existe") is None
