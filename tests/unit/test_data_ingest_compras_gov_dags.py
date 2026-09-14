import re
from pathlib import Path

import pytest
from airflow.models import DagBag

pytestmark = pytest.mark.unit

DAGS_FOLDER = (
    Path(__file__).resolve().parents[2]
    / "airflow"
    / "dags"
    / "data_ingest"
    / "compras_gov"
)

TAG_FORMAT = re.compile(r"^[a-z_]+:[a-z0-9_]+$")


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag(dag_folder=str(DAGS_FOLDER), include_examples=False)


class TestComprasGovDagsIntegrity:
    def test_no_import_errors(self, dagbag: DagBag) -> None:
        assert dagbag.import_errors == {}, dagbag.import_errors

    def test_expected_number_of_dags_loaded(self, dagbag: DagBag) -> None:
        # 23 compartilhadas na raiz do sistema + 1 do recorte do MIR em
        # compras_gov/mir/ (caso 2 da ADR-0004: sistema compartilhado, código
        # específico de um órgão).
        assert len(dagbag.dags) == 24

    def test_dag_ids_match_filenames(self, dagbag: DagBag) -> None:
        # rglob e não glob: o DagBag varre recursivamente, então as subpastas
        # de órgão previstas na ADR-0004 também entram. Com glob simples, a
        # primeira subpasta de órgão criada quebraria este teste.
        py_files = {p.stem for p in DAGS_FOLDER.rglob("*.py")}
        loaded_ids = set(dagbag.dags.keys())
        assert loaded_ids == py_files

    def test_all_dag_ids_end_with_ingest_dag(self, dagbag: DagBag) -> None:
        for dag_id in dagbag.dags:
            assert dag_id.endswith("_ingest_dag"), dag_id

    def test_all_dags_have_description(self, dagbag: DagBag) -> None:
        missing = [dag_id for dag_id, dag in dagbag.dags.items() if not dag.description]
        assert not missing, f"DAGs sem description: {missing}"

    def test_all_tags_follow_adr_0008_format(self, dagbag: DagBag) -> None:
        violations = {}
        for dag_id, dag in dagbag.dags.items():
            bad_tags = [t for t in dag.tags if not TAG_FORMAT.match(t)]
            if bad_tags:
                violations[dag_id] = bad_tags
        assert not violations, f"Tags fora do formato dimensao:valor: {violations}"

    def test_all_dags_have_sistema_tag(self, dagbag: DagBag) -> None:
        missing = [
            dag_id
            for dag_id, dag in dagbag.dags.items()
            if not any(t.startswith("sistema:") for t in dag.tags)
        ]
        assert not missing, f"DAGs sem tag sistema:: {missing}"

    def test_all_dags_have_owner(self, dagbag: DagBag) -> None:
        missing = [
            dag_id
            for dag_id, dag in dagbag.dags.items()
            if not dag.default_args.get("owner")
        ]
        assert not missing, f"DAGs sem owner em default_args: {missing}"
