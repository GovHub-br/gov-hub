"""
Comportamento da contrato_fatura_ingest_dag (issue #23).

As regras estruturais (dag_id, tags, owner, description) já são cobradas para
toda a pasta em test_data_ingest_contratos_gov_dags.py. Este arquivo cobre o que
é específico desta DAG: o recorte pela Variable de escopo sobre as raws de ativos
e inativos, a validação de contrato_id contra a URL, a deduplicação e validação
do lote antes da escrita, a tolerância a contratos sem fatura e a gravação em
arquivos separados no object_storage.
"""

import json
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import landing_zone
import pytest
from airflow.models import DagBag
from cliente_contratos_gov import ClienteContratosGov
from landing_zone import RawIndisponivel

pytestmark = pytest.mark.unit

DAG_FILE = (
    Path(__file__).resolve().parents[2]
    / "airflow"
    / "dags"
    / "data_ingest"
    / "contratos_gov"
    / "contrato_fatura_ingest_dag.py"
)
DAG_ID = "contrato_fatura_ingest_dag"
SISTEMA = "contratos_gov"
ENTIDADE = "contrato_fatura"
BLOCK_SIZE = 50  # espelha a constante da DAG
MIN_CONTRATOS = 10  # espelha MIN_CONTRATOS_PARA_EXIGIR_FATURA


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag(dag_folder=str(DAG_FILE), include_examples=False)


def task(dagbag: DagBag, task_id: str) -> Any:
    """Função Python por trás de uma task do TaskFlow, para chamar direto."""
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


def usar_cliente(
    alvo: Any, monkeypatch: pytest.MonkeyPatch, por_contrato: dict
) -> MagicMock:
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


def fatura(
    fatura_id: int, contrato_id: Any = "2289", numero: str = "3922B"
) -> dict[str, Any]:
    return {
        "id": fatura_id,
        "contrato_id": contrato_id,
        "tipolistafatura_id": "PRESTAÇÃO DE SERVIÇOS",
        "tipo_instrumento_cobranca": "Fatura",
        "justificativafatura_id": "",
        "sfadrao_id": "2025NP000170",
        "numero": numero,
        "numero_serie": None,
        "fornecedor_contrato": "02.605.452/0001-22",
        "fornecedor_ic": "02.605.452/0001-22",
        "emissao": "2024-01-15",
        "vencimento": "2024-02-15",
        "valor": "58.314,00",
        "valorliquido": "55.000,00",
        "data_liquidacao": "2024-02-10",
        "mesref": 1,
        "anoref": 2024,
        "chave_nfe": "12345678901234567890123456789012345678901234",
        "dados_empenho": [{"numero": "2024NE000001"}],
        "dados_referencia": [],
        "dados_item_faturado": [{"item_id": 1, "quantidade": "10"}],
    }


def test_dag_carrega_sem_erro(dagbag: DagBag) -> None:
    assert dagbag.import_errors == {}, dagbag.import_errors
    assert DAG_ID in dagbag.dags


