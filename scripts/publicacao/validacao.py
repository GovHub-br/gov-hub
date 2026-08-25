"""Validação do catálogo de publicação (ADR-0019, ADR-0020).

Duas perguntas são respondidas aqui, e as duas são caras de responder tarde:

1. *O que está publicado é o que foi declarado?* O bundle exportado do Superset
   é um artefato editado em outra ferramenta — nada impede que alguém arraste
   para a dashboard uma coluna que o catálogo não previu. A validação compara
   um com o outro.
2. *Alguém enxerga mais do que o nível dele permite?* A classificação de cada
   coluna vem do ``schema.yml`` do modelo (ADR-0013); o nível de cada
   consumidor vem do catálogo. Cruzar os dois é o que transforma nível de
   acesso declarado em nível de acesso verificado.

Como no catálogo de modelagem, `erro` reprova o CI e `aviso` apenas sinaliza.
"""

from __future__ import annotations

from pathlib import Path

from ..modelagem.catalogo import (
    CLASSIFICACOES,
    PADRAO_IDENTIFICADOR,
    RAIZ,
    ErroCatalogo,
    Problema,
)
from ..modelagem.catalogo import carregar as carregar_modelagem
from . import acesso as acesso_mod
from . import bundle as bundle_mod
from . import dbt_meta
from .catalogo import (
    ABRANGENCIAS,
    DESTINOS,
    DIR_PUBLICACAO,
    FORMATOS,
    CatalogoPublicacao,
    Publicacao,
)


def _relativo(caminho: Path) -> str:
    """Caminho relativo à raiz do repositório, para a mensagem ficar acionável."""
    try:
        return str(caminho.relative_to(RAIZ))
    except ValueError:
        return str(caminho)


def _erro(onde: str, mensagem: str) -> Problema:
    return Problema(nivel="erro", onde=onde, mensagem=mensagem)


def _aviso(onde: str, mensagem: str) -> Problema:
    return Problema(nivel="aviso", onde=onde, mensagem=mensagem)


def tem_erro(problemas: list[Problema]) -> bool:
    return any(p.nivel == "erro" for p in problemas)


def validar(
    catalogo: CatalogoPublicacao,
    dir_publicacao: Path | None = None,
    dir_dbt: Path | None = None,
) -> list[Problema]:
    """Valida o catálogo de publicação inteiro."""
    problemas: list[Problema] = []
    problemas += _validar_acesso(catalogo)
    if not catalogo.orgaos:
        problemas.append(
            _aviso("catalogo/publicacao/", "nenhum órgão publica nada ainda.")
        )
    for id_orgao in sorted(catalogo.orgaos):
        problemas += _validar_orgao(
            catalogo,
            catalogo.orgaos[id_orgao],
            dir_publicacao or DIR_PUBLICACAO,
            dir_dbt,
        )
    return problemas


# --------------------------------------------------------------------------
# Níveis de acesso
# --------------------------------------------------------------------------


def _validar_acesso(catalogo: CatalogoPublicacao) -> list[Problema]:
    problemas: list[Problema] = []
    acesso = catalogo.acesso
    onde = "acesso.yml"

    if not acesso.niveis:
        return [_erro(onde, "nenhum nível de acesso declarado.")]

    for id_nivel in sorted(acesso.niveis):
        nivel = acesso.niveis[id_nivel]
        onde_nivel = f"{onde}:{id_nivel}"
        if not PADRAO_IDENTIFICADOR.match(id_nivel):
            problemas.append(_erro(onde_nivel, "id do nível deve ser snake_case."))
        if not nivel.descricao:
            problemas.append(
                _erro(
                    onde_nivel, "descricao é obrigatória — ela é o critério de concessão."
                )
            )
        if not nivel.ve_classificacoes:
            problemas.append(
                _erro(onde_nivel, "ve_classificacoes vazio: o nível não enxerga nada.")
            )
        for classificacao in nivel.ve_classificacoes:
            if classificacao not in CLASSIFICACOES:
                problemas.append(
                    _erro(
                        onde_nivel,
                        f"classificacao '{classificacao}' não existe no vocabulário do "
                        f"ADR-0013; use uma de: {', '.join(sorted(CLASSIFICACOES))}.",
                    )
                )

    for campo, valor in (
        ("papel.prefixo", acesso.prefixo_papel),
        ("papel.herda", acesso.papel_herda),
        ("recorte.chave", acesso.chave_recorte),
        ("recorte.sufixo", acesso.sufixo_recorte),
    ):
        if not valor:
            problemas.append(_erro(onde, f"{campo} é obrigatório."))

    problemas += _validar_chave_recorte(acesso.chave_recorte, onde)
    return problemas


