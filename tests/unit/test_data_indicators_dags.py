"""Testes das DAGs de indicadores (ADR-0022).

Valem aqui as mesmas convenções de nome, pasta e tag das demais categorias
(ADR-0008), mais as duas regras próprias do ADR-0022: a DAG vive em
`data_indicators/<orgao>/` e o resultado é um produto de dados Gold.
"""

import re
from pathlib import Path

import pytest
from airflow.models import DagBag

pytestmark = pytest.mark.unit

DAGS_FOLDER = Path(__file__).resolve().parents[2] / "airflow" / "dags" / "data_indicators"

TAG_FORMAT = re.compile(r"^[a-z_]+:[a-z0-9_]+$")


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag(dag_folder=str(DAGS_FOLDER), include_examples=False)


class TestDagsIndicadoresIntegridade:
    def test_sem_erro_de_import(self, dagbag: DagBag) -> None:
        assert dagbag.import_errors == {}, dagbag.import_errors

    def test_ha_ao_menos_uma_dag(self, dagbag: DagBag) -> None:
        assert dagbag.dags, "nenhuma DAG de indicador carregada"

    def test_dag_ids_correspondem_aos_nomes_dos_arquivos(self, dagbag: DagBag) -> None:
        arquivos = {p.stem for p in DAGS_FOLDER.rglob("*_indicator_dag.py")}
        assert set(dagbag.dags) == arquivos

    def test_dag_ids_terminam_em_indicator_dag(self, dagbag: DagBag) -> None:
        for dag_id in dagbag.dags:
            assert dag_id.endswith("_indicator_dag"), dag_id

    def test_arquivo_fica_em_pasta_de_orgao(self, dagbag: DagBag) -> None:
        """ADR-0022: indicador é sempre de um órgão, como a transformação."""
        for caminho in DAGS_FOLDER.rglob("*_indicator_dag.py"):
            orgao = caminho.parent.name
            assert (
                caminho.parent.parent == DAGS_FOLDER
            ), f"{caminho} deve estar em data_indicators/<orgao>/"
            assert (
                f"_{orgao}_indicator_dag" in caminho.stem
            ), f"{caminho.name} deve conter o órgão '{orgao}' no nome"

    def test_todas_tem_description(self, dagbag: DagBag) -> None:
        sem = [i for i, d in dagbag.dags.items() if not d.description]
        assert not sem, f"DAGs sem description: {sem}"

    def test_tags_seguem_o_formato_do_adr_0008(self, dagbag: DagBag) -> None:
        violacoes = {
            i: [t for t in d.tags if not TAG_FORMAT.match(t)]
            for i, d in dagbag.dags.items()
            if any(not TAG_FORMAT.match(t) for t in d.tags)
        }
        assert not violacoes, f"Tags fora do formato dimensao:valor: {violacoes}"

    def test_todas_tem_tag_de_orgao(self, dagbag: DagBag) -> None:
        sem = [
            i
            for i, d in dagbag.dags.items()
            if not any(t.startswith("orgao:") for t in d.tags)
        ]
        assert not sem, f"DAGs de indicador sem tag orgao:: {sem}"

    def test_todas_declaram_dominio_indicadores(self, dagbag: DagBag) -> None:
        sem = [i for i, d in dagbag.dags.items() if "dominio:indicadores" not in d.tags]
        assert not sem, f"DAGs sem tag dominio:indicadores: {sem}"

    def test_todas_declaram_camada_gold(self, dagbag: DagBag) -> None:
        """ADR-0022: a saída de um indicador é produto de dados Gold."""
        sem = [i for i, d in dagbag.dags.items() if "camada:gold" not in d.tags]
        assert not sem, f"DAGs de indicador sem tag camada:gold: {sem}"

    def test_todas_tem_owner_e_queue(self, dagbag: DagBag) -> None:
        sem_owner = [i for i, d in dagbag.dags.items() if not d.default_args.get("owner")]
        sem_queue = [i for i, d in dagbag.dags.items() if not d.default_args.get("queue")]
        assert not sem_owner, f"DAGs sem owner em default_args: {sem_owner}"
        assert not sem_queue, f"DAGs sem queue em default_args: {sem_queue}"


class TestContratoDoAdr0022:
    """A saída vai para o schema de produto Gold, e não para um schema livre."""

    def test_saida_vai_para_o_schema_gold_de_indicadores(self) -> None:
        for caminho in DAGS_FOLDER.rglob("*_indicator_dag.py"):
            conteudo = caminho.read_text(encoding="utf-8")
            assert (
                'SCHEMA_SAIDA = "003_gld_indicadores"' in conteudo
            ), f"{caminho.name} deve gravar em 003_gld_indicadores (ADR-0010)"

    def test_leitura_usa_a_connection_do_destino_analitico(self) -> None:
        """ADR-0021: o destino analítico é `postgres_dw`, não o banco do Airflow."""
        for caminho in DAGS_FOLDER.rglob("*_indicator_dag.py"):
            conteudo = caminho.read_text(encoding="utf-8")
            assert (
                'CONEXAO = "postgres_dw"' in conteudo
            ), f"{caminho.name} deve ler por postgres_dw"
