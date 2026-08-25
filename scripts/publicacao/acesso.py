"""Plano de acesso derivado do catálogo de publicação (ADR-0020).

Ninguém cria papel na mão no Superset. Cada consumidor declarado em
``catalogo/publicacao/<orgao>.yml`` vira um papel — com os datasets que ele
alcança e, quando não tem abrangência total, um filtro de recorte por órgão. O
plano é escrito em ``airflow/dags/superset/<orgao>/acesso.yml``, ao alcance da
DAG de publicação, e verificado no CI como qualquer outro artefato derivado:
editar o arquivo gerado à mão não muda nada, porque a próxima geração o desfaz.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from ..modelagem.gerador import Escrita, _escrever
from . import bundle as bundle_mod
from . import dbt_meta
from .catalogo import (
    CatalogoPublicacao,
    Publicacao,
    mais_restritiva,
)

CABECALHO = """\
# GERADO por `make publicacao-sync` a partir de catalogo/publicacao/{orgao}.yml
# e catalogo/acesso.yml. Não edite à mão — a edição é desfeita na próxima
# geração, e o CI reprova o build quando este arquivo diverge do catálogo.
#
# A DAG {orgao}_publish_dag lê este plano e o aplica no Superset: cria os
# papéis, concede a cada um os datasets que ele alcança e instala o recorte de
# linhas de quem não tem abrangência total (ADR-0019, ADR-0020).
"""


@dataclass(frozen=True)
class DatasetPlano:
    """Um dataset publicado, com o que se sabe sobre o que ele expõe."""

    id: str
    schema: str
    tabela: str
    nivel: str
    recorte: bool
    colunas: tuple[str, ...]
    # A mais restritiva entre as classificações das colunas expostas, segundo o
    # schema.yml do modelo. Coluna não documentada não entra na conta — a
    # validação é que reporta a lacuna.
    classificacao_efetiva: str

    @property
    def qualificado(self) -> str:
        return f"{self.schema}.{self.tabela}" if self.schema else self.tabela


@dataclass(frozen=True)
class PapelPlano:
    """Um papel do Superset e o que ele alcança."""

    nome: str
    consumidor: str
    nivel: str
    herda: str
    datasets: tuple[str, ...]
    dashboards: tuple[str, ...]


@dataclass(frozen=True)
class RecortePlano:
    """Um filtro de linhas (RLS) aplicado a um papel."""

    nome: str
    papel: str
    clausula: str
    datasets: tuple[str, ...]


@dataclass(frozen=True)
class EntregaPlano:
    """Uma cópia do relatório, com o recorte de um consumidor."""

    consumidor: str
    # Cláusula SQL de recorte, ou None quando o consumidor tem abrangência
    # total. É o mesmo recorte da dashboard: o relatório não é uma porta dos
    # fundos para o que o papel não veria no Superset.
    clausula: str | None


@dataclass(frozen=True)
class RelatorioPlano:
    """Um relatório periódico e para quem ele é gerado."""

    id: str
    dag: str
    dataset: str
    formato: str
    destinos: tuple[str, ...]
    nivel: str
    destinatarios_variavel: str | None
    entregas: tuple[EntregaPlano, ...]


@dataclass(frozen=True)
class Plano:
    """O plano de acesso de um órgão publicador."""

    orgao: str
    database: str
    papel_herda: str
    datasets: tuple[DatasetPlano, ...]
    papeis: tuple[PapelPlano, ...]
    recortes: tuple[RecortePlano, ...]
    relatorios: tuple[RelatorioPlano, ...]
    bundles: tuple[str, ...]


def _dataset_plano(
    publicacao: Publicacao, id_dataset: str, dir_dbt: Path | None = None
) -> DatasetPlano:
    dataset = publicacao.datasets[id_dataset]
    colunas: tuple[str, ...] = ()
    schema = ""

    for id_dash in sorted(publicacao.dashboards):
        dashboard = publicacao.dashboards[id_dash]
        if id_dataset not in dashboard.datasets:
            continue
        lido = bundle_mod.carregar(
            publicacao.dir_bundles / dashboard.bundle, dashboard.bundle
        )
        encontrado = lido.dataset(id_dataset) if lido else None
        if encontrado:
            colunas = encontrado.colunas
            schema = encontrado.schema
            break

    modelo = dbt_meta.carregar_modelo(publicacao.orgao, dataset.modelo, dir_dbt)
    classificacoes = [
        modelo.classificacao_de(coluna)
        for coluna in colunas
        if modelo and modelo.classificacao_de(coluna)
    ]

    return DatasetPlano(
        id=id_dataset,
        schema=schema,
        tabela=id_dataset,
        nivel=dataset.nivel,
        recorte=dataset.recorte,
        colunas=colunas,
        classificacao_efetiva=mais_restritiva([c for c in classificacoes if c]),
    )


def montar(
    catalogo: CatalogoPublicacao, id_orgao: str, dir_dbt: Path | None = None
) -> Plano:
    """Monta o plano de acesso de um órgão a partir do catálogo."""
    publicacao = catalogo.orgao(id_orgao)
    acesso = catalogo.acesso

    datasets = tuple(
        _dataset_plano(publicacao, id_dataset, dir_dbt)
        for id_dataset in sorted(publicacao.datasets)
    )
    por_id = {dataset.id: dataset for dataset in datasets}

    papeis: list[PapelPlano] = []
    recortes: list[RecortePlano] = []

    for id_consumidor in sorted(publicacao.consumidores):
        consumidor = publicacao.consumidores[id_consumidor]

        alcancados: list[str] = []
        dashboards: list[str] = []
        for id_dash in consumidor.dashboards:
            dashboard = publicacao.dashboards.get(id_dash)
            if dashboard is None:
                continue
            dashboards.append(dashboard.bundle)
            alcancados += [d for d in dashboard.datasets if d in por_id]

        nome_papel = acesso.papel(id_consumidor, consumidor.nivel)
        qualificados = tuple(sorted({por_id[d].qualificado for d in alcancados}))
        papeis.append(
            PapelPlano(
                nome=nome_papel,
                consumidor=id_consumidor,
                nivel=consumidor.nivel,
                herda=acesso.papel_herda,
                datasets=qualificados,
                dashboards=tuple(sorted(set(dashboards))),
            )
        )

        # Sem recorte, um instituto que ganha acesso a um produto federado passa
        # a ver a execução de todos os demais órgãos.
        com_recorte = tuple(
            sorted({por_id[d].qualificado for d in alcancados if por_id[d].recorte})
        )
        if consumidor.tem_recorte and com_recorte:
            recortes.append(
                RecortePlano(
                    nome=acesso.filtro_recorte(id_consumidor),
                    papel=nome_papel,
                    clausula=f"{acesso.chave_recorte} = '{consumidor.codigo_orgao}'",
                    datasets=com_recorte,
                )
            )

    relatorios = tuple(
        RelatorioPlano(
            id=id_rel,
            dag=relatorio.dag,
            dataset=relatorio.dataset,
            formato=relatorio.formato,
            destinos=relatorio.destinos,
            nivel=relatorio.nivel,
            destinatarios_variavel=relatorio.destinatarios_variavel,
            entregas=tuple(
                EntregaPlano(
                    consumidor=id_consumidor,
                    clausula=(
                        f"{acesso.chave_recorte} = "
                        f"'{publicacao.consumidores[id_consumidor].codigo_orgao}'"
                        if publicacao.consumidores[id_consumidor].tem_recorte
                        else None
                    ),
                )
                for id_consumidor in sorted(publicacao.consumidores)
                if id_rel in publicacao.consumidores[id_consumidor].relatorios
            ),
        )
        for id_rel, relatorio in sorted(publicacao.relatorios.items())
    )

    return Plano(
        orgao=publicacao.orgao,
        database=publicacao.database,
        papel_herda=acesso.papel_herda,
        datasets=datasets,
        papeis=tuple(papeis),
        recortes=tuple(recortes),
        relatorios=relatorios,
        bundles=tuple(
            sorted({d.bundle for d in publicacao.dashboards.values() if d.bundle})
        ),
    )


def renderizar(plano: Plano) -> str:
    """O plano como YAML, do jeito que a DAG de publicação o lê."""
    documento = {
        "orgao": plano.orgao,
        "database": plano.database,
        "papel_herda": plano.papel_herda,
        "bundles": list(plano.bundles),
        "datasets": [
            {
                "id": dataset.id,
                "schema": dataset.schema,
                "tabela": dataset.tabela,
                "nivel": dataset.nivel,
                "recorte": dataset.recorte,
                "classificacao_efetiva": dataset.classificacao_efetiva,
                "colunas": list(dataset.colunas),
            }
            for dataset in plano.datasets
        ],
        "papeis": [
            {
                "nome": papel.nome,
                "consumidor": papel.consumidor,
                "nivel": papel.nivel,
                "herda": papel.herda,
                "datasets": list(papel.datasets),
                "dashboards": list(papel.dashboards),
            }
            for papel in plano.papeis
        ],
        "recortes": [
            {
                "nome": recorte.nome,
                "papel": recorte.papel,
                "clausula": recorte.clausula,
                "datasets": list(recorte.datasets),
            }
            for recorte in plano.recortes
        ],
        "relatorios": [
            {
                "id": relatorio.id,
                "dag": relatorio.dag,
                "dataset": relatorio.dataset,
                "formato": relatorio.formato,
                "destinos": list(relatorio.destinos),
                "nivel": relatorio.nivel,
                "destinatarios_variavel": relatorio.destinatarios_variavel,
                "entregas": [
                    {"consumidor": entrega.consumidor, "clausula": entrega.clausula}
                    for entrega in relatorio.entregas
                ],
            }
            for relatorio in plano.relatorios
        ],
    }
    corpo = yaml.safe_dump(
        documento, sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    return CABECALHO.format(orgao=plano.orgao) + "\n" + corpo


def caminho_plano(catalogo: CatalogoPublicacao, id_orgao: str) -> Path:
    return catalogo.orgao(id_orgao).caminho_plano


def sincronizar(
    catalogo: CatalogoPublicacao, dir_dbt: Path | None = None
) -> list[Escrita]:
    """Regrava o plano de acesso de todos os órgãos catalogados."""
    escritas: list[Escrita] = []
    for id_orgao in sorted(catalogo.orgaos):
        plano = montar(catalogo, id_orgao, dir_dbt)
        destino = catalogo.orgao(id_orgao).caminho_plano
        escritas.append(_escrever(destino, renderizar(plano), forcar=True))
    return escritas


def dessincronizados(
    catalogo: CatalogoPublicacao, dir_dbt: Path | None = None
) -> list[str]:
    """Órgãos cujo plano no disco não corresponde ao catálogo atual."""
    fora: list[str] = []
    for id_orgao in sorted(catalogo.orgaos):
        destino = catalogo.orgao(id_orgao).caminho_plano
        esperado = renderizar(montar(catalogo, id_orgao, dir_dbt))
        if not destino.is_file() or destino.read_text(encoding="utf-8") != esperado:
            fora.append(id_orgao)
    return fora


def render_matriz(catalogo: CatalogoPublicacao) -> str:
    """A matriz de acesso em texto: quem vê o quê, e com que recorte."""
    linhas = ["MATRIZ DE ACESSO — quem enxerga o quê (ADR-0020)", ""]
    for id_orgao in sorted(catalogo.orgaos):
        publicacao = catalogo.orgao(id_orgao)
        plano = montar(catalogo, id_orgao)
        recorte_por_papel = {r.papel: r for r in plano.recortes}
        linhas.append(f"  {publicacao.orgao} — {publicacao.nome}")
        linhas.append(f"    database: {plano.database or '(não declarado)'}")
        for dataset in plano.datasets:
            marca = "recorte por órgão" if dataset.recorte else "sem recorte"
            linhas.append(
                f"    dataset {dataset.qualificado} "
                f"[nível {dataset.nivel}, colunas até {dataset.classificacao_efetiva}, {marca}]"
            )
        linhas.append("")
        for papel in plano.papeis:
            consumidor = publicacao.consumidores[papel.consumidor]
            linhas.append(
                f"    papel {papel.nome}  ({consumidor.nome or papel.consumidor})"
            )
            linhas.append(
                f"      nível {papel.nivel}: vê "
                f"{', '.join(catalogo.acesso.nivel(papel.nivel).ve_classificacoes)}"
            )
            recorte = recorte_por_papel.get(papel.nome)
            linhas.append(
                f"      linhas: {recorte.clausula}"
                if recorte
                else "      linhas: todas (abrangência total)"
            )
            linhas.append(f"      dashboards: {', '.join(papel.dashboards) or 'nenhuma'}")
            linhas.append(f"      datasets: {', '.join(papel.datasets) or 'nenhum'}")
            recebidos = [
                relatorio.id
                for relatorio in plano.relatorios
                if any(e.consumidor == papel.consumidor for e in relatorio.entregas)
            ]
            linhas.append(f"      relatórios: {', '.join(recebidos) or 'nenhum'}")
            linhas.append("")
    return "\n".join(linhas)
