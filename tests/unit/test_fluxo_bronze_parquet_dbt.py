"""Exercita o fluxo Parquet → Bronze → Silver de cada domínio DuckDB.

Roda os SQLs reais (a Bronze via `gov_bricks.bronze_parquet`, a Silver do
domínio e os testes genéricos `mesma_contagem` e `mesmo_conteudo_em_snake_case`)
num DuckDB local, com o object storage emulado em disco, sem serviços externos.

Sem `chave` na amostra, a Silver é a inicial: só renomeia e preserva a Bronze.
Com `chave`, é tratada: a linha com chave nula é descartada, e a Silver tem uma
linha por chave, a de maior `dt_ingest`. Nesse modo, o teste não roda os
genéricos `mesma_contagem` e `mesmo_conteudo_em_snake_case` e exige que o
schema.yml não os declare, mas declare `not_null` em cada coluna da chave e
`unique`, se a chave é simples, ou `gov_bricks.unicidade_composta`, se composta.

Limitação conhecida: a amostra anula só a última coluna da chave; uma Silver
composta que filtre nulo só nessa coluna passa.

Cada Bronze em Parquet precisa de uma amostra em AMOSTRAS: é o único dado por
domínio; o resto do teste vale para qualquer um.
"""

import os
import re
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import NotRequired, TypedDict

import duckdb
import pytest
import yaml
from fsspec.implementations.dirfs import DirFileSystem
from fsspec.implementations.local import LocalFileSystem
from jinja2 import Environment, StrictUndefined

RAIZ = Path(__file__).resolve().parents[2]
DBT = RAIZ / "airflow/dags/dbt"
SISTEMA = "compras_gov"
PACOTE = DBT / SISTEMA
MACROS = DBT / "gov_bricks/macros"

CLASSIFICACOES = {"publico", "interno", "pessoal", "pessoal_sensivel"}


class Amostra(TypedDict):
    colunas: list[str]
    tipos: dict[str, str]
    # Colunas da raw (camelCase) que identificam o registro na fonte. Sem chave,
    # a Silver é a inicial; com chave, a tratada, que deduplica por ela.
    chave: NotRequired[list[str]]
    # Silver tratada com chave conformada (ex.: slv_orgao), que o modo `chave`
    # ainda não cobre: só confere a deduplicação e o descarte do nulo.
    silver_tratada: NotRequired[bool]


# Contrato observado nos Parquets de cada entidade: colunas na ordem em que
# chegam da raw e os tipos que não são texto, para detectar conversão acidental.
AMOSTRAS: dict[str, Amostra] = {
    "orgao": {
        "colunas": ["codigoOrgao", "nomeOrgao", "dt_ingest"],
        "tipos": {},
        "silver_tratada": True,
    },
    "arp": {
        "colunas": [
            "numeroAtaRegistroPreco",
            "codigoUnidadeGerenciadora",
            "nomeUnidadeGerenciadora",
            "codigoOrgao",
            "nomeOrgao",
            "linkAtaPNCP",
            "linkCompraPNCP",
            "numeroCompra",
            "anoCompra",
            "codigoModalidadeCompra",
            "nomeModalidadeCompra",
            "dataAssinatura",
            "dataVigenciaInicial",
            "dataVigenciaFinal",
            "valorTotal",
            "statusAta",
            "objeto",
            "quantidadeItens",
            "dataHoraAtualizacao",
            "dataHoraInclusao",
            "dataHoraExclusao",
            "ataExcluido",
            "numeroControlePncpAta",
            "numeroControlePncpCompra",
            "idCompra",
            "dt_ingest",
        ],
        "tipos": {
            "codigoOrgao": "BIGINT",
            "quantidadeItens": "BIGINT",
            "valorTotal": "DOUBLE",
            "ataExcluido": "BOOLEAN",
        },
    },
}

VALORES = {
    "BIGINT": 48000,
    "DOUBLE": 12.5,
    "BOOLEAN": True,
    "VARCHAR": "  original  ",
    "INTEGER": 7,
}

BRONZES = sorted(p.stem for p in (PACOTE / "models/bronze").glob("*.sql"))


class _Retorno(Exception):
    """Equivalente ao MacroReturn do dbt: carrega o valor do `return()`."""

    def __init__(self, valor):
        self.valor = valor