def _validar_chave_recorte(chave: str, onde: str) -> list[Problema]:
    """O recorte precisa ser feito por uma chave conformada de verdade."""
    if not chave:
        return []
    try:
        catalogo_modelagem = carregar_modelagem()
    except ErroCatalogo as exc:
        return [
            _aviso(
                onde, f"não deu para conferir recorte.chave no catálogo de chaves: {exc}"
            )
        ]
    if chave not in catalogo_modelagem.chaves:
        conhecidas = ", ".join(sorted(catalogo_modelagem.chaves)) or "nenhuma"
        return [
            _erro(
                onde,
                f"recorte.chave '{chave}' não é uma chave conformada (ADR-0017). "
                f"Declaradas: {conhecidas}.",
            )
        ]
    return []


# --------------------------------------------------------------------------
# Publicação de um órgão
# --------------------------------------------------------------------------


def _validar_orgao(
    catalogo: CatalogoPublicacao,
    publicacao: Publicacao,
    dir_publicacao: Path,
    dir_dbt: Path | None,
) -> list[Problema]:
    onde = f"publicacao/{publicacao.orgao}.yml"
    problemas: list[Problema] = []

    if not PADRAO_IDENTIFICADOR.match(publicacao.orgao):
        problemas.append(
            _erro(onde, "orgao deve ser snake_case — é pasta e prefixo de papel.")
        )
    if not (dir_publicacao / f"{publicacao.orgao}.yml").is_file():
        problemas.append(
            _erro(
                onde,
                f"nome do arquivo difere do campo 'orgao' ('{publicacao.orgao}'); "
                "renomeie o arquivo para manter a correspondência 1-para-1.",
            )
        )
    if not publicacao.owner:
        problemas.append(
            _erro(
                onde, "owner é obrigatório e deve ser um time, não uma pessoa (ADR-0013)."
            )
        )
    if not publicacao.database:
        problemas.append(_erro(onde, "database é obrigatório — é a conexão do Superset."))
    if not (publicacao.dir_dbt / "dbt_project.yml").is_file():
        problemas.append(
            _erro(
                onde,
                f"não há projeto dbt em {publicacao.dir_dbt.name}/ — um órgão publica o "
                "que ele próprio materializa (ADR-0004).",
            )
        )

    problemas += _validar_datasets(publicacao, onde, dir_dbt)
    problemas += _validar_dashboards(catalogo, publicacao, onde, dir_dbt)
    problemas += _validar_relatorios(catalogo, publicacao, onde)
    problemas += _validar_consumidores(catalogo, publicacao, onde)
    return problemas


def _validar_datasets(
    publicacao: Publicacao, onde_orgao: str, dir_dbt: Path | None
) -> list[Problema]:
    problemas: list[Problema] = []
    for id_dataset in sorted(publicacao.datasets):
        dataset = publicacao.datasets[id_dataset]
        onde = f"{onde_orgao}:datasets.{id_dataset}"

        if not PADRAO_IDENTIFICADOR.match(id_dataset):
            problemas.append(
                _erro(onde, "id do dataset deve ser o nome da tabela, em snake_case.")
            )
        if not dataset.descricao:
            problemas.append(_erro(onde, "descricao é obrigatória (ADR-0013)."))
        if not dataset.modelo:
            problemas.append(
                _erro(onde, "modelo é obrigatório — o caminho do modelo dbt.")
            )
        elif dbt_meta.localizar_sql(publicacao.orgao, dataset.modelo, dir_dbt) is None:
            problemas.append(
                _erro(
                    onde,
                    f"modelo '{dataset.modelo}.sql' não existe no projeto dbt de "
                    f"{publicacao.orgao} nem nos pacotes que ele importa.",
                )
            )
        if dataset.camada == "bronze":
            problemas.append(
                _erro(
                    onde,
                    "dataset apontando para a Bronze: consumidor final não acessa "
                    "Bronze (ADR-0006).",
                )
            )

        usado = any(
            id_dataset in dashboard.datasets
            for dashboard in publicacao.dashboards.values()
        ) or any(
            relatorio.dataset == id_dataset
            for relatorio in publicacao.relatorios.values()
        )
        if not usado:
            problemas.append(
                _aviso(
                    onde,
                    "dataset declarado e não usado por nenhuma dashboard ou relatório.",
                )
            )
    return problemas


