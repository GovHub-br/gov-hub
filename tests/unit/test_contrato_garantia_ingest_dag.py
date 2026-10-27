"""Comportamento da ingestão das garantias por contrato (issue #26)."""

from pathlib import Path
from unittest.mock import MagicMock, call

import fsspec
import polars as pl
import pytest
from airflow.models import DagBag

import landing_zone

pytestmark = pytest.mark.unit

DAG_FILE = (
    Path(__file__).resolve().parents[2]
    / "airflow"
    / "dags"
    / "data_ingest"
    / "contratos_gov"
    / "contrato_garantia_ingest_dag.py"
)
DAG_ID = "contrato_garantia_ingest_dag"


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag(dag_folder=str(DAG_FILE), include_examples=False)


def task(dagbag: DagBag, task_id: str):
    return dagbag.dags[DAG_ID].get_task(task_id).python_callable


def test_dag_carrega_depois_dos_cabecalhos(dagbag: DagBag) -> None:
    assert dagbag.import_errors == {}, dagbag.import_errors
    assert dagbag.dags[DAG_ID].timetable.expression == "0 15 * * 6"


def test_filtra_limita_e_particiona_antes_de_expandir(
    dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
) -> None:
    preparar = task(dagbag, "get_contract_blocks")
    escopo = MagicMock(return_value={"46000"})
    ids = MagicMock(return_value=[str(i) for i in range(61)])
    monkeypatch.setitem(preparar.__globals__, "orgaos_no_escopo", escopo)
    monkeypatch.setitem(preparar.__globals__, "ids_contratos_no_escopo", ids)
    monkeypatch.setenv("INGEST_MAX_CONTRATOS", "51")

    blocos = preparar()

    assert [len(bloco) for bloco in blocos] == [25, 25, 1]
    assert [id_ for bloco in blocos for id_ in bloco] == [str(i) for i in range(51)]
    ids.assert_called_once_with({"46000"})
    assert dagbag.dags[DAG_ID].get_task("ingest_contracts").max_active_tis_per_dag == 4


def test_muitos_ids_nao_excedem_o_limite_de_mapeamento(
    dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
) -> None:
    preparar = task(dagbag, "get_contract_blocks")
    monkeypatch.setitem(preparar.__globals__, "orgaos_no_escopo", lambda: {"46000"})
    monkeypatch.setitem(
        preparar.__globals__,
        "ids_contratos_no_escopo",
        lambda _: [str(i) for i in range(26000)],
    )
    monkeypatch.delenv("INGEST_MAX_CONTRATOS", raising=False)

    blocos = preparar()

    assert len(blocos) <= 1024
    assert sum(map(len, blocos)) == 26000


def test_raw_ausente_falha_antes_de_consultar_api(
    dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
) -> None:
    preparar = task(dagbag, "get_contract_blocks")
    monkeypatch.setitem(preparar.__globals__, "orgaos_no_escopo", lambda: {"46000"})

    def sem_raw(_: set[str]) -> list[str]:
        raise RuntimeError("Execute contrato_inativo_ingest_dag antes")

    monkeypatch.setitem(preparar.__globals__, "ids_contratos_no_escopo", sem_raw)

    with pytest.raises(RuntimeError, match="contrato_inativo_ingest_dag"):
        preparar()


def test_limite_local_zerado_falha_antes_de_expandir(
    dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
) -> None:
    preparar = task(dagbag, "get_contract_blocks")
    monkeypatch.setitem(preparar.__globals__, "orgaos_no_escopo", lambda: {"46000"})
    monkeypatch.setitem(
        preparar.__globals__, "ids_contratos_no_escopo", lambda _: ["2289"]
    )
    monkeypatch.setenv("INGEST_MAX_CONTRATOS", "0")

    with pytest.raises(RuntimeError, match="INGEST_MAX_CONTRATOS"):
        preparar()


