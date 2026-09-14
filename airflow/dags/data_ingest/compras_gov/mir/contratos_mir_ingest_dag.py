"""Ingestão do compras_gov específica do MIR (ADR-0004).

MOCK de time. Vive em `data_ingest/<sistema>/<orgao>/` porque é o caso 2 da
ADR-0004: o sistema é compartilhado, mas este recorte só faz sentido para um
órgão. Existe para validar que o `dag_selector` (ADR-0005) inclui a pasta do
sistema sem arrastar as subpastas de órgão junto.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.sdk import dag, task

SISTEMA = "compras_gov"
ORGAO = "mir"

default_args = {
    "owner": ORGAO,
    "queue": ORGAO,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    dag_id=f"contratos_{ORGAO}_ingest_dag",
    schedule="0 1 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    description="MOCK: recorte de contratos do compras_gov específico do MIR.",
    tags=[f"sistema:{SISTEMA}", f"orgao:{ORGAO}", "dominio:contratacoes"],
)
def contratos_mir_dag() -> None:
    @task
    def extrair() -> int:
        """Substitui a chamada real à API; devolve uma contagem simbólica."""
        return 0

    extrair()


contratos_mir_dag()
