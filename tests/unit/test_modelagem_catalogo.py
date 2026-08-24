"""Testes do carregamento e da validação do catálogo (ADR-0017)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from scripts.modelagem.catalogo import (
    ErroCatalogo,
    carregar,
    classificacao_mais_restritiva,
)
from scripts.modelagem.validacao import tem_erro, validar

CHAVES_MINIMAS = """
versao: 1
chaves:
  co_orgao:
    nome: Código do órgão
    descricao: Código do órgão no Poder Executivo federal.
    normalizacao: digitos
    tamanho: 5
    sistema_de_referencia: siorg
    classificacao: publico
  nu_cpf:
    nome: CPF
    descricao: Cadastro de Pessoa Física, sem máscara.
    normalizacao: digitos
    tamanho: 11
    sistema_de_referencia: receita_federal
    classificacao: pessoal
pontes:
  - de: co_orgao
    para: nu_cpf
    tipo: derivacao_condicional
    condicao: nunca
    confiabilidade: indicio
    descricao: Ponte artificial, só para teste.
"""

SISTEMA_MINIMO = """
sistema: sistema_teste
nome: Sistema de Teste
descricao: Sistema fictício usado nos testes.
orgao_gestor: xpto
owner: "@GovHub-br/oss"
status: ingerido
entidades:
  pessoas:
    descricao: Pessoas cadastradas.
    granularidade: uma linha por pessoa
    dominio: pessoal
    origem_atual: bruto.raw_pessoas
    chave_primaria: [id_pessoa]
    classificacao: pessoal
    chaves:
      - chave: co_orgao
        coluna: cd_orgao
        verificado: true
