"""DAG de transformação do projeto dbt do MIR (ADR-0018).

Executa o projeto dbt do órgão — a Silver dos pacotes de sistema estruturante
que ele consome (contratos_gov, tesouro_gerencial) e a Gold que ele próprio materializa —
com uma task do Airflow por nó do grafo dbt, via Cosmos.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from cosmos import DbtDag, ProfileConfig, ProjectConfig, RenderConfig
from cosmos.constants import TestBehavior

ORGAO = "mir"

# airflow/dags/data_transform/<orgao>/<arquivo>.py -> airflow/dags/dbt
DIR_DBT = Path(__file__).resolve().parents[2] / "dbt"

default_args = {
    "owner": ORGAO,
    "queue": ORGAO,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

perfil = ProfileConfig(
    profile_name="gov_bricks",
    target_name=os.environ.get("DBT_TARGET", "dev"),
    profiles_yml_filepath=DIR_DBT / "profiles.yml",
)

mir_transform_dag = DbtDag(
    dag_id=f"{ORGAO}_transform_dag",
    project_config=ProjectConfig(
        dbt_project_path=DIR_DBT / ORGAO,
        env_vars={"GOV_BRICKS_DBT_DIR": str(DIR_DBT)},
    ),
    profile_config=perfil,
    render_config=RenderConfig(
        test_behavior=TestBehavior.AFTER_EACH,
    ),
    schedule="0 6 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Materializa Silver e Gold do projeto dbt do MIR, uma task por modelo "
        "(Cosmos, ADR-0018)."
    ),
    tags=[
        "orgao:mir",
        "sistema:contratos_gov",
        "sistema:tesouro_gerencial",
        "sistema:camara_deputados",
        "sistema:senado_federal",
        "camada:silver",
        "camada:gold",
    ],
)