def _validar_dashboards(
    catalogo: CatalogoPublicacao,
    publicacao: Publicacao,
    onde_orgao: str,
    dir_dbt: Path | None,
) -> list[Problema]:
    problemas: list[Problema] = []
    acesso = catalogo.acesso

    for id_dash in sorted(publicacao.dashboards):
        dashboard = publicacao.dashboards[id_dash]
        onde = f"{onde_orgao}:dashboards.{id_dash}"

        if not dashboard.titulo:
            problemas.append(_erro(onde, "titulo é obrigatório."))
        if not dashboard.descricao:
            problemas.append(
                _erro(
                    onde, "descricao é obrigatória — a pergunta que a dashboard responde."
                )
            )
        problemas += _validar_nivel(acesso, dashboard.nivel, onde)
        if not dashboard.datasets:
            problemas.append(_erro(onde, "dashboard sem dataset declarado."))

        if not dashboard.bundle:
            problemas.append(_erro(onde, "bundle é obrigatório."))
            continue

        caminho = publicacao.dir_bundles / dashboard.bundle
        lido = bundle_mod.carregar(caminho, dashboard.bundle)
        if lido is None:
            problemas.append(
                _erro(
                    onde,
                    f"bundle não encontrado em {_relativo(caminho)}. "
                    "Exporte a dashboard do Superset e versione o export.",
                )
            )
            continue

        problemas += _validar_bundle(catalogo, publicacao, dashboard, lido, onde, dir_dbt)
    return problemas


def _validar_bundle(
    catalogo: CatalogoPublicacao,
    publicacao: Publicacao,
    dashboard,
    lido: bundle_mod.Bundle,
    onde: str,
    dir_dbt: Path | None,
) -> list[Problema]:
    problemas: list[Problema] = []
    acesso = catalogo.acesso

    for arquivo, motivo in sorted(lido.ilegiveis.items()):
        problemas.append(
            _erro(onde, f"arquivo ilegível no bundle ({arquivo}): {motivo}.")
        )
    if not lido.versao or not lido.tipo:
        problemas.append(
            _erro(onde, "bundle sem metadata.yaml válido (campos 'version' e 'type').")
        )
    if not lido.dashboards:
        problemas.append(_erro(onde, "bundle não contém nenhuma dashboard."))
    if len(lido.dashboards) > 1:
        problemas.append(
            _aviso(
                onde,
                f"bundle traz {len(lido.dashboards)} dashboards; o catálogo declara uma. "
                "Uma pasta de bundle por dashboard mantém o versionamento legível.",
            )
        )
    if not lido.graficos:
        problemas.append(_aviso(onde, "bundle sem nenhum gráfico."))

    nomes_db = {db.nome for db in lido.databases}
    if publicacao.database and nomes_db and publicacao.database not in nomes_db:
        problemas.append(
            _erro(
                onde,
                f"bundle aponta para o database {', '.join(sorted(nomes_db))}, "
                f"e o catálogo declara '{publicacao.database}'.",
            )
        )

    uuids_dataset = {ds.uuid: ds for ds in lido.datasets if ds.uuid}
    for grafico in lido.graficos:
        if grafico.dataset_uuid and grafico.dataset_uuid not in uuids_dataset:
            problemas.append(
                _erro(
                    onde,
                    f"gráfico '{grafico.nome}' lê um dataset que não está no bundle "
                    f"(uuid {grafico.dataset_uuid}) — o import criaria uma dashboard quebrada.",
                )
            )

    declarados = set(publicacao.datasets)
    no_bundle = {ds.tabela for ds in lido.datasets}
    for tabela in sorted(no_bundle - declarados):
        problemas.append(
            _erro(
                onde,
                f"bundle expõe o dataset '{tabela}', que não está declarado em "
                "datasets: — publicação não catalogada.",
            )
        )
    for id_dataset in dashboard.datasets:
        if id_dataset not in no_bundle:
            problemas.append(
                _erro(
                    onde,
                    f"catálogo declara o dataset '{id_dataset}' nesta dashboard, "
                    "mas ele não está no bundle exportado.",
                )
            )

    for id_dataset in sorted(set(dashboard.datasets) & declarados & no_bundle):
        dataset = publicacao.datasets[id_dataset]
        if acesso.niveis.get(dashboard.nivel) and acesso.niveis.get(dataset.nivel):
            if not acesso.alcanca(dashboard.nivel, dataset.nivel):
                problemas.append(
                    _erro(
                        onde,
                        f"dashboard de nível '{dashboard.nivel}' usa o dataset "
                        f"'{id_dataset}', que exige nível '{dataset.nivel}'.",
                    )
                )
        problemas += _validar_colunas_expostas(
            catalogo, publicacao, dataset, lido, onde, dir_dbt
        )
    return problemas


