"""Mapa de cruzamento entre sistemas estruturantes (ADR-0017).

Responde, a partir do catálogo, a pergunta que antecede qualquer modelagem
Gold: *o que dá para cruzar com o quê, por qual chave, e com que confiança?*
"""

from __future__ import annotations

from itertools import combinations

from .catalogo import Catalogo, Entidade, Sistema

_MARCA_VERIFICADO = {True: "ok", False: "??"}


def _qualificado(sistema: Sistema, entidade: Entidade) -> str:
    return f"{sistema.id}.{entidade.id}"


def linhas_por_chave(catalogo: Catalogo) -> list[str]:
    """Para cada chave conformada, onde ela aparece."""
    linhas = ["CHAVES CONFORMADAS — onde cada uma aparece", ""]
    for id_chave in sorted(catalogo.chaves):
        chave = catalogo.chaves[id_chave]
        ocorrencias = catalogo.ocorrencias(id_chave)
        sistemas_distintos = {sistema.id for sistema, _, _ in ocorrencias}
        alcance = (
            f"{len(ocorrencias)} entidade(s) em {len(sistemas_distintos)} sistema(s)"
            if ocorrencias
            else "ainda não usada por nenhuma entidade catalogada"
        )
        tamanho = f", {chave.tamanho} dígitos" if chave.tamanho else ""
        linhas.append(
            f"  {id_chave}  [{chave.normalizacao}{tamanho}, {chave.classificacao}]"
        )
        linhas.append(f"    {alcance}")
        for sistema, entidade, mapeamento in ocorrencias:
            marca = _MARCA_VERIFICADO[mapeamento.verificado]
            linhas.append(
                f"      [{marca}] {_qualificado(sistema, entidade)}.{mapeamento.coluna}"
            )
        for ponte in catalogo.pontes_de(id_chave):
            condicao = f" quando {ponte.condicao}" if ponte.condicao else ""
            linhas.append(
                f"      ponte → {ponte.para}{condicao} "
                f"(confiabilidade: {ponte.confiabilidade})"
            )
        linhas.append("")
    return linhas


def linhas_por_par(catalogo: Catalogo) -> list[str]:
    """Pares de entidades cruzáveis — por chave compartilhada ou por ponte."""
    entidades = [
        (sistema, entidade)
        for sistema in catalogo.sistemas.values()
        for entidade in sistema.entidades.values()
    ]

    linhas_diretas: list[tuple[bool, str, str, str]] = []
    for (sis_a, ent_a), (sis_b, ent_b) in combinations(entidades, 2):
        chaves_a = {m.chave: m for m in ent_a.chaves}
        chaves_b = {m.chave: m for m in ent_b.chaves}
        entre_sistemas = sis_a.id != sis_b.id
        rotulo = f"{_qualificado(sis_a, ent_a)} ⨝ {_qualificado(sis_b, ent_b)}"
        escopo = "entre sistemas" if entre_sistemas else "mesmo sistema"

        comuns = sorted(set(chaves_a) & set(chaves_b))
        if comuns:
            verificado = all(
                chaves_a[c].verificado and chaves_b[c].verificado for c in comuns
            )
            linhas_diretas.append(
                (
                    entre_sistemas,
                    rotulo,
                    f"  [{_MARCA_VERIFICADO[verificado]}] {rotulo}  "
                    f"por {', '.join(comuns)}  ({escopo})",
                    "direto",
                )
            )
            continue

        # Sem chave em comum, a ligação ainda pode existir por uma ponte — que é
        # justamente o caso mais frequente entre sistemas estruturantes distintos.
        for ponte in catalogo.pontes:
            ligacoes = [
                (ponte.de, ponte.para, chaves_a, chaves_b),
                (ponte.de, ponte.para, chaves_b, chaves_a),
            ]
            achou = next(
                (
                    (de, para)
                    for de, para, esquerda, direita in ligacoes
                    if de in esquerda and para in direita
                ),
                None,
            )
            if achou is None:
                continue
            de, para = achou
            condicao = f", quando {ponte.condicao}" if ponte.condicao else ""
            linhas_diretas.append(
                (
                    entre_sistemas,
                    rotulo,
                    f"  [->] {rotulo}  via ponte {de} → {para}{condicao}  "
                    f"(confiabilidade: {ponte.confiabilidade}, {escopo})",
                    "ponte",
                )
            )
            break

    linhas = ["CRUZAMENTOS — entidades que se ligam", ""]
    if not linhas_diretas:
        linhas += ["  Nenhum par de entidades se liga por chave conformada.", ""]
        return linhas

    # Cruzamento entre sistemas diferentes vem primeiro: é o que o catálogo
    # existe para revelar.
    linhas_diretas.sort(key=lambda item: (not item[0], item[3] == "ponte", item[1]))
    linhas += [item[2] for item in linhas_diretas]
    linhas.append("")
    return linhas


def linhas_por_sistema(catalogo: Catalogo) -> list[str]:
    """Inventário do que está catalogado, por sistema."""
    linhas = ["SISTEMAS CATALOGADOS", ""]
    for id_sistema in sorted(catalogo.sistemas):
        sistema = catalogo.sistemas[id_sistema]
        linhas.append(
            f"  {sistema.id} — {sistema.nome} "
            f"[{sistema.status}, owner {sistema.owner}, bronze: {sistema.schema_bronze}]"
        )
        for id_entidade in sorted(sistema.entidades):
            entidade = sistema.entidades[id_entidade]
            chaves = ", ".join(m.chave for m in entidade.chaves) or "sem chave conformada"
            linhas.append(f"      {entidade.id}  ({entidade.dominio})  → {chaves}")
        linhas.append("")
    return linhas


def render(catalogo: Catalogo) -> str:
    """Mapa completo, em texto, para o terminal."""
    partes = (
        linhas_por_sistema(catalogo)
        + linhas_por_chave(catalogo)
        + linhas_por_par(catalogo)
        + [
            "Legenda: [ok] cruzamento verificado; [??] mapeamento não verificado; "
            "[->] ligação por ponte entre chaves distintas.",
        ]
    )
    return "\n".join(partes)


def render_mermaid(catalogo: Catalogo) -> str:
    """Mapa como grafo Mermaid, para colar em documentação."""
    linhas = ["graph LR"]
    for id_sistema in sorted(catalogo.sistemas):
        sistema = catalogo.sistemas[id_sistema]
        linhas.append(f'  subgraph {sistema.id}["{sistema.nome}"]')
        for id_entidade in sorted(sistema.entidades):
            no = f"{sistema.id}__{id_entidade}"
            linhas.append(f'    {no}["{id_entidade}"]')
        linhas.append("  end")

    for id_chave in sorted(catalogo.chaves):
        ocorrencias = catalogo.ocorrencias(id_chave)
        for (sis_a, ent_a, map_a), (sis_b, ent_b, map_b) in combinations(ocorrencias, 2):
            estilo = "---" if (map_a.verificado and map_b.verificado) else "-.-"
            linhas.append(
                f"  {sis_a.id}__{ent_a.id} {estilo}|{id_chave}| {sis_b.id}__{ent_b.id}"
            )
    return "\n".join(linhas)
