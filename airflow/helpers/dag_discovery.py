from __future__ import annotations

import logging
import os
import re
import threading
import zipfile
from pathlib import Path, PurePosixPath

from airflow.configuration import conf

# A heurística padrão do Airflow, importada pelo nome dela.
#
# NÃO troque por `might_contain_dag`: no Airflow 3 essa função é o *despachante*
# que lê `core.might_contain_dag_callable` — que aponta para esta aqui. Chamá-la
# daqui faz o processador de DAGs recursar até estourar a pilha, e o efeito é o
# pior possível: nenhum arquivo é considerado, nenhuma DAG aparece, e o erro só
# se manifesta com Airflow rodando.
from airflow.utils.file import might_contain_dag_via_default_heuristic

log = logging.getLogger(__name__)

SELECTOR_FILENAME = "dag_selector"

# Caminho alternativo para o arquivo de allowlist (ADR-0005).
#
# O ADR pede que cada deployment de órgão declare a própria allowlist,
# "validada no manifesto/Helm". Sem esta variável isso é impossível: o arquivo
# só podia vir de `<dags_folder>/dag_selector`, que no deployment é conteúdo do
# repositório clonado — igual para todo mundo que sincroniza a mesma branch.
# Com ela, o deployment monta o próprio arquivo (ConfigMap, por exemplo) em um
# caminho qualquer e aponta o env para lá.
SELECTOR_PATH_ENVVAR = "GOVHUB_DAG_SELECTOR"

# Special line that includes everything
INCLUDE_ALL_MARKER = "*"


class DagSelector:
    """
    Reads and interprets the `dag_selector` file, exposing `is_included(path)`.

    The file is reloaded automatically whenever its mtime changes, so tests
    and the DAG Processor itself don't need a process restart to pick up an
    updated allowlist.
    """

    def __init__(self, dags_folder: str | os.PathLike | None = None) -> None:
        self._dags_folder = Path(dags_folder) if dags_folder else None
        self._lock = threading.Lock()
        self._mtime: float | None = None
        self._include_all = True
        self._patterns: list[re.Pattern[str]] = []

    @property
    def dags_folder(self) -> Path:
        if self._dags_folder is None:
            self._dags_folder = Path(conf.get("core", "dags_folder"))
        return self._dags_folder

    @property
    def selector_path(self) -> Path:
        override = os.environ.get(SELECTOR_PATH_ENVVAR)
        if override:
            return Path(override)
        return self.dags_folder / SELECTOR_FILENAME

    def _reload_if_needed(self) -> None:
        path = self.selector_path

        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            log.warning(
                "dag_selector file not found at %s; including every DAG file "
                "(backward-compatible default).",
                path,
            )
            with self._lock:
                self._include_all = True
                self._patterns = []
                self._mtime = None
            return

        if mtime == self._mtime:
            return

        with self._lock:
            include_all, patterns = self._parse(path)
            self._include_all = include_all
            self._patterns = patterns
            self._mtime = mtime

        log.info(
            "dag_selector reloaded from %s: include_all=%s, %d pattern(s).",
            path,
            include_all,
            len(patterns),
        )

    @staticmethod
    def _parse(path: Path) -> tuple[bool, list[re.Pattern[str]]]:
        patterns: list[re.Pattern[str]] = []
        include_all = False

        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()

            if not line or line.startswith("#"):
                continue

            if line == INCLUDE_ALL_MARKER:
                include_all = True
                continue

            patterns.append(re.compile(line))

        return include_all, patterns

    @staticmethod
    def _matches_without_deeper_subfolder(
        pattern: re.Pattern[str], relative_str: str
    ) -> bool:
        match = pattern.search(relative_str)
        if not match:
            return False

        remainder = relative_str[match.end() :].lstrip("/")
        return "/" not in remainder

    def is_included(self, file_path: str | os.PathLike) -> bool:
        self._reload_if_needed()

        if self._include_all:
            return True

        try:
            relative = PurePosixPath(
                Path(file_path).resolve().relative_to(self.dags_folder.resolve())
            )
        except ValueError:
            log.warning(
                "%s is outside of dags_folder (%s); skipping dag_selector "
                "filtering for it.",
                file_path,
                self.dags_folder,
            )
            return True

        relative_str = str(relative)
        return any(
            self._matches_without_deeper_subfolder(pattern, relative_str)
            for pattern in self._patterns
        )


_dag_selector: DagSelector | None = None
_dag_selector_lock = threading.Lock()


def _get_dag_selector() -> DagSelector:
    global _dag_selector

    if _dag_selector is None:
        with _dag_selector_lock:
            if _dag_selector is None:
                _dag_selector = DagSelector()

    return _dag_selector


def might_contain_selected_dag(
    file_path: str, zip_file: zipfile.ZipFile | None = None
) -> bool:
    """Callable de `core.might_contain_dag_callable` (ADR-0005).

    O Airflow só chama este callable com `dag_discovery_safe_mode` ligado —
    desligado, ele devolve True antes de chegar aqui. Por isso a heurística
    padrão é aplicada direto, sem repassar `safe_mode`.
    """
    if not might_contain_dag_via_default_heuristic(file_path, zip_file):
        return False

    return _get_dag_selector().is_included(file_path)
