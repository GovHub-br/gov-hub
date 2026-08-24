"""Testes das DAGs de transformação (ADR-0018).

Carregar a DAG aqui não é formalidade: o Cosmos monta o grafo rodando `dbt ls`
no projeto durante o import, então este teste é o que garante que o projeto dbt
e os pacotes locais que ele importa continuam resolvendo — falha que, sem isto,
só apareceria no DAG processor em execução.
"""

import re
from pathlib import Path

import pytest
from airflow.models import DagBag

pytestmark = pytest.mark.unit

DAGS_FOLDER = Path(__file__).resolve().parents[2] / "airflow" / "dags" / "data_transform"

TAG_FORMAT = re.compile(r"^[a-z_]+:[a-z0-9_]+$")


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag(dag_folder=str(DAGS_FOLDER), include_examples=False)


class TestDagsTransformacaoIntegridade:
    def test_sem_erro_de_import(self, dagbag: DagBag) -> None:
        assert dagbag.import_errors == {}, dagbag.import_errors

    def test_ha_ao_menos_uma_dag(self, dagbag: DagBag) -> None:
        assert dagbag.dags, "nenhuma DAG de transformação carregada"

    def test_dag_ids_correspondem_aos_nomes_dos_arquivos(self, dagbag: DagBag) -> None:
        arquivos = {p.stem for p in DAGS_FOLDER.rglob("*_transform_dag.py")}
        assert set(dagbag.dags) == arquivos

    def test_dag_ids_terminam_em_transform_dag(self, dagbag: DagBag) -> None:
        for dag_id in dagbag.dags:
            assert dag_id.endswith("_transform_dag"), dag_id

    def test_arquivo_fica_em_pasta_de_orgao(self, dagbag: DagBag) -> None:
        """ADR-0018: transformação é sempre específica de um órgão."""
        for caminho in DAGS_FOLDER.rglob("*_transform_dag.py"):
            orgao = caminho.parent.name
            assert (
                caminho.parent.parent == DAGS_FOLDER
            ), f"{caminho} deve estar em data_transform/<orgao>/"
            assert caminho.stem.endswith(
                f"{orgao}_transform_dag"
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
        assert not sem, f"DAGs de transformação sem tag orgao:: {sem}"

    def test_todas_tem_owner(self, dagbag: DagBag) -> None:
        sem = [i for i, d in dagbag.dags.items() if not d.default_args.get("owner")]
        assert not sem, f"DAGs sem owner em default_args: {sem}"


class TestGrafoDbtRenderizado:
    def test_mgi_expande_em_uma_task_por_modelo(self, dagbag: DagBag) -> None:
        """O ganho do Cosmos sobre um `dbt build` em BashOperator (ADR-0018).

        Se o grafo colapsar em uma única task, a decisão do ADR deixou de valer
        na prática — e o retry volta a reprocessar o projeto inteiro.
        """
        dag = dagbag.dags["mgi_transform_dag"]
        tasks = {t.task_id for t in dag.tasks}

        # A Silver do pacote compras_gov e a Gold do próprio MGI, cada modelo
        # como sua própria task.
        for modelo in ("contratos", "uasg", "orgao", "contratos_por_orgao"):
            assert any(
                t.startswith(modelo) for t in tasks
            ), f"modelo '{modelo}' não virou task: {sorted(tasks)}"
        assert len(tasks) > 1