def _retornar(valor):
    raise _Retorno(valor)


def _chamar(macro, *args, **kwargs):
    try:
        return macro(*args, **kwargs)
    except _Retorno as retorno:
        return retorno.valor


def _modulo(texto, **contexto):
    return (
        Environment(undefined=StrictUndefined)
        .from_string(texto)
        .make_module({"return": _retornar, **contexto})
    )


def _gov_bricks(conexao, entidade):
    """O namespace `gov_bricks` que o dbt injeta, com os macros reais.

    `{% test %}` é sintaxe do dbt; aqui ele vira `{% macro test_<nome> %}`,
    que é o que o próprio dbt faz ao carregar um teste genérico.
    """
    gov_bricks = SimpleNamespace()
    testes = re.sub(
        r"{%\s*test\s+(\w+)\(", r"{% macro test_\1(", (MACROS / "testes.sql").read_text()
    )
    testes = re.sub(r"{%\s*endtest\s*%}", "{% endmacro %}", testes)
    adapter = SimpleNamespace(
        quote=lambda nome: f'"{nome}"',
        get_columns_in_relation=lambda relacao: [
            SimpleNamespace(name=linha[0])
            for linha in conexao.sql(f"describe {relacao}").fetchall()
        ],
    )
    modulo_testes = _modulo(
        testes,
        adapter=adapter,
        execute=True,
        exceptions=SimpleNamespace(raise_compiler_error=pytest.fail),
        modules=SimpleNamespace(re=re),
        gov_bricks=gov_bricks,
    )
    modulo_bronze = _modulo(
        (MACROS / "bronze_parquet.sql").read_text(),
        env_var=os.getenv,
        model=SimpleNamespace(package_name=SISTEMA, name=entidade),
    )
    gov_bricks.snake_case = lambda nome: _chamar(modulo_testes.snake_case, nome)
    gov_bricks.bronze_parquet = modulo_bronze.bronze_parquet
    # A normalização real é coberta em test_macros_dbt.py.
    gov_bricks.chave_conformada = lambda chave, coluna: f"cast({coluna} as varchar)"
    gov_bricks.teste = lambda nome, **kw: str(
        getattr(modulo_testes, f"test_{nome}")(**kw)
    )
    return gov_bricks


def _renderizar(caminho, gov_bricks):
    return (
        Environment(undefined=StrictUndefined)
        .from_string(caminho.read_text())
        .render(gov_bricks=gov_bricks, ref=lambda nome: f'"{nome}"')
    )


def _le_a_bronze(texto, entidade):
    """O SQL dá `ref()` na Bronze da entidade, com aspas simples ou duplas."""
    padrao = r"ref\(\s*['\"]" + re.escape(entidade) + r"['\"]\s*\)"
    return re.search(padrao, texto) is not None


def _metadados(silver):
    """Entrada da Silver no schema.yml da pasta do domínio. A pasta tem um
    schema.yml só, que documenta todas as Silvers do domínio."""
    modelos = yaml.safe_load(silver.with_name("schema.yml").read_text())["models"]
    (metadados,) = [m for m in modelos if m["name"] == silver.stem]
    return metadados


def _linhas_tratadas(colunas, tipos, chave):
    nova = {c: VALORES[tipos[c]] for c in colunas} | {"dt_ingest": "2026-10-02 00:00:00"}
    texto = next(
        c
        for c in colunas
        if tipos[c] == "VARCHAR" and c not in chave and c != "dt_ingest"
    )
    antiga = nova | {texto: "versão antiga", "dt_ingest": "2026-10-01 00:00:00"}
    ultima = chave[-1]
    valor = nova[ultima]
    outra = nova | {ultima: f"{valor} outra" if isinstance(valor, str) else valor + 1}
    nula = nova | {ultima: None}
    linhas = [[linha[c] for c in colunas] for linha in (antiga, nova, nova, outra, nula)]
    return linhas, [tuple(linha[c] for c in colunas) for linha in (nova, outra)]


def _nome_teste(teste):
    return teste if isinstance(teste, str) else next(iter(teste))