def test_garantia_da_api_e_gravada_sem_alterar_campos_da_fonte(
    dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingerir = task(dagbag, "ingest_contracts")
    payload = [
        {
            "id": 9062,
            "contrato_id": 47411,
            "tipo": "Seguro Garantia",
            "valor": "121.248,40",
            "vencimento": "2022-06-15",
        }
    ]
    cliente = MagicMock()
    cliente.listar_subrecurso.side_effect = [payload, []]
    escrita = MagicMock()
    monkeypatch.setitem(ingerir.__globals__, "ClienteContratosGov", lambda: cliente)
    monkeypatch.setitem(ingerir.__globals__, "write_raw", escrita)

    assert ingerir(["47411", "2289"]) == {
        "garantias": 1,
        "contratos_vazios": 1,
        "linhas_repetidas": 0,
    }
    assert cliente.listar_subrecurso.call_args_list == [
        call("47411", "garantias"),
        call("2289", "garantias"),
    ]
    escrita.assert_called_once_with(
        "contratos_gov",
        "contrato_garantia",
        payload,
        primary_key=["id"],
        run_id=None,
    )


def test_contratos_sem_garantia_nao_geram_escrita(
    dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingerir = task(dagbag, "ingest_contracts")
    cliente = MagicMock()
    cliente.listar_subrecurso.return_value = []
    escrita = MagicMock()
    monkeypatch.setitem(ingerir.__globals__, "ClienteContratosGov", lambda: cliente)
    monkeypatch.setitem(ingerir.__globals__, "write_raw", escrita)

    assert ingerir(["2289", "2290"]) == {
        "garantias": 0,
        "contratos_vazios": 2,
        "linhas_repetidas": 0,
    }
    escrita.assert_not_called()


def test_linha_identica_repetida_e_descartada(
    dagbag: DagBag, monkeypatch: pytest.MonkeyPatch
) -> None:
    ingerir = task(dagbag, "ingest_contracts")
    garantia = {"id": 9062, "contrato_id": 47411, "valor": "121.248,40"}
    cliente = MagicMock()
    cliente.listar_subrecurso.return_value = [garantia, dict(garantia)]
    escrita = MagicMock()
    monkeypatch.setitem(ingerir.__globals__, "ClienteContratosGov", lambda: cliente)
    monkeypatch.setitem(ingerir.__globals__, "write_raw", escrita)

    assert ingerir(["47411"]) == {
        "garantias": 1,
        "contratos_vazios": 0,
        "linhas_repetidas": 1,
    }
    assert escrita.call_args.args[2] == [garantia]


@pytest.mark.parametrize(
    "payload",
    [
        [{"id": 9062, "contrato_id": 99999}],
        [{"id": 9062}],
        [{"contrato_id": 47411}],
        [
            {"id": 9062, "contrato_id": 47411, "valor": "1,00"},
            {"id": 9062, "contrato_id": 47411, "valor": "2,00"},
        ],
    ],
    ids=["contrato_divergente", "sem_contrato", "sem_id", "id_conflitante"],
)
def test_lote_invalido_falha_antes_da_escrita(
    dagbag: DagBag, monkeypatch: pytest.MonkeyPatch, payload: list[dict]
) -> None:
    ingerir = task(dagbag, "ingest_contracts")
    cliente = MagicMock()
    cliente.listar_subrecurso.return_value = payload
    escrita = MagicMock()
    monkeypatch.setitem(ingerir.__globals__, "ClienteContratosGov", lambda: cliente)
    monkeypatch.setitem(ingerir.__globals__, "write_raw", escrita)

    with pytest.raises(RuntimeError):
        ingerir(["47411"])

    escrita.assert_not_called()


def test_object_storage_mantem_arquivos_por_contrato_e_execucao(
    dagbag: DagBag, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ingerir = task(dagbag, "ingest_contracts")
    cliente = MagicMock()
    cliente.listar_subrecurso.side_effect = lambda contrato_id, _: [
        {
            "id": int(contrato_id),
            "contrato_id": int(contrato_id),
            "valor": "1.234,56",
            "vencimento": "2026-10-26",
        }
    ]
    run_id = ["primeiro"]
    monkeypatch.setitem(ingerir.__globals__, "ClienteContratosGov", lambda: cliente)
    monkeypatch.setitem(ingerir.__globals__, "write_raw", landing_zone.write_raw)
    monkeypatch.setitem(
        ingerir.__globals__, "get_current_context", lambda: {"run_id": run_id[0]}
    )
    monkeypatch.setattr(
        landing_zone, "get_storage_fs", lambda: fsspec.filesystem("file", auto_mkdir=True)
    )
    monkeypatch.setattr(landing_zone, "get_bucket", lambda: str(tmp_path))
    monkeypatch.setenv("RAW_BACKEND", "object_storage")

    assert ingerir(["47411", "2289"])["garantias"] == 2
    # Retry da mesma DagRun também deve preservar os arquivos anteriores.
    assert ingerir(["47411", "2289"])["garantias"] == 2
    run_id[0] = "segundo"
    assert ingerir(["47411", "2289"])["garantias"] == 2

    arquivos = sorted(tmp_path.rglob("*.parquet"))
    assert len(arquivos) == 6
    identificadores = [arquivo.stem.split("--lote-")[0] for arquivo in arquivos]
    assert set(identificadores) == {
        "primeiro__contrato_47411",
        "primeiro__contrato_2289",
        "segundo__contrato_47411",
        "segundo__contrato_2289",
    }
    assert identificadores.count("primeiro__contrato_47411") == 2
    assert identificadores.count("primeiro__contrato_2289") == 2
    for arquivo in arquivos:
        registro = pl.read_parquet(arquivo).to_dicts()[0]
        assert str(registro["contrato_id"]) in arquivo.stem
        assert registro["dt_ingest"]
        assert registro["valor"] == "1.234,56"


def test_validacao_conta_os_blocos(dagbag: DagBag) -> None:
    validar = task(dagbag, "validate")
    assert (
        validar(
            [
                {"garantias": 3, "contratos_vazios": 1, "linhas_repetidas": 2},
                {"garantias": 2, "contratos_vazios": 4, "linhas_repetidas": 0},
            ]
        )
        == 5
    )