"""


@pytest.fixture
def catalogo_dir(tmp_path: Path) -> Path:
    (tmp_path / "sistemas").mkdir(parents=True)
    (tmp_path / "chaves.yml").write_text(
        textwrap.dedent(CHAVES_MINIMAS), encoding="utf-8"
    )
    (tmp_path / "sistemas" / "sistema_teste.yml").write_text(
        textwrap.dedent(SISTEMA_MINIMO), encoding="utf-8"
    )
    return tmp_path


def test_carrega_chaves_entidades_e_mapeamentos(catalogo_dir: Path) -> None:
    catalogo = carregar(catalogo_dir)

    assert set(catalogo.chaves) == {"co_orgao", "nu_cpf"}
    assert catalogo.chaves["co_orgao"].tamanho == 5
    entidade = catalogo.entidade("sistema_teste", "pessoas")
    assert entidade.chaves[0].chave == "co_orgao"
    assert entidade.chaves[0].verificado is True
    assert entidade.schema_origem == "bruto"
    assert entidade.tabela_origem == "raw_pessoas"


def test_schema_bronze_segue_adr_0010(catalogo_dir: Path) -> None:
    assert carregar(catalogo_dir).sistema("sistema_teste").schema_bronze == (
        "001_bnz_sistema_teste"
    )


def test_arquivos_com_underscore_sao_ignorados(catalogo_dir: Path) -> None:
    (catalogo_dir / "sistemas" / "_template.yml").write_text(
        textwrap.dedent(SISTEMA_MINIMO).replace("sistema_teste", "modelo"),
        encoding="utf-8",
    )
    assert set(carregar(catalogo_dir).sistemas) == {"sistema_teste"}


def test_sistema_desconhecido_lista_os_conhecidos(catalogo_dir: Path) -> None:
    catalogo = carregar(catalogo_dir)
    with pytest.raises(ErroCatalogo, match="sistema_teste"):
        catalogo.sistema("siafi")


def test_ocorrencias_encontram_a_chave_em_todos_os_sistemas(catalogo_dir: Path) -> None:
    ocorrencias = carregar(catalogo_dir).ocorrencias("co_orgao")
    assert [(s.id, e.id, m.coluna) for s, e, m in ocorrencias] == [
        ("sistema_teste", "pessoas", "cd_orgao")
    ]


def test_catalogo_valido_nao_produz_erro(catalogo_dir: Path) -> None:
    problemas = validar(carregar(catalogo_dir), catalogo_dir)
    assert not tem_erro(problemas)


def test_ponte_indicio_gera_aviso_nao_erro(catalogo_dir: Path) -> None:
    problemas = validar(carregar(catalogo_dir), catalogo_dir)
    avisos = [p for p in problemas if "indicio" in p.mensagem]
    assert avisos and all(p.nivel == "aviso" for p in avisos)


def test_chave_inexistente_em_entidade_e_erro(catalogo_dir: Path) -> None:
    arquivo = catalogo_dir / "sistemas" / "sistema_teste.yml"
    arquivo.write_text(
        arquivo.read_text(encoding="utf-8").replace(
            "chave: co_orgao", "chave: co_inexistente"
        ),
        encoding="utf-8",
    )
    problemas = validar(carregar(catalogo_dir), catalogo_dir)
    assert tem_erro(problemas)
    assert any("co_inexistente" in p.mensagem for p in problemas if p.nivel == "erro")


def test_ponte_para_chave_inexistente_e_erro(catalogo_dir: Path) -> None:
    arquivo = catalogo_dir / "chaves.yml"
    arquivo.write_text(
        arquivo.read_text(encoding="utf-8").replace("para: nu_cpf", "para: nao_existe"),
        encoding="utf-8",
    )
    assert tem_erro(validar(carregar(catalogo_dir), catalogo_dir))


def test_sistema_ingerido_sem_origem_atual_e_erro(catalogo_dir: Path) -> None:
    arquivo = catalogo_dir / "sistemas" / "sistema_teste.yml"
    arquivo.write_text(
        arquivo.read_text(encoding="utf-8").replace(
            "    origem_atual: bruto.raw_pessoas\n", ""
        ),
        encoding="utf-8",
    )
    problemas = validar(carregar(catalogo_dir), catalogo_dir)
    assert tem_erro(problemas)
    assert any("origem_atual" in p.mensagem for p in problemas)


def test_mapeamento_nao_verificado_e_aviso_nao_erro(catalogo_dir: Path) -> None:
    arquivo = catalogo_dir / "sistemas" / "sistema_teste.yml"
    arquivo.write_text(
        arquivo.read_text(encoding="utf-8").replace(
            "verificado: true", "verificado: false"
        ),
        encoding="utf-8",
    )
    problemas = validar(carregar(catalogo_dir), catalogo_dir)
    assert not tem_erro(problemas)
    assert any("não verificado" in p.mensagem for p in problemas)


def test_nome_de_arquivo_precisa_bater_com_o_campo_sistema(catalogo_dir: Path) -> None:
    origem = catalogo_dir / "sistemas" / "sistema_teste.yml"
    origem.rename(catalogo_dir / "sistemas" / "outro_nome.yml")
    problemas = validar(carregar(catalogo_dir), catalogo_dir)
    assert tem_erro(problemas)


def test_catalogo_sem_chaves_yml_falha_alto(tmp_path: Path) -> None:
    with pytest.raises(ErroCatalogo, match="chaves conformadas"):
        carregar(tmp_path)


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (["publico", "interno"], "interno"),
        (["publico", "pessoal", "interno"], "pessoal"),
        (["pessoal", "pessoal_sensivel"], "pessoal_sensivel"),
        (["publico"], "publico"),
        ([], "pessoal"),
        (["desconhecido"], "pessoal"),
    ],
)
def test_classificacao_do_modelo_e_a_mais_restritiva(entrada, esperado) -> None:
    assert classificacao_mais_restritiva(entrada) == esperado


def test_catalogo_real_do_repositorio_e_valido() -> None:
    """O catálogo versionado precisa passar na própria validação."""
    problemas = validar(carregar())
    assert not tem_erro(problemas), "\n".join(str(p) for p in problemas)
