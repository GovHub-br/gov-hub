import csv
import io
import logging
import zipfile
from typing import Iterator, List, Optional

import requests


class ClienteSiconv:
    """Cliente de extração dos dados abertos do SICONV.

    Migrado de data-application-mir (``airflow_lappis/plugins/cliente_siconv.py``).
    Baixa um único ``.zip`` nacional — a fonte não tem nenhum filtro de órgão
    (ADR-0004: SICONV é 100% genérico/nacional) — e lê cada CSV de dentro dele
    em streaming, sem carregar o arquivo inteiro em memória.

    Agnóstica de motor de persistência (ADR-0011): só baixa o zip e devolve
    registros como ``dict``; quem grava é a DAG, via ``landing_zone.write_raw``.
    """

    URL_ZIP = "https://repositorio.dados.gov.br/seges/detru/siconv.zip"
    ENCODING = "utf-8-sig"
    DELIMITER = ";"

    def __init__(self, zip_path: str = "/tmp/siconv.zip") -> None:
        self.zip_path = zip_path

    def baixar_zip(self) -> str:
        logging.info(
            "[cliente_siconv.py] Baixando arquivo SICONV de %s ...", self.URL_ZIP
        )
        response = requests.get(self.URL_ZIP, stream=True)
        response.raise_for_status()
        with open(self.zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logging.info("[cliente_siconv.py] Download concluído em %s", self.zip_path)
        return self.zip_path

    def ler_csv(
        self,
        nome_csv: str,
        skip_rows: int = 0,
        colunas_esperadas: Optional[List[str]] = None,
    ) -> Iterator[dict]:
        logging.info("[cliente_siconv.py] Lendo %s em modo streaming...", nome_csv)
        with zipfile.ZipFile(self.zip_path, "r") as z:
            with z.open(nome_csv) as f:
                conteudo = io.TextIOWrapper(f, encoding=self.ENCODING)
                reader = csv.DictReader(conteudo, delimiter=self.DELIMITER)

                if colunas_esperadas:
                    colunas_csv = reader.fieldnames or []
                    faltando = [c for c in colunas_esperadas if c not in colunas_csv]
                    if faltando:
                        raise ValueError(
                            f"[cliente_siconv.py] Colunas faltando em {nome_csv}: "
                            f"{faltando}"
                        )

                for i, row in enumerate(reader):
                    if i < skip_rows:
                        continue

                    if colunas_esperadas:
                        yield {k.lower(): row[k] for k in colunas_esperadas}
                    else:
                        yield {k.lower(): v for k, v in row.items() if k is not None}