def _silver_sobre(entidade):
    """A Silver de um domínio DuckDB que lê a Bronze da entidade."""
    (silver,) = [
        p
        for p in (PACOTE / "models/silver").glob("*/*.sql")
        if _le_a_bronze(p.read_text(), entidade)
    ]
    return silver


def test_toda_bronze_parquet_tem_amostra():
    assert set(BRONZES) == set(AMOSTRAS)


@pytest.mark.parametrize("bucket", [None, "outro-bucket"])
@pytest.mark.parametrize("entidade", BRONZES)
def test_bronze_e_silver_preservam_linhas_valores_e_tipos(
    tmp_path, monkeypatch, entidade, bucket
):
    if bucket is None:
        monkeypatch.delenv("MINIO_BUCKET", raising=False)
    else:
        monkeypatch.setenv("MINIO_BUCKET", bucket)
    colunas = AMOSTRAS[entidade]["colunas"]
    tipos = {c: AMOSTRAS[entidade]["tipos"].get(c, "VARCHAR") for c in colunas}
    chave = AMOSTRAS[entidade].get("chave")

    class S3Local(DirFileSystem):
        protocol = "s3"

    with duckdb.connect() as conexao:
        conexao.register_filesystem(S3Local(path=str(tmp_path), fs=LocalFileSystem()))
        gov_bricks = _gov_bricks(conexao, entidade)

        declaracoes = ", ".join(f'"{c}" {tipos[c]}' for c in colunas)
        conexao.execute(f"create table amostra ({declaracoes})")
        linha = [VALORES[tipos[c]] for c in colunas]
        linhas, esperadas = [linha, linha, [None] * len(colunas)], []
        if chave:
            linhas, esperadas = _linhas_tratadas(colunas, tipos, chave)
        conexao.executemany(
            f"insert into amostra values ({', '.join('?' for _ in colunas)})", linhas
        )
        pasta = tmp_path / (bucket or "data-lake") / SISTEMA / entidade / "2026/10"
        pasta.mkdir(parents=True)
        conexao.execute("copy amostra to ? (format parquet)", [str(pasta / "p.parquet")])

        sql_bronze = _renderizar(PACOTE / "models/bronze" / f"{entidade}.sql", gov_bricks)
        assert f"s3://{bucket or 'data-lake'}/{SISTEMA}/{entidade}/" in sql_bronze
        conexao.execute(f'create table "{entidade}" as {sql_bronze}')

        silver = _silver_sobre(entidade)
        sql_silver = _renderizar(silver, gov_bricks)
        if AMOSTRAS[entidade].get("silver_tratada"):
            # Duas linhas iguais e uma nula na Bronze: sobra um órgão só, sem o nulo.
            conexao.execute(f'create table "{silver.stem}" as {sql_silver}')
            assert conexao.sql(f'select count(*) from "{silver.stem}"').fetchone() == (1,)
            assert conexao.sql(f'select count(*) from "{entidade}"').fetchone() == (3,)
            return
        for _ in range(2):
            conexao.execute(f'create or replace table "{silver.stem}" as {sql_silver}')
            if chave:
                # A Bronze guarda todas as versões; a Silver, só a nova de cada chave.
                bronze = conexao.sql(f'select count(*) from "{entidade}"').fetchone()
                assert bronze == (len(linhas),)
                nomes = ", ".join(gov_bricks.snake_case(c) for c in colunas)
                assert Counter(
                    conexao.sql(f'select {nomes} from "{silver.stem}"').fetchall()
                ) == Counter(esperadas)
            else:
                assert Counter(
                    conexao.sql(f'select * from "{silver.stem}"').fetchall()
                ) == Counter(conexao.sql(f'select * from "{entidade}"').fetchall())

        # Mesmo tipo em cada coluna, pelo nome em snake_case.
        descricao = conexao.sql(f'describe "{silver.stem}"').fetchall()
        tipos_silver = {nome: tipo for nome, tipo, *_ in descricao}
        assert tipos_silver == {gov_bricks.snake_case(c): tipos[c] for c in colunas}

        # schema.yml documenta exatamente as colunas da Silver, na ordem.
        metadados = _metadados(silver)
        assert [c["name"] for c in metadados["columns"]] == list(tipos_silver)
        assert all(
            c["description"] and c["meta"]["classificacao"] in CLASSIFICACOES
            for c in metadados["columns"]
        )

        if chave:
            # Silver tratada: chave única e não nula, sem os testes da Silver inicial,
            # que exigem as mesmas linhas da Bronze.
            do_modelo = metadados.get("data_tests", [])
            assert not {_nome_teste(t) for t in do_modelo} & {
                "gov_bricks.mesma_contagem",
                "gov_bricks.mesmo_conteudo_em_snake_case",
            }
            da_coluna = {
                c["name"]: {_nome_teste(t) for t in c.get("data_tests", [])}
                for c in metadados["columns"]
            }
            chave_silver = [gov_bricks.snake_case(c) for c in chave]
            assert all("not_null" in da_coluna[c] for c in chave_silver)
            if len(chave_silver) == 1:
                assert "unique" in da_coluna[chave_silver[0]]
            else:
                assert {
                    "gov_bricks.unicidade_composta": {
                        "arguments": {"colunas": chave_silver}
                    }
                } in do_modelo
        else:
            # Os testes genéricos passam e detectam divergência.
            def teste(nome):
                sql = gov_bricks.teste(
                    nome, model=f'"{silver.stem}"', comparar_com=f'"{entidade}"'
                )
                return conexao.sql(sql).fetchall()

            assert teste("mesma_contagem") == []
            assert teste("mesmo_conteudo_em_snake_case") == []
            texto = gov_bricks.snake_case(
                next(c for c in colunas if tipos[c] == "VARCHAR")
            )
            conexao.execute(
                f"update \"{silver.stem}\" set {texto} = 'alterado' where {texto} is not null"
            )
            assert teste("mesma_contagem") == []
            assert len(teste("mesmo_conteudo_em_snake_case")) == 4
            conexao.execute(f'delete from "{silver.stem}" where {texto} is null')
            assert len(teste("mesma_contagem")) == 1


