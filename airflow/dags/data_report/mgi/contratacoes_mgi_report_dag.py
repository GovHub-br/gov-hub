"""Relatório mensal de contratações do MGI (ADR-0019).

Entrega, a cada órgão consumidor declarado em catalogo/publicacao/mgi.yml, o
extrato de contratos do seu próprio recorte. A consulta é escrita uma vez; o
filtro por órgão vem do plano de acesso, o mesmo que governa a dashboard.
"""

from __future__ import annotations

from pathlib import Path

from relatorio_dag_factory import build_relatorio_dag

ORGAO = "mgi"
RELATORIO = "contratacoes_mensal"

# airflow/dags/data_report/<orgao>/<arquivo>.py -> airflow/dags/superset/<orgao>
CAMINHO_PLANO = Path(__file__).resolve().parents[2] / "superset" / ORGAO / "acesso.yml"

# As colunas são as mesmas expostas no dataset publicado: o relatório não é uma
# porta dos fundos para coluna que a dashboard não mostra (ADR-0020).
CONSULTA = """
    select co_orgao, co_uasg, nu_ni, numerocontrato, dt_ingest
    from "003_gld_contratacoes".contratos_por_orgao
    where {recorte}
    order by co_orgao, co_uasg, numerocontrato
"""

contratacoes_mgi_report_dag = build_relatorio_dag(
    dag_id="contratacoes_mgi_report_dag",
    orgao=ORGAO,
    relatorio=RELATORIO,
    titulo="Contratações do mês",
    consulta=CONSULTA,
    caminho_plano=CAMINHO_PLANO,
    # Todo dia 1º, depois da janela de transformação.
    schedule="0 7 1 * *",
    description=(
        "Entrega a cada órgão consumidor o extrato mensal de contratos do seu "
        "recorte, na landing zone e por e-mail (ADR-0019)."
    ),
    tags=["orgao:mgi", "sistema:compras_gov", "camada:gold", "dominio:contratacoes"],
)
