"""
Comportamento da contrato_publicacao_ingest_dag (issue #25).

As regras estruturais (dag_id, tags, owner, description) já são cobradas para
toda a pasta em test_data_ingest_contratos_gov_dags.py. Este arquivo cobre o que
é desta DAG: o recorte pela Variable de escopo sobre as raws de ativos e
inativos, o contrato_id vindo da URL, a validação do lote antes da escrita e a
diferença em relação ao histórico — contrato sem publicação é possível na fonte,
então só a execução grande e inteira vazia é anomalia.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from airflow.models import DagBag
from landing_zone import RawIndisponivel

pytestmark = pytest.mark.unit

DAG_FILE = (
    Path(__file__).resolve().parents[2]
    / "airflow"
    / "dags"
    / "data_ingest"
    / "contratos_gov"
    / "contrato_publicacao_ingest_dag.py"
)
DAG_ID = "contrato_publicacao_ingest_dag"
SISTEMA = "contratos_gov"
ENTIDADE = "contrato_publicacao"
BLOCK_SIZE = 50  # espelha a constante da DAG
MIN_CONTRATOS = 10  # espelha MIN_CONTRATOS_PARA_EXIGIR_PUBLICACAO


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag(dag_folder=str(DAG_FILE), include_examples=False)


def task(dagbag: DagBag, task_id: str) -> Any:
    """Função Python por trás de uma task do TaskFlow, para chamar direto.

    `Any` porque os helpers mexem no `__globals__`, que `Callable` não declara.
    """
    return dagbag.dags[DAG_ID].get_task(task_id).python_callable


def usar_escopo(alvo: Any, monkeypatch: pytest.MonkeyPatch, escopo: object) -> None:
    variavel = MagicMock()
    variavel.get.return_value = escopo
    monkeypatch.setitem(alvo.__globals__, "Variable", variavel)


def usar_raw(alvo: Any, monkeypatch: pytest.MonkeyPatch, por_entidade: dict) -> None:
    """Faz distinct_raw_rows responder (id, orgao_codigo) por entidade."""

    def linhas(_sistema: str, entidade: str, _colunas: list[str]) -> list[tuple]:
        resposta = por_entidade[entidade]
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    monkeypatch.setitem(alvo.__globals__, "distinct_raw_rows", linhas)


def usar_cliente(alvo: Any, monkeypatch: pytest.MonkeyPatch, por_contrato: dict):
    """listar_subrecurso devolve o payload com o contrato_id da URL, como o cliente."""
    cliente = MagicMock()
    cliente.listar_subrecurso.side_effect = lambda contrato_id, _recurso: [
        {**registro, "contrato_id": contrato_id} for registro in por_contrato[contrato_id]
    ]
    monkeypatch.setitem(alvo.__globals__, "ClienteContratosGov", lambda: cliente)
    return cliente


def capturar_escritas(alvo: Any, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    escrita = MagicMock()
    monkeypatch.setitem(alvo.__globals__, "write_raw", escrita)
    return escrita


def publicacao(publicacao_id: int, historico_id: int = 1) -> dict[str, object]:
    return {
        "id": publicacao_id,
        "contratohistorico_id": historico_id,
        "data_publicacao": "2023-05-11",
        "status": "PUBLICADA",
        "texto_dou": "##ATO EXTRATO DE CONTRATO\r\n\r\nNúmero do Contrato: 2/2019.",
        "link_publicacao": None,
    }


def test_dag_carrega_sem_erro(dagbag: DagBag) -> None:
    assert dagbag.import_errors == {}, dagbag.import_errors
    assert DAG_ID in dagbag.dags


def test_agenda_semanal_no_horario_da_fase(dagbag: DagBag) -> None:
    """14:30 de sábado: depois do cronograma (#24, 14:00), antes da garantia (#26)."""
    assert dagbag.dags[DAG_ID].schedule == "30 14 * * 6"


class TestEscopo:
    def test_une_ativos_e_inativos_do_escopo_em_ordem_numerica(
        self, dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        alvo = task(dagbag, "get_contract_blocks")
        usar_escopo(alvo, monkeypatch, ["46000"])
        usar_raw(
            alvo,
            monkeypatch,
            {
                "contrato_ativo": [("10", "46000"), ("2", "46000"), ("7", "99999")],
                "contrato_inativo": [("10", "46000"), ("3", "46000")],
            },
        )
        monkeypatch.delenv("INGEST_MAX_CONTRATOS", raising=False)

        assert alvo() == [["2", "3", "10"]]

    def test_limite_local_trunca_antes_dos_blocos(
        self, dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        alvo = task(dagbag, "get_contract_blocks")
        usar_escopo(alvo, monkeypatch, ["46000"])
        ids = [(str(i), "46000") for i in range(1, 121)]
        usar_raw(alvo, monkeypatch, {"contrato_ativo": ids, "contrato_inativo": []})
        monkeypatch.setenv("INGEST_MAX_CONTRATOS", "60")

        blocos = alvo()

        assert [len(b) for b in blocos] == [BLOCK_SIZE, 10]
        assert blocos[0][0] == "1"

    def test_escopo_grande_aumenta_o_bloco_em_vez_de_passar_de_1024(
        self, dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        alvo = task(dagbag, "get_contract_blocks")
        usar_escopo(alvo, monkeypatch, ["46000"])
        ids = [(str(i), "46000") for i in range(1, 60_001)]
        usar_raw(alvo, monkeypatch, {"contrato_ativo": ids, "contrato_inativo": []})
        monkeypatch.delenv("INGEST_MAX_CONTRATOS", raising=False)

        blocos = alvo()

        assert len(blocos) <= 1024
        assert sum(len(b) for b in blocos) == 60_000

    @pytest.mark.parametrize(
        "escopo",
        [[], [46000], ["4600"], ["46000a"], "46000", None],
        ids=["vazio", "inteiro", "quatro_digitos", "nao_numerico", "texto", "nulo"],
    )
    def test_variable_invalida_falha_antes_de_ler_a_raw(
        self, dagbag: DagBag, monkeypatch: pytest.MonkeyPatch, escopo: object
    ) -> None:
        alvo = task(dagbag, "get_contract_blocks")
        usar_escopo(alvo, monkeypatch, escopo)
        usar_raw(alvo, monkeypatch, {})

        with pytest.raises(RuntimeError, match="contratos_gov_escopo_orgaos"):
            alvo()

    def test_raw_de_cabecalho_ausente_falha_com_mensagem(
        self, dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        alvo = task(dagbag, "get_contract_blocks")
        usar_escopo(alvo, monkeypatch, ["46000"])
        usar_raw(
            alvo,
            monkeypatch,
            {"contrato_ativo": RawIndisponivel("sem tabela"), "contrato_inativo": []},
        )

        with pytest.raises(RuntimeError, match="contrato_ativo_ingest_dag"):
            alvo()

    def test_nenhum_contrato_do_escopo_falha_com_mensagem(
        self, dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        alvo = task(dagbag, "get_contract_blocks")
        usar_escopo(alvo, monkeypatch, ["46000"])
        usar_raw(
            alvo,
            monkeypatch,
            {"contrato_ativo": [("1", "99999")], "contrato_inativo": []},
        )

        with pytest.raises(RuntimeError, match="Nenhum contrato dos órgãos"):
            alvo()

    def test_id_de_contrato_invalido_na_raw_falha(
        self, dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        alvo = task(dagbag, "get_contract_blocks")
        usar_escopo(alvo, monkeypatch, ["46000"])
        usar_raw(
            alvo,
            monkeypatch,
            {"contrato_ativo": [("NaN", "46000")], "contrato_inativo": []},
        )

        with pytest.raises(RuntimeError, match="id de contrato inválido"):
            alvo()


class TestIngestao:
    def test_grava_por_contrato_com_contrato_id_da_url_e_chave_id(
        self, dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        alvo = task(dagbag, "ingest_contracts")
        cliente = usar_cliente(
            alvo, monkeypatch, {"2289": [publicacao(1), publicacao(2)], "93055": []}
        )
        escrita = capturar_escritas(alvo, monkeypatch)

        resultado = alvo(["2289", "93055"])

        assert resultado == {
            "publicacoes": 2,
            "contratos": 2,
            "contratos_vazios": 1,
            "linhas_repetidas": 0,
        }
        assert [c.args for c in cliente.listar_subrecurso.call_args_list] == [
            ("2289", "publicacoes"),
            ("93055", "publicacoes"),
        ]
        escrita.assert_called_once()
        (sistema, entidade, lote), kwargs = escrita.call_args
        assert (sistema, entidade, kwargs) == (SISTEMA, ENTIDADE, {"primary_key": ["id"]})
        assert {r["contrato_id"] for r in lote} == {"2289"}

    def test_linha_identica_repetida_e_descartada(
        self, dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        alvo = task(dagbag, "ingest_contracts")
        usar_cliente(alvo, monkeypatch, {"2289": [publicacao(1), publicacao(1)]})
        escrita = capturar_escritas(alvo, monkeypatch)

        resultado = alvo(["2289"])

        assert resultado["linhas_repetidas"] == 1
        assert len(escrita.call_args.args[2]) == 1

    @pytest.mark.parametrize(
        ("payload", "mensagem"),
        [
            ([{**publicacao(1), "id": None}], "sem id"),
            ([publicacao(1, historico_id=1), publicacao(1, historico_id=2)], "repetido"),
        ],
        ids=["sem_id", "id_repetido_com_conteudo_diferente"],
    )
    def test_lote_invalido_falha_antes_da_escrita(
        self,
        dagbag: DagBag,
        monkeypatch: pytest.MonkeyPatch,
        payload: list[dict],
        mensagem: str,
    ) -> None:
        alvo = task(dagbag, "ingest_contracts")
        usar_cliente(alvo, monkeypatch, {"2289": payload})
        escrita = capturar_escritas(alvo, monkeypatch)

        with pytest.raises(RuntimeError, match=mensagem):
            alvo(["2289"])
        escrita.assert_not_called()

    def test_registro_sem_o_contrato_id_da_url_falha(
        self, dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        alvo = task(dagbag, "ingest_contracts")
        cliente = MagicMock()
        cliente.listar_subrecurso.return_value = [publicacao(1)]  # sem contrato_id
        monkeypatch.setitem(alvo.__globals__, "ClienteContratosGov", lambda: cliente)
        escrita = capturar_escritas(alvo, monkeypatch)

        with pytest.raises(RuntimeError, match="contrato_id da URL"):
            alvo(["2289"])
        escrita.assert_not_called()


class TestValidacao:
    def _resultado(self, publicacoes: int, contratos: int) -> dict[str, int]:
        return {
            "publicacoes": publicacoes,
            "contratos": contratos,
            "contratos_vazios": contratos if publicacoes == 0 else 0,
            "linhas_repetidas": 0,
        }

    def test_soma_os_blocos(self, dagbag: DagBag) -> None:
        alvo = task(dagbag, "validate")
        assert alvo([self._resultado(3, 2), self._resultado(4, 5)]) == 7

    def test_amostra_pequena_toda_vazia_so_avisa(self, dagbag: DagBag) -> None:
        alvo = task(dagbag, "validate")
        assert alvo([self._resultado(0, MIN_CONTRATOS - 1)]) == 0

    def test_varredura_grande_toda_vazia_falha(self, dagbag: DagBag) -> None:
        alvo = task(dagbag, "validate")
        with pytest.raises(RuntimeError, match="anomalia"):
            alvo([self._resultado(0, MIN_CONTRATOS)])