def _validar_colunas_expostas(
    catalogo: CatalogoPublicacao,
    publicacao: Publicacao,
    dataset,
    lido: bundle_mod.Bundle,
    onde: str,
    dir_dbt: Path | None,
) -> list[Problema]:
    """O coração da verificação de acesso: coluna exposta × classificação."""
    problemas: list[Problema] = []
    no_bundle = lido.dataset(dataset.id)
    if no_bundle is None:
        return problemas

    nivel = catalogo.acesso.niveis.get(dataset.nivel)
    modelo = dbt_meta.carregar_modelo(publicacao.orgao, dataset.modelo, dir_dbt)
    if modelo is None:
        return problemas

    if not no_bundle.colunas:
        problemas.append(
            _erro(onde, f"dataset '{dataset.id}' no bundle não lista nenhuma coluna.")
        )

    for coluna in no_bundle.colunas:
        classificacao = modelo.classificacao_de(coluna)
        if classificacao is None:
            # ADR-0013 trata coluna sem classificação como dado pessoal. Só é
            # aviso quando o nível já enxergaria dado pessoal de qualquer forma.
            problemas.append(
                _aviso(
                    onde,
                    f"coluna '{coluna}' exposta em '{dataset.id}' não está documentada "
                    f"em {modelo.nome}: sem classificação, o ADR-0013 a trata como "
                    "'pessoal'. Documente no schema.yml do modelo.",
                )
                if nivel and nivel.ve("pessoal")
                else _erro(
                    onde,
                    f"coluna '{coluna}' exposta em '{dataset.id}' não está documentada "
                    f"em {modelo.nome}. Sem classificação declarada ela vale como "
                    f"'pessoal' (ADR-0013), acima do nível '{dataset.nivel}' do dataset.",
                )
            )
            continue
        if nivel and not nivel.ve(classificacao):
            problemas.append(
                _erro(
                    onde,
                    f"coluna '{coluna}' é '{classificacao}' e o dataset '{dataset.id}' "
                    f"é de nível '{dataset.nivel}', que vê apenas "
                    f"{', '.join(nivel.ve_classificacoes)}. Tire a coluna do SQL do "
                    "dataset ou eleve o nível declarado.",
                )
            )

    if dataset.recorte and catalogo.acesso.chave_recorte not in no_bundle.colunas:
        problemas.append(
            _erro(
                onde,
                f"dataset '{dataset.id}' pede recorte por "
                f"'{catalogo.acesso.chave_recorte}', mas essa coluna não está exposta "
                "no bundle — o filtro de linhas não teria onde se aplicar.",
            )
        )
    return problemas