@pytest.mark.parametrize("entidade", BRONZES)
def test_bronze_materializada_e_declarada_no_catalogo_e_no_source(entidade):
    """A Bronze em Parquet substitui a tabela raw como origem da entidade."""
    catalogo = yaml.safe_load((RAIZ / f"catalogo/sistemas/{SISTEMA}.yml").read_text())
    assert catalogo["entidades"][entidade]["origem_atual"] == (
        f"001_bnz_{SISTEMA}.{entidade}"
    )
    fontes = {
        f["name"]: f
        for f in yaml.safe_load((PACOTE / "models/bronze/sources.yml").read_text())[
            "sources"
        ]
    }
    bronze = fontes[f"{SISTEMA}_bronze"]
    assert bronze["schema"] == f"001_bnz_{SISTEMA}"
    assert entidade in {t["identifier"] for t in bronze["tables"]}
    assert entidade not in {t["name"] for t in fontes[SISTEMA]["tables"]}
    assert _le_a_bronze(_silver_sobre(entidade).read_text(), entidade)


def test_metadados_acham_a_silver_pelo_nome_com_tres_no_dominio(tmp_path):
    (tmp_path / "schema.yml").write_text(
        "models:\n"
        "  - {name: slv_a, columns: [{name: a}]}\n"
        "  - {name: slv_b, columns: [{name: b}]}\n"
        "  - {name: slv_c, columns: [{name: c}]}\n"
    )
    for nome in ("a", "b", "c"):
        assert _metadados(tmp_path / f"slv_{nome}.sql")["columns"] == [{"name": nome}]


@pytest.mark.parametrize(
    "nome,esperado",
    [
        ("numeroAtaRegistroPreco", "numero_ata_registro_preco"),
        ("linkAtaPNCP", "link_ata_pncp"),
        ("numeroControlePncpAta", "numero_controle_pncp_ata"),
        ("CNPJFornecedor", "cnpj_fornecedor"),
        ("valor2Etapa", "valor2_etapa"),
        ("objeto", "objeto"),
        ("dt_ingest", "dt_ingest"),
    ],
)
def test_snake_case_trata_siglas_como_uma_palavra(nome, esperado):
    with duckdb.connect() as conexao:
        assert _gov_bricks(conexao, "x").snake_case(nome) == esperado