def test_agenda_semanal_no_horario_da_fase(dagbag: DagBag) -> None:
    """13:30 de sábado: depois dos empenhos (13:00) e antes do cronograma (14:00)."""
    assert dagbag.dags[DAG_ID].schedule == "30 13 * * 6"


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
    def test_grava_por_contrato_com_contrato_id_e_chave_id(
        self, dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        alvo = task(dagbag, "ingest_contracts")
        cliente = usar_cliente(
            alvo, monkeypatch, {"2289": [fatura(1001), fatura(1002)], "93055": []}
        )
        escrita = capturar_escritas(alvo, monkeypatch)

        resultado = alvo(["2289", "93055"])

        assert resultado == {
            "faturas": 2,
            "contratos": 2,
            "contratos_vazios": 1,
            "linhas_repetidas": 0,
        }
        assert [c.args for c in cliente.listar_subrecurso.call_args_list] == [
            ("2289", "faturas"),
            ("93055", "faturas"),
        ]
        escrita.assert_called_once()
        (sistema, entidade, lote), kwargs = escrita.call_args
        assert (sistema, entidade) == (SISTEMA, ENTIDADE)
        assert kwargs == {"primary_key": ["id"], "run_id": None}
        assert {r["contrato_id"] for r in lote} == {"2289"}

    def test_linha_identica_repetida_e_descartada(
        self, dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        alvo = task(dagbag, "ingest_contracts")
        usar_cliente(alvo, monkeypatch, {"2289": [fatura(1001), fatura(1001)]})
        escrita = capturar_escritas(alvo, monkeypatch)

        resultado = alvo(["2289"])

        assert resultado["linhas_repetidas"] == 1
        assert len(escrita.call_args.args[2]) == 1

    @pytest.mark.parametrize(
        ("payload", "mensagem"),
        [
            ([{**fatura(1001), "id": None}], "sem id"),
            ([fatura(1001, numero="A"), fatura(1001, numero="B")], "repetido"),
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

    def test_registro_com_contrato_id_divergente_da_url_falha(
        self, dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        alvo = task(dagbag, "ingest_contracts")
        cliente = MagicMock()
        # cliente simulando registro com contrato_id diferente da URL
        cliente.listar_subrecurso.return_value = [{**fatura(1001), "contrato_id": "9999"}]
        monkeypatch.setitem(alvo.__globals__, "ClienteContratosGov", lambda: cliente)
        escrita = capturar_escritas(alvo, monkeypatch)

        with pytest.raises(RuntimeError, match="contrato_id divergente"):
            alvo(["2289"])
        escrita.assert_not_called()


class TestValidacao:
    def _resultado(self, faturas: int, contratos: int) -> dict[str, int]:
        return {
            "faturas": faturas,
            "contratos": contratos,
            "contratos_vazios": contratos if faturas == 0 else 0,
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


PAYLOAD_REAL = [
    {
        "id": 1001069,
        "contrato_id": 2289,
        "tipolistafatura_id": "PRESTAÇÃO DE SERVIÇOS",
        "tipo_instrumento_cobranca": "Fatura",
        "justificativafatura_id": "",
        "sfadrao_id": "2025NP000170",
        "numero": "3922B",
        "numero_serie": None,
        "fornecedor_contrato": "02.605.452/0001-22",
        "fornecedor_ic": "02.605.452/0001-22",
        "contratante": "CENTRAL DE COMPRAS",
        "codigo_ug_ic": "201057",
        "emissao": "2024-01-15",
        "prazo": "30",
        "vencimento": "2024-02-15",
        "valor": "58.314,00",
        "juros": "0,00",
        "multa": "0,00",
        "glosa": "0,00",
        "valorliquido": "58.314,00",
        "base_calculo_inss": "0,00",
        "aliquota_inss": "0,00",
        "optante_cprb": "Não",
        "optante_simples": "Não",
        "valor_inss": "0,00",
        "data_liquidacao": "2024-02-10",
        "nota_cancelada": "Não",
        "processo": "19973.100001/2024-01",
        "protocolo": "2024/00001",
        "ateste": "2024-01-20",
        "repactuacao": "Não",
        "infcomplementar": "",
        "mesref": 1,
        "anoref": 2024,
        "situacao": "Paga",
        "chave_nfe": None,
        "dados_empenho": [{"empenho_id": 101, "numero": "2024NE000001"}],
        "dados_referencia": [],
        "dados_item_faturado": [{"item_id": 1, "quantidade": "10"}],
    }
]


def usar_api(
    alvo: Any, monkeypatch: pytest.MonkeyPatch, resposta: httpx.Response
) -> MagicMock:
    cliente = ClienteContratosGov(request_delay=0)
    chamada = MagicMock(return_value=resposta)
    monkeypatch.setattr(cliente.client, "request", chamada)
    monkeypatch.setitem(alvo.__globals__, "ClienteContratosGov", lambda: cliente)
    monkeypatch.setattr("cliente_base.time.sleep", lambda _s: None)
    return chamada


def http(status: int, corpo: str) -> httpx.Response:
    requisicao = httpx.Request("GET", "https://contratos.comprasnet.gov.br/api")
    return httpx.Response(status, text=corpo, request=requisicao)


class TestFonteReal:
    def test_payload_chega_ao_write_raw_intacto_com_contrato_id(
        self, dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        alvo = task(dagbag, "ingest_contracts")
        usar_api(alvo, monkeypatch, http(200, json.dumps(PAYLOAD_REAL)))
        escrita = capturar_escritas(alvo, monkeypatch)

        alvo(["2289"])

        lote = escrita.call_args.args[2]
        assert lote == [{**PAYLOAD_REAL[0], "contrato_id": 2289}]
        assert lote[0]["id"] == 1001069
        assert lote[0]["contrato_id"] == 2289
        assert lote[0]["valor"] == "58.314,00"
        assert len(lote[0]["dados_empenho"]) == 1
        assert len(lote[0]["dados_item_faturado"]) == 1

    def test_lista_vazia_e_contrato_sem_fatura(
        self, dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        alvo = task(dagbag, "ingest_contracts")
        usar_api(alvo, monkeypatch, http(200, "[]"))
        escrita = capturar_escritas(alvo, monkeypatch)

        assert alvo(["2289"])["contratos_vazios"] == 1
        escrita.assert_not_called()

    def test_http_500_falha_a_task_depois_dos_retries_sem_gravar(
        self, dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        alvo = task(dagbag, "ingest_contracts")
        chamada = usar_api(alvo, monkeypatch, http(500, "<html>erro</html>"))
        escrita = capturar_escritas(alvo, monkeypatch)

        with pytest.raises(Exception, match="API failed after the maximum"):
            alvo(["2289"])
        assert chamada.call_count == ClienteContratosGov.DEFAULT_MAX_RETRIES + 1
        escrita.assert_not_called()

    def test_corpo_que_nao_e_json_falha_em_vez_de_virar_vazio(
        self, dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        alvo = task(dagbag, "ingest_contracts")
        usar_api(alvo, monkeypatch, http(200, "<html>manutenção</html>"))
        escrita = capturar_escritas(alvo, monkeypatch)

        with pytest.raises(ValueError):
            alvo(["2289"])
        escrita.assert_not_called()

    def test_task_falha_e_o_airflow_tenta_de_novo(self, dagbag: DagBag) -> None:
        tarefa = dagbag.dags[DAG_ID].get_task("ingest_contracts")

        assert tarefa.retries == 3
        assert tarefa.retry_delay == timedelta(minutes=10)
        assert tarefa.max_active_tis_per_dag == 4


class TestObjectStorage:
    def test_cada_contrato_grava_em_arquivo_proprio(
        self, dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        alvo = task(dagbag, "ingest_contracts")
        usar_cliente(alvo, monkeypatch, {"2289": [fatura(1001)], "9099": [fatura(1002)]})
        monkeypatch.setitem(
            alvo.__globals__, "get_current_context", lambda: {"run_id": "manual__x"}
        )
        monkeypatch.setenv("RAW_BACKEND", "object_storage")
        monkeypatch.setattr(landing_zone, "_run_id_do_contexto", lambda *_a: "manual__x")
        caminhos: list[str] = []
        with patch.object(
            landing_zone, "write_parquet", side_effect=lambda _df, c: caminhos.append(c)
        ):
            alvo(["2289", "9099"])

        assert len(caminhos) == 2
        assert len(set(caminhos)) == 2
        assert all("manual__x__contrato_" in c for c in caminhos)
