"""Validação do catálogo de sistemas estruturantes (ADR-0017).

Separa dois tipos de achado: `erro`, que reprova o CI porque torna o catálogo
inconsistente ou inutilizável pelo gerador, e `aviso`, que apenas sinaliza —
notadamente mapeamentos ainda não verificados contra o dado ingerido, que são
informação legítima e não defeito.
"""

from __future__ import annotations

from pathlib import Path

from .catalogo import (
    CLASSIFICACOES,
    CONFIABILIDADES,
    DIR_CATALOGO,
    NORMALIZACOES,
    PADRAO_IDENTIFICADOR,
    STATUS_SISTEMA,
    Catalogo,
    Problema,
)


def validar(catalogo: Catalogo, dir_catalogo: Path | None = None) -> list[Problema]:
    """Valida o catálogo inteiro e devolve os problemas encontrados."""
    problemas: list[Problema] = []
    problemas += _validar_chaves(catalogo)
    problemas += _validar_pontes(catalogo)
    problemas += _validar_sistemas(catalogo, dir_catalogo or DIR_CATALOGO)
    return problemas


def tem_erro(problemas: list[Problema]) -> bool:
    return any(p.nivel == "erro" for p in problemas)


def _erro(onde: str, mensagem: str) -> Problema:
    return Problema(nivel="erro", onde=onde, mensagem=mensagem)


def _aviso(onde: str, mensagem: str) -> Problema:
    return Problema(nivel="aviso", onde=onde, mensagem=mensagem)


def _validar_chaves(catalogo: Catalogo) -> list[Problema]:
    problemas: list[Problema] = []
    if not catalogo.chaves:
        return [_erro("chaves.yml", "nenhuma chave conformada declarada.")]

    for chave in catalogo.chaves.values():
        onde = f"chaves.yml:{chave.id}"
        if not PADRAO_IDENTIFICADOR.match(chave.id):
            problemas.append(
                _erro(onde, "id deve ser snake_case (minúsculas, dígitos e underscore).")
            )
        if not chave.descricao:
            problemas.append(_erro(onde, "descricao é obrigatória."))
        if chave.normalizacao not in NORMALIZACOES:
            problemas.append(
                _erro(
                    onde,
                    f"normalizacao '{chave.normalizacao}' inválida; "
                    f"use uma de: {', '.join(sorted(NORMALIZACOES))}.",
                )
            )
        if chave.classificacao not in CLASSIFICACOES:
            problemas.append(
                _erro(
                    onde,
                    f"classificacao '{chave.classificacao}' inválida; "
                    f"use uma de: {', '.join(sorted(CLASSIFICACOES))} (ADR-0013).",
                )
            )
        if chave.tamanho is not None and (
            not isinstance(chave.tamanho, int) or chave.tamanho <= 0
        ):
            problemas.append(_erro(onde, "tamanho deve ser um inteiro positivo."))
        if not chave.sistema_de_referencia:
            problemas.append(
                _aviso(
                    onde, "sem sistema_de_referencia — a origem da chave fica implícita."
                )
            )
    return problemas


def _validar_pontes(catalogo: Catalogo) -> list[Problema]:
    problemas: list[Problema] = []
    for indice, ponte in enumerate(catalogo.pontes):
        onde = f"chaves.yml:pontes[{indice}] ({ponte.de or '?'} → {ponte.para or '?'})"
        for lado, valor in (("de", ponte.de), ("para", ponte.para)):
            if valor not in catalogo.chaves:
                problemas.append(
                    _erro(onde, f"'{lado}' aponta para chave inexistente: '{valor}'.")
                )
        if ponte.de and ponte.de == ponte.para:
            problemas.append(_erro(onde, "ponte de uma chave para ela mesma."))
        if ponte.confiabilidade not in CONFIABILIDADES:
            problemas.append(
                _erro(
                    onde,
                    f"confiabilidade '{ponte.confiabilidade}' inválida; "
                    f"use uma de: {', '.join(sorted(CONFIABILIDADES))}.",
                )
            )
        if ponte.tipo == "derivacao_condicional" and not ponte.condicao:
            problemas.append(
                _erro(onde, "derivacao_condicional exige o campo 'condicao'.")
            )
        if ponte.confiabilidade == "indicio":
            problemas.append(
                _aviso(onde, "confiabilidade 'indicio' — não use esta ponte em Gold.")
            )
    return problemas


