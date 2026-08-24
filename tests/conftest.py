import os
import sys

# O Cosmos guarda o resultado do `dbt ls` em uma Variable do Airflow, para não
# reinspecionar o projeto dbt a cada parsing (ADR-0018). Em teste não há metadata
# database, e a escrita da Variable derrubaria o import da DAG de transformação.
# Sem cache o grafo é montado na hora — mais lento, mas é o que se quer no teste.
os.environ.setdefault("AIRFLOW__COSMOS__ENABLE_CACHE", "False")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../airflow/plugins")),
)
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../airflow/helpers")),
)