def _validar_relatorios(
    catalogo: CatalogoPublicacao, publicacao: Publicacao, onde_orgao: str
) -> list[Problema]:
    problemas: list[Problema] = []
    acesso = catalogo.acesso

    for id_rel in sorted(publicacao.relatorios):
        relatorio = publicacao.relatorios[id_rel]
        onde = f"{onde_orgao}:relatorios.{id_rel}"

        if not relatorio.titulo:
            problemas.append(_erro(onde, "titulo é obrigatório."))
        if not relatorio.descricao:
            problemas.append(_erro(onde, "descricao é obrigatória."))
        problemas += _validar_nivel(acesso, relatorio.nivel, onde)

        if relatorio.formato not in FORMATOS:
            problemas.append(
                _erro(
                    onde,
                    f"formato '{relatorio.formato}' inválido; "
                    f"use um de: {', '.join(sorted(FORMATOS))}.",
                )
            )
        if not relatorio.destinos:
            problemas.append(
                _erro(onde, "destinos vazio: o relatório não seria entregue.")
            )
        for destino in relatorio.destinos:
            if destino not in DESTINOS:
                problemas.append(
                    _erro(
                        onde,
                        f"destino '{destino}' inválido; "
                        f"use um de: {', '.join(sorted(DESTINOS))}.",
                    )
                )
        if "email" in relatorio.destinos and not relatorio.destinatarios_variavel:
            problemas.append(
                _erro(
                    onde,
                    "destino 'email' exige destinatarios_variavel — a lista de "
                    "destinatários é dado pessoal e não entra no repositório (ADR-0013).",
                )
            )

        dataset = publicacao.datasets.get(relatorio.dataset)
        if dataset is None:
            problemas.append(
                _erro(
                    onde,
                    f"dataset '{relatorio.dataset}' não está declarado em datasets:.",
                )
            )
        elif acesso.niveis.get(relatorio.nivel) and acesso.niveis.get(dataset.nivel):
            if not acesso.alcanca(relatorio.nivel, dataset.nivel):
                problemas.append(
                    _erro(
                        onde,
                        f"relatório de nível '{relatorio.nivel}' lê o dataset "
                        f"'{dataset.id}', que exige nível '{dataset.nivel}'.",
                    )
                )

        if not relatorio.dag:
            problemas.append(_erro(onde, "dag é obrigatório."))
        elif not (publicacao.dir_relatorios / f"{relatorio.dag}.py").is_file():
            problemas.append(
                _erro(
                    onde,
                    f"DAG declarada não existe: data_report/{publicacao.orgao}/"
                    f"{relatorio.dag}.py (ADR-0019).",
                )
            )
        elif not relatorio.dag.endswith(f"{publicacao.orgao}_report_dag"):
            problemas.append(
                _erro(
                    onde,
                    f"nome da DAG deve terminar em '{publicacao.orgao}_report_dag' "
                    "(ADR-0019).",
                )
            )

    problemas += _validar_relatorios_orfaos(publicacao, onde_orgao)
    return problemas


def _validar_relatorios_orfaos(publicacao: Publicacao, onde_orgao: str) -> list[Problema]:
    """DAG de relatório que existe no disco e ninguém declarou no catálogo."""
    if not publicacao.dir_relatorios.is_dir():
        return []
    declaradas = {relatorio.dag for relatorio in publicacao.relatorios.values()}
    problemas: list[Problema] = []
    for arquivo in sorted(publicacao.dir_relatorios.glob("*_report_dag.py")):
        if arquivo.stem not in declaradas:
            problemas.append(
                _erro(
                    f"{onde_orgao}:relatorios",
                    f"a DAG data_report/{publicacao.orgao}/{arquivo.name} entrega um "
                    "relatório que o catálogo não declara — sem declaração não há "
                    "nível de acesso conferido.",
                )
            )
    return problemas