def _validar_sistemas(catalogo: Catalogo, dir_catalogo: Path) -> list[Problema]:
    problemas: list[Problema] = []
    if not catalogo.sistemas:
        return [_erro("catalogo/sistemas/", "nenhum sistema catalogado.")]

    dir_sistemas = dir_catalogo / "sistemas"
    for sistema in catalogo.sistemas.values():
        onde = f"sistemas/{sistema.id}.yml"
        if not PADRAO_IDENTIFICADOR.match(sistema.id):
            problemas.append(
                _erro(
                    onde, "sistema deve ser snake_case — vira o schema Bronze (ADR-0010)."
                )
            )
        if not (dir_sistemas / f"{sistema.id}.yml").is_file():
            problemas.append(
                _erro(
                    onde,
                    f"nome do arquivo difere do campo 'sistema' ('{sistema.id}'); "
                    "renomeie o arquivo para manter a correspondência 1-para-1.",
                )
            )
        if sistema.status not in STATUS_SISTEMA:
            problemas.append(
                _erro(
                    onde,
                    f"status '{sistema.status}' inválido; "
                    f"use um de: {', '.join(sorted(STATUS_SISTEMA))}.",
                )
            )
        if not sistema.owner:
            problemas.append(
                _erro(
                    onde,
                    "owner é obrigatório e deve ser um time, não uma pessoa (ADR-0013).",
                )
            )
        if not sistema.entidades:
            problemas.append(_aviso(onde, "sistema sem nenhuma entidade catalogada."))

        for entidade in sistema.entidades.values():
            problemas += _validar_entidade(catalogo, sistema, entidade, onde)

    return problemas


def _validar_entidade(catalogo, sistema, entidade, onde_sistema: str) -> list[Problema]:
    problemas: list[Problema] = []
    onde = f"{onde_sistema}:{entidade.id}"

    if not PADRAO_IDENTIFICADOR.match(entidade.id):
        problemas.append(
            _erro(
                onde,
                "nome da entidade deve ser snake_case — vira nome de tabela (ADR-0010).",
            )
        )
    if not entidade.descricao:
        problemas.append(_erro(onde, "descricao é obrigatória (ADR-0013)."))
    if not entidade.granularidade:
        problemas.append(
            _erro(
                onde,
                "granularidade é obrigatória — o que uma linha representa (ADR-0013).",
            )
        )
    if entidade.classificacao not in CLASSIFICACOES:
        problemas.append(
            _erro(
                onde,
                f"classificacao '{entidade.classificacao}' inválida; "
                f"use uma de: {', '.join(sorted(CLASSIFICACOES))} (ADR-0013).",
            )
        )
    if entidade.dominio and not PADRAO_IDENTIFICADOR.match(entidade.dominio):
        problemas.append(
            _erro(onde, "dominio deve ser snake_case — vira o schema Silver (ADR-0010).")
        )
    if not entidade.dominio:
        problemas.append(
            _erro(onde, "dominio é obrigatório — define a pasta e o schema da Silver.")
        )
    if sistema.status == "ingerido" and not entidade.origem_atual:
        problemas.append(
            _erro(
                onde,
                "sistema 'ingerido' exige origem_atual (schema.tabela onde a DAG grava), "
                "usada para declarar o source Bronze.",
            )
        )
    if entidade.origem_atual and "." not in entidade.origem_atual:
        problemas.append(
            _erro(
                onde, f"origem_atual '{entidade.origem_atual}' deve ser 'schema.tabela'."
            )
        )
    if not entidade.chave_primaria:
        problemas.append(
            _aviso(onde, "sem chave_primaria — o gerador não criará teste de unicidade.")
        )

    vistos: set[str] = set()
    for mapeamento in entidade.chaves:
        onde_chave = f"{onde}.{mapeamento.chave or '?'}"
        if mapeamento.chave not in catalogo.chaves:
            problemas.append(
                _erro(
                    onde_chave,
                    f"chave conformada '{mapeamento.chave}' não existe em chaves.yml.",
                )
            )
        if not mapeamento.coluna:
            problemas.append(_erro(onde_chave, "coluna de origem não informada."))
        if mapeamento.chave in vistos:
            problemas.append(
                _erro(
                    onde_chave, "chave conformada declarada mais de uma vez na entidade."
                )
            )
        vistos.add(mapeamento.chave)
        if not mapeamento.verificado:
            problemas.append(
                _aviso(
                    onde_chave,
                    f"mapeamento não verificado (coluna '{mapeamento.coluna}') — "
                    "confirme contra o dado ingerido antes de usar em Gold.",
                )
            )
    return problemas
