"""Carregamento e validação do catálogo de sistemas estruturantes (ADR-0017)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import yaml

RAIZ = Path(__file__).resolve().parents[2]
DIR_CATALOGO = RAIZ / "catalogo"

PADRAO_IDENTIFICADOR = re.compile(r"^[a-z][a-z0-9_]*$")

NORMALIZACOES = frozenset({"digitos", "texto"})
CLASSIFICACOES = frozenset({"publico", "interno", "pessoal", "pessoal_sensivel"})
CONFIABILIDADES = frozenset({"total", "parcial", "indicio"})
STATUS_SISTEMA = frozenset({"ingerido", "planejado"})
CAMADAS = ("bronze", "silver", "gold")

# Classificações da menos para a mais restritiva (ADR-0013): a classificação de
# um modelo é a mais restritiva entre as de suas colunas.
ORDEM_CLASSIFICACAO = ("publico", "interno", "pessoal", "pessoal_sensivel")


class ErroCatalogo(RuntimeError):
    """Catálogo ausente ou ilegível — impede qualquer operação."""


@dataclass(frozen=True)
class Problema:
    """Uma inconsistência encontrada na validação do catálogo."""

    nivel: str  # "erro" bloqueia o CI; "aviso" apenas sinaliza.
    onde: str
    mensagem: str

    def __str__(self) -> str:
        marca = "ERRO " if self.nivel == "erro" else "aviso"
        return f"{marca}  {self.onde}: {self.mensagem}"


@dataclass(frozen=True)
class Chave:
    """Chave conformada — identificador cruzável entre sistemas."""

    id: str
    nome: str
    descricao: str
    normalizacao: str
    classificacao: str
    sistema_de_referencia: str
    tamanho: int | None = None


@dataclass(frozen=True)
class Ponte:
    """Equivalência ou derivação conhecida entre duas chaves conformadas."""

    de: str
    para: str
    tipo: str
    confiabilidade: str
    descricao: str
    condicao: str | None = None
    observacao: str | None = None


@dataclass(frozen=True)
class Mapeamento:
    """Coluna de uma entidade que expõe uma chave conformada."""

    chave: str
    coluna: str
    verificado: bool = False
    # `verificado` diz que a coluna de origem está certa; `opcional` diz que ela
    # é nula em parte das linhas por natureza do cadastro — são coisas
    # diferentes. Um fornecedor pessoa jurídica não tem CPF, e testar not_null
    # nessa coluna reprovaria o build por um fato do domínio, não por defeito.
    opcional: bool = False
    observacao: str | None = None


@dataclass(frozen=True)
class Entidade:
    """Uma tabela/entidade de um sistema estruturante."""

    id: str
    descricao: str
    granularidade: str
    dominio: str
    classificacao: str
    chave_primaria: tuple[str, ...] = ()
    chaves: tuple[Mapeamento, ...] = ()
    dag: str | None = None
    origem_atual: str | None = None

    @property
    def schema_origem(self) -> str | None:
        """Schema da tabela onde a ingestão grava hoje, se declarada."""
        if not self.origem_atual or "." not in self.origem_atual:
            return None
        return self.origem_atual.split(".", 1)[0]

    @property
    def tabela_origem(self) -> str | None:
        """Tabela onde a ingestão grava hoje, se declarada."""
        if not self.origem_atual:
            return None
        return self.origem_atual.split(".", 1)[-1]


@dataclass(frozen=True)
class Sistema:
    """Um sistema estruturante catalogado."""

    id: str
    nome: str
    descricao: str
    orgao_gestor: str
    owner: str
    status: str
    entidades: dict[str, Entidade] = field(default_factory=dict)

    @property
    def schema_bronze(self) -> str:
        """Schema Bronze deste sistema, conforme ADR-0010."""
        return f"001_bnz_{self.id}"


@dataclass(frozen=True)
class Catalogo:
    """O catálogo completo: chaves conformadas, pontes e sistemas."""

    chaves: dict[str, Chave]
    pontes: tuple[Ponte, ...]
    sistemas: dict[str, Sistema]

    def sistema(self, id_sistema: str) -> Sistema:
        try:
            return self.sistemas[id_sistema]
        except KeyError:
            conhecidos = ", ".join(sorted(self.sistemas)) or "nenhum"
            raise ErroCatalogo(
                f"Sistema '{id_sistema}' não está catalogado. Catalogados: {conhecidos}."
            ) from None

    def entidade(self, id_sistema: str, id_entidade: str) -> Entidade:
        sistema = self.sistema(id_sistema)
        try:
            return sistema.entidades[id_entidade]
        except KeyError:
            conhecidas = ", ".join(sorted(sistema.entidades)) or "nenhuma"
            raise ErroCatalogo(
                f"Entidade '{id_entidade}' não existe em '{id_sistema}'. "
                f"Catalogadas: {conhecidas}."
            ) from None

    def ocorrencias(self, id_chave: str) -> list[tuple[Sistema, Entidade, Mapeamento]]:
        """Onde uma chave conformada aparece, em todos os sistemas."""
        achados = []
        for sistema in self.sistemas.values():
            for entidade in sistema.entidades.values():
                for mapeamento in entidade.chaves:
                    if mapeamento.chave == id_chave:
                        achados.append((sistema, entidade, mapeamento))
        return achados

    def pontes_de(self, id_chave: str) -> list[Ponte]:
        return [p for p in self.pontes if p.de == id_chave]


def classificacao_mais_restritiva(valores: Iterator[str] | list[str]) -> str:
    """Retorna a classificação mais restritiva entre as informadas (ADR-0013)."""
    posicao = -1
    for valor in valores:
        if valor in ORDEM_CLASSIFICACAO:
            posicao = max(posicao, ORDEM_CLASSIFICACAO.index(valor))
    # Sem classificação declarada, o padrão falha para o lado restritivo.
    return ORDEM_CLASSIFICACAO[posicao] if posicao >= 0 else "pessoal"


def _ler_yaml(caminho: Path) -> dict[str, Any]:
    try:
        conteudo = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ErroCatalogo(f"YAML inválido em {caminho}: {exc}") from exc
    if not isinstance(conteudo, dict):
        raise ErroCatalogo(f"{caminho} não contém um mapeamento YAML no topo.")
    return conteudo


def _texto(bruto: Any) -> str:
    return str(bruto).strip() if bruto is not None else ""


def carregar(dir_catalogo: Path | None = None) -> Catalogo:
    """Lê o catálogo do disco. Só falha quando o YAML é irrecuperável.

    Campos ausentes viram valores vazios em vez de exceção — quem aponta o que
    está faltando é ``validar``, para que um catálogo incompleto ainda possa ser
    inspecionado com ``mapa``.
    """
    base = dir_catalogo or DIR_CATALOGO
    arquivo_chaves = base / "chaves.yml"
    if not arquivo_chaves.is_file():
        raise ErroCatalogo(
            f"Arquivo de chaves conformadas não encontrado: {arquivo_chaves}"
        )

    bruto = _ler_yaml(arquivo_chaves)
    chaves = {
        id_chave: Chave(
            id=id_chave,
            nome=_texto(dados.get("nome")),
            descricao=_texto(dados.get("descricao")),
            normalizacao=_texto(dados.get("normalizacao")),
            classificacao=_texto(dados.get("classificacao")),
            sistema_de_referencia=_texto(dados.get("sistema_de_referencia")),
            tamanho=dados.get("tamanho"),
        )
        for id_chave, dados in (bruto.get("chaves") or {}).items()
        if isinstance(dados, dict)
    }
    pontes = tuple(
        Ponte(
            de=_texto(dados.get("de")),
            para=_texto(dados.get("para")),
            tipo=_texto(dados.get("tipo")),
            confiabilidade=_texto(dados.get("confiabilidade")),
            descricao=_texto(dados.get("descricao")),
            condicao=_texto(dados.get("condicao")) or None,
            observacao=_texto(dados.get("observacao")) or None,
        )
        for dados in (bruto.get("pontes") or [])
        if isinstance(dados, dict)
    )

    sistemas: dict[str, Sistema] = {}
    dir_sistemas = base / "sistemas"
    for arquivo in sorted(dir_sistemas.glob("*.yml")) if dir_sistemas.is_dir() else []:
        if arquivo.name.startswith("_"):
            continue
        sistema = _carregar_sistema(arquivo)
        sistemas[sistema.id] = sistema

    return Catalogo(chaves=chaves, pontes=pontes, sistemas=sistemas)


def _carregar_sistema(arquivo: Path) -> Sistema:
    bruto = _ler_yaml(arquivo)
    entidades: dict[str, Entidade] = {}
    for id_entidade, dados in (bruto.get("entidades") or {}).items():
        if not isinstance(dados, dict):
            continue
        entidades[id_entidade] = Entidade(
            id=id_entidade,
            descricao=_texto(dados.get("descricao")),
            granularidade=_texto(dados.get("granularidade")),
            dominio=_texto(dados.get("dominio")),
            classificacao=_texto(dados.get("classificacao")),
            chave_primaria=tuple(dados.get("chave_primaria") or ()),
            chaves=tuple(
                Mapeamento(
                    chave=_texto(m.get("chave")),
                    coluna=_texto(m.get("coluna")),
                    verificado=bool(m.get("verificado", False)),
                    opcional=bool(m.get("opcional", False)),
                    observacao=_texto(m.get("observacao")) or None,
                )
                for m in (dados.get("chaves") or [])
                if isinstance(m, dict)
            ),
            dag=_texto(dados.get("dag")) or None,
            origem_atual=_texto(dados.get("origem_atual")) or None,
        )

    return Sistema(
        id=_texto(bruto.get("sistema")) or arquivo.stem,
        nome=_texto(bruto.get("nome")),
        descricao=_texto(bruto.get("descricao")),
        orgao_gestor=_texto(bruto.get("orgao_gestor")),
        owner=_texto(bruto.get("owner")),
        status=_texto(bruto.get("status")),
        entidades=entidades,
    )
