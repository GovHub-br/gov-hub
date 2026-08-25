"""Testes das DAGs de publicação e de relatório (ADR-0019).

Carregar as DAGs aqui é o que garante que a factory de relatório e o plano de
acesso gerado continuam casando: a DAG lê o plano no import, então um plano
fora de sincronia aparece como erro de import — e não só no DAG processor.
"""

import re
from pathlib import Path

import pytest
from airflow.models import DagBag

pytestmark = pytest.mark.unit

RAIZ = Path(__file__).resolve().parents[2]
DAGS = RAIZ / "airflow" / "dags"
PUBLICACAO = DAGS / "data_publish"
RELATORIOS = DAGS / "data_report"

TAG_FORMAT = re.compile(r"^[a-z_]+:[a-z0-9_]+$")
# ADR-0008: vocabulário fixo de dimensões.
DIMENSOES = {"sistema", "orgao", "camada", "dominio"}


@pytest.fixture(scope="module")
def dagbag_publicacao() -> DagBag:
    return DagBag(dag_folder=str(PUBLICACAO), include_examples=False)


@pytest.fixture(scope="module")
def dagbag_relatorios() -> DagBag:
    return DagBag(dag_folder=str(RELATORIOS), include_examples=False)


class TestIntegridade:
    def test_publicacao_sem_erro_de_import(self, dagbag_publicacao: DagBag) -> None:
        assert dagbag_publicacao.import_errors == {}, dagbag_publicacao.import_errors

    def test_relatorios_sem_erro_de_import(self, dagbag_relatorios: DagBag) -> None:
        assert dagbag_relatorios.import_errors == {}, dagbag_relatorios.import_errors

    def test_dag_ids_correspondem_aos_nomes_dos_arquivos(
        self, dagbag_publicacao: DagBag, dagbag_relatorios: DagBag
    ) -> None:
        assert set(dagbag_publicacao.dags) == {
            p.stem for p in PUBLICACAO.rglob("*_publish_dag.py")
        }
        assert set(dagbag_relatorios.dags) == {
            p.stem for p in RELATORIOS.rglob("*_report_dag.py")
        }

    @pytest.mark.parametrize(
        "pasta,sufixo", [(PUBLICACAO, "_publish_dag"), (RELATORIOS, "_report_dag")]
    )
    def test_arquivo_fica_em_pasta_de_orgao(self, pasta: Path, sufixo: str) -> None:
        """ADR-0019: quem publica é sempre um órgão."""
        for caminho in pasta.rglob(f"*{sufixo}.py"):
            orgao = caminho.parent.name
            assert (
                caminho.parent.parent == pasta
            ), f"{caminho} deve estar em <pasta>/<orgao>/"
            assert caminho.stem.endswith(
                f"{orgao}{sufixo}"
            ), f"{caminho.name} deve conter o órgão '{orgao}' no nome"

    def test_pastas_estao_no_dag_selector(self) -> None:
        """Sem entrada no dag_selector (ADR-0005) o deployment não carrega a DAG."""
        selector = (DAGS / "dag_selector").read_text(encoding="utf-8")
        for caminho in list(PUBLICACAO.iterdir()) + list(RELATORIOS.iterdir()):
            if not caminho.is_dir():
                continue
            esperado = f"{caminho.parent.name}/{caminho.name}/"
            assert esperado in selector, f"{esperado} ausente do dag_selector"


class TestMetadados:
    @pytest.fixture(params=["dagbag_publicacao", "dagbag_relatorios"])
    def dagbag(self, request) -> DagBag:
        return request.getfixturevalue(request.param)

    def test_todas_tem_description(self, dagbag: DagBag) -> None:
        sem = [i for i, d in dagbag.dags.items() if not d.description]
        assert not sem, f"DAGs sem description: {sem}"

    def test_tags_seguem_o_vocabulario_do_adr_0008(self, dagbag: DagBag) -> None:
        for dag_id, dag in dagbag.dags.items():
            for tag in dag.tags:
                assert TAG_FORMAT.match(tag), f"{dag_id}: tag fora do formato — {tag}"
                assert (
                    tag.split(":", 1)[0] in DIMENSOES
                ), f"{dag_id}: dimensão desconhecida — {tag}"

    def test_todas_tem_tag_de_orgao(self, dagbag: DagBag) -> None:
        sem = [
            i
            for i, d in dagbag.dags.items()
            if not any(t.startswith("orgao:") for t in d.tags)
        ]
        assert not sem, f"DAGs de publicação sem tag orgao:: {sem}"

    def test_todas_tem_owner(self, dagbag: DagBag) -> None:
        sem = [i for i, d in dagbag.dags.items() if not d.default_args.get("owner")]
        assert not sem, f"DAGs sem owner em default_args: {sem}"


class TestDagDePublicacaoDoMgi:
    def test_ordem_importar_papeis_recortes(self, dagbag_publicacao: DagBag) -> None:
        """Papel sobre dataset que ainda não existe seria papel que não vê nada."""
        dag = dagbag_publicacao.dags["mgi_publish_dag"]
        tarefas = {t.task_id for t in dag.tasks}
        assert {
            "listar_bundles",
            "importar_bundle",
            "aplicar_papeis",
            "aplicar_recortes",
        } <= tarefas

        papeis = dag.get_task("aplicar_papeis")
        assert "importar_bundle" in papeis.upstream_task_ids
        assert "aplicar_papeis" in dag.get_task("aplicar_recortes").upstream_task_ids


class TestDagDeRelatorioDoMgi:
    def test_entrega_e_mapeada_por_consumidor(self, dagbag_relatorios: DagBag) -> None:
        dag = dagbag_relatorios.dags["contratacoes_mgi_report_dag"]
        entregar = dag.get_task("entregar")
        assert "listar_entregas" in entregar.upstream_task_ids
        # Uma entrega por consumidor: sem o mapeamento, a falha de um órgão
        # refaria o relatório de todos.
        assert getattr(entregar, "is_mapped", False)