def _validar_consumidores(
    catalogo: CatalogoPublicacao, publicacao: Publicacao, onde_orgao: str
) -> list[Problema]:
    problemas: list[Problema] = []
    acesso = catalogo.acesso

    if not publicacao.consumidores:
        problemas.append(
            _aviso(
                f"{onde_orgao}:consumidores", "ninguém consome o que este órgão publica."
            )
        )

    for id_cons in sorted(publicacao.consumidores):
        consumidor = publicacao.consumidores[id_cons]
        onde = f"{onde_orgao}:consumidores.{id_cons}"

        if not PADRAO_IDENTIFICADOR.match(id_cons):
            problemas.append(
                _erro(
                    onde,
                    "id do consumidor deve ser o do órgão, em snake_case — vira papel.",
                )
            )
        if not consumidor.nome:
            problemas.append(_erro(onde, "nome é obrigatório."))
        problemas += _validar_nivel(acesso, consumidor.nivel, onde)

        if consumidor.abrangencia not in ABRANGENCIAS:
            problemas.append(
                _erro(
                    onde,
                    f"abrangencia '{consumidor.abrangencia}' inválida; "
                    f"use uma de: {', '.join(sorted(ABRANGENCIAS))}.",
                )
            )
        if consumidor.abrangencia == "total":
            problemas.append(
                _aviso(
                    onde,
                    "abrangência total: este consumidor vê as linhas de todos os órgãos, "
                    "sem recorte. Confirme que a competência sobre a base inteira é "
                    "declarada em algum lugar fora deste catálogo.",
                )
            )
        if not consumidor.codigo_orgao.isdigit():
            problemas.append(
                _erro(
                    onde,
                    f"codigo_orgao '{consumidor.codigo_orgao}' deve conter só dígitos.",
                )
            )
        elif not consumidor.codigo_orgao_verificado:
            problemas.append(
                _aviso(
                    onde,
                    f"codigo_orgao '{consumidor.codigo_orgao}' não verificado contra a "
                    "tabela de órgãos ingerida — confirme antes de confiar no recorte.",
                )
            )

        if not consumidor.dashboards and not consumidor.relatorios:
            problemas.append(
                _aviso(onde, "consumidor sem dashboard nem relatório atribuído.")
            )

        for id_dash in consumidor.dashboards:
            dashboard = publicacao.dashboards.get(id_dash)
            if dashboard is None:
                problemas.append(
                    _erro(
                        onde, f"dashboard '{id_dash}' não está declarada em dashboards:."
                    )
                )
                continue
            if acesso.niveis.get(consumidor.nivel) and acesso.niveis.get(dashboard.nivel):
                if not acesso.alcanca(consumidor.nivel, dashboard.nivel):
                    problemas.append(
                        _erro(
                            onde,
                            f"consumidor de nível '{consumidor.nivel}' recebe a dashboard "
                            f"'{id_dash}', que exige nível '{dashboard.nivel}'.",
                        )
                    )

        for id_rel in consumidor.relatorios:
            relatorio = publicacao.relatorios.get(id_rel)
            if relatorio is None:
                problemas.append(
                    _erro(
                        onde, f"relatório '{id_rel}' não está declarado em relatorios:."
                    )
                )
                continue
            if acesso.niveis.get(consumidor.nivel) and acesso.niveis.get(relatorio.nivel):
                if not acesso.alcanca(consumidor.nivel, relatorio.nivel):
                    problemas.append(
                        _erro(
                            onde,
                            f"consumidor de nível '{consumidor.nivel}' recebe o relatório "
                            f"'{id_rel}', que exige nível '{relatorio.nivel}'.",
                        )
                    )
    return problemas


def _validar_nivel(acesso, nivel: str, onde: str) -> list[Problema]:
    if nivel in acesso.niveis:
        return []
    conhecidos = ", ".join(sorted(acesso.niveis)) or "nenhum"
    return [
        _erro(
            onde, f"nivel '{nivel}' não existe em acesso.yml. Declarados: {conhecidos}."
        )
    ]


def planos_dessincronizados(
    catalogo: CatalogoPublicacao, dir_dbt: Path | None = None
) -> list[Problema]:
    """Planos de acesso no disco que já não correspondem ao catálogo."""
    return [
        _erro(
            f"superset/{id_orgao}/acesso.yml",
            "plano de acesso fora de sincronia com o catálogo. Rode: make publicacao-sync",
        )
        for id_orgao in acesso_mod.dessincronizados(catalogo, dir_dbt)
    ]
