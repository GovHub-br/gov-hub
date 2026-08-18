from pathlib import Path

import pytest

from dag_discovery import DagSelector

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_selector(tmp_path: Path, content: str | None) -> DagSelector:
    if content is not None:
        (tmp_path / "dag_selector").write_text(content, encoding="utf-8")
    return DagSelector(dags_folder=tmp_path)


# ---------------------------------------------------------------------------
# DagSelector.is_included
# ---------------------------------------------------------------------------


class TestDagSelectorIsIncluded:
    def test_missing_file_includes_everything(self, tmp_path: Path) -> None:
        selector = _make_selector(tmp_path, content=None)

        assert selector.is_included(tmp_path / "data_ingest" / "anything.py")

    def test_wildcard_marker_includes_everything(self, tmp_path: Path) -> None:
        selector = _make_selector(tmp_path, content="*\n")

        assert selector.is_included(tmp_path / "data_ingest" / "anything.py")

    def test_comments_and_blank_lines_are_ignored(self, tmp_path: Path) -> None:
        content = "\n# comment\n\ndata_ingest/ibge/\n"
        selector = _make_selector(tmp_path, content=content)

        assert selector.is_included(tmp_path / "data_ingest" / "ibge" / "dag.py")
        assert not selector.is_included(tmp_path / "data_ingest" / "cnpq" / "dag.py")

    def test_included_folder_does_not_propagate_to_subfolder(
        self, tmp_path: Path
    ) -> None:
        content = "data_ingest/compras_gov/\n"
        selector = _make_selector(tmp_path, content=content)

        assert selector.is_included(tmp_path / "data_ingest" / "compras_gov" / "dag.py")
        assert not selector.is_included(
            tmp_path / "data_ingest" / "compras_gov" / "mir" / "dag.py"
        )

    def test_explicitly_declared_subfolder_is_included(self, tmp_path: Path) -> None:
        content = "data_ingest/compras_gov/mir/\n"
        selector = _make_selector(tmp_path, content=content)

        assert selector.is_included(
            tmp_path / "data_ingest" / "compras_gov" / "mir" / "dag.py"
        )
        assert not selector.is_included(
            tmp_path / "data_ingest" / "compras_gov" / "other_org" / "dag.py"
        )

    def test_file_outside_dags_folder_is_not_filtered(self, tmp_path: Path) -> None:
        content = "data_ingest/ibge/\n"
        selector = _make_selector(tmp_path, content=content)

        outside_path = tmp_path.parent / "outside_dags" / "file.py"
        assert selector.is_included(outside_path)

    def test_reloads_after_file_change(self, tmp_path: Path) -> None:
        selector_file = tmp_path / "dag_selector"
        selector_file.write_text("data_ingest/ibge/\n", encoding="utf-8")
        selector = DagSelector(dags_folder=tmp_path)

        assert not selector.is_included(tmp_path / "data_ingest" / "cnpq" / "dag.py")

        selector_file.write_text("data_ingest/cnpq/\n", encoding="utf-8")

        assert selector.is_included(tmp_path / "data_ingest" / "cnpq" / "dag.py")
        assert not selector.is_included(tmp_path / "data_ingest" / "ibge" / "dag.py")
