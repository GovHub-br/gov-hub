"""DAG base de relatório periódico (ADR-0019).

Um relatório é a entrega do mesmo produto de dados a vários órgãos, cada um
enxergando só o seu recorte. É isso que esta factory encapsula: a consulta é
escrita uma vez, na DAG do órgão publicador, e executada uma vez por consumidor
declarado no plano de acesso — com o mesmo filtro de linhas que ele teria no
Superset (ADR-0020).

Fluxo: `carregar_entregas` lê o plano gerado e devolve uma entrega por
consumidor; `entregar` roda a consulta com o recorte daquele consumidor,
renderiza o arquivo e o coloca nos destinos declarados (storage, e-mail, ou
ambos). O mapeamento dinâmico dá retry por consumidor: um e-mail que falha não
refaz o relatório dos outros.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Sequence

import pandas as pd
import psycopg2
import yaml
from airflow.models import Variable
from airflow.sdk import dag, task

from cliente_email import enviar_email
from cliente_storage import ensure_bucket_exists, get_bucket, get_storage_fs
from postgres_helpers import get_postgres_conn

log = logging.getLogger(__name__)

# Prefixo dos relatórios na landing zone, ao lado do dado bruto ingerido.
PREFIXO_RELATORIOS = "relatorios"

FORMATOS = ("csv", "parquet")

# Marca obrigatória na consulta. Sem ela, o mesmo SQL iria para todos os
# consumidores sem recorte — que é justamente o acidente que a publicação
# compartilhada torna fácil cometer.
MARCA_RECORTE = "{recorte}"

# Variable com as credenciais de envio: host, port, usuario, senha, remetente.
VARIAVEL_SMTP = "smtp_credentials"


class ErroRelatorio(RuntimeError):
    """Relatório declarado de forma incoerente com o plano de acesso."""


def carregar_plano(caminho_plano: Path) -> dict[str, Any]:
    if not caminho_plano.is_file():
        raise ErroRelatorio(
            f"Plano de acesso não encontrado: {caminho_plano}. Rode: make publicacao-sync"
        )
    conteudo = yaml.safe_load(caminho_plano.read_text(encoding="utf-8"))
    return conteudo if isinstance(conteudo, dict) else {}


def carregar_entregas(caminho_plano: Path, id_relatorio: str) -> list[dict[str, Any]]:
    """As entregas de um relatório: um destinatário-órgão e seu recorte."""
    plano = carregar_plano(caminho_plano)
    for relatorio in plano.get("relatorios") or []:
        if relatorio.get("id") != id_relatorio:
            continue
        entregas = relatorio.get("entregas") or []
        if not entregas:
            raise ErroRelatorio(
                f"Relatório '{id_relatorio}' não tem nenhum consumidor atribuído no "
                "catálogo de publicação — não há a quem entregar."
            )
        return [
            {
                "consumidor": entrega.get("consumidor"),
                "clausula": entrega.get("clausula"),
                "destinos": relatorio.get("destinos") or [],
                "formato": relatorio.get("formato") or "csv",
                "destinatarios_variavel": relatorio.get("destinatarios_variavel"),
            }
            for entrega in entregas
        ]
    raise ErroRelatorio(
        f"Relatório '{id_relatorio}' não está no plano de acesso {caminho_plano.name}."
    )


def montar_consulta(consulta: str, clausula: str | None) -> str:
    """Aplica o recorte do consumidor à consulta do relatório.

    A cláusula não vem de entrada de usuário: ela é gerada pelo
    `make publicacao-sync` a partir de um código de órgão que a validação já
    exigiu ser só dígitos.
    """
    if MARCA_RECORTE not in consulta:
        raise ErroRelatorio(
            "A consulta do relatório precisa conter a marca "
            f"'{MARCA_RECORTE}' — é onde entra o recorte por órgão de cada "
            "consumidor. Use 'where {recorte}' e, se o relatório tiver outros "
            "filtros, componha com 'and'."
        )
    return consulta.replace(MARCA_RECORTE, clausula or "true")


def consultar(consulta: str, conn_key: str) -> pd.DataFrame:
    """Roda a consulta no warehouse e devolve o resultado com nome de coluna.

    O `close()` no finally é deliberado: o context manager do psycopg2 cuida da
    transação, não da conexão — sem isso, cada entrega deixaria uma conexão
    aberta no warehouse.
    """
    conexao = psycopg2.connect(get_postgres_conn(conn_key))
    try:
        with conexao.cursor() as cursor:
            cursor.execute(consulta)
            colunas = [descricao[0] for descricao in cursor.description or []]
            linhas = cursor.fetchall()
    finally:
        conexao.close()
    return pd.DataFrame(linhas, columns=colunas)


def renderizar(dados: pd.DataFrame, formato: str) -> bytes:
    if formato == "csv":
        return dados.to_csv(index=False).encode("utf-8")
    if formato == "parquet":
        buffer = BytesIO()
        dados.to_parquet(buffer, index=False)
        return buffer.getvalue()
    raise ErroRelatorio(
        f"Formato '{formato}' não suportado; use um de: {', '.join(FORMATOS)}."
    )


def nome_do_arquivo(
    id_relatorio: str, consumidor: str, data: datetime, formato: str
) -> str:
    return f"{id_relatorio}_{consumidor}_{data:%Y-%m-%d}.{formato}"


def caminho_no_storage(
    orgao: str, id_relatorio: str, consumidor: str, data: datetime, formato: str
) -> str:
    """Caminho do relatório na landing zone, particionado por data de execução."""
    return (
        f"{get_bucket()}/{PREFIXO_RELATORIOS}/{orgao}/{id_relatorio}/"
        f"{data:%Y/%m/%d}/{nome_do_arquivo(id_relatorio, consumidor, data, formato)}"
    )


def gravar_no_storage(conteudo: bytes, caminho: str) -> str:
    fs = get_storage_fs()
    ensure_bucket_exists(fs, get_bucket())
    with fs.open(caminho, "wb") as arquivo:
        arquivo.write(conteudo)
    log.info("[relatorio] %s bytes gravados em %s", len(conteudo), caminho)
    return caminho


def destinatarios_de(variavel: str | None, consumidor: str) -> list[str]:
    """Lê a lista de destinatários de um consumidor na Variable declarada.

    A Variable guarda um JSON ``{consumidor: [endereços]}``: endereço de pessoa
    é dado pessoal e não entra no repositório (ADR-0013).
    """
    if not variavel:
        return []
    bruto = Variable.get(variavel, default_var="{}")
    try:
        mapa = json.loads(bruto) if isinstance(bruto, str) else bruto
    except json.JSONDecodeError as exc:
        raise ErroRelatorio(
            f"Variable '{variavel}' não contém JSON válido: {exc}"
        ) from exc
    return list(mapa.get(consumidor) or [])


def credenciais_smtp() -> dict[str, Any]:
    """Credenciais de envio, lidas da Variable do Airflow.

    Falha com mensagem acionável em vez do `VARIABLE_NOT_FOUND` cru do Airflow:
    a ausência dessa Variable é erro de configuração do deployment, e quem lê o
    log precisa saber o que configurar.
    """
    bruto = Variable.get(VARIAVEL_SMTP, default_var=None)
    if not bruto:
        raise ErroRelatorio(
            f"Relatório com destino 'email' exige a Variable '{VARIAVEL_SMTP}' — "
            "JSON com host, port, usuario, senha e remetente. Configure-a no "
            "deployment, ou tire 'email' dos destinos do relatório no catálogo "
            "de publicação."
        )
    try:
        return json.loads(bruto) if isinstance(bruto, str) else bruto
    except json.JSONDecodeError as exc:
        raise ErroRelatorio(
            f"Variable '{VARIAVEL_SMTP}' não contém JSON válido: {exc}"
        ) from exc


def corpo_do_email(
    titulo: str, consumidor: str, linhas: int, data: datetime, recortado: bool
) -> str:
    recorte = (
        "Os dados estão restritos ao seu órgão."
        if recortado
        else "Os dados abrangem todos os órgãos."
    )
    return (
        f"{titulo}\n\n"
        f"Órgão destinatário: {consumidor}\n"
        f"Data de geração: {data:%d/%m/%Y}\n"
        f"Linhas no arquivo: {linhas}\n\n"
        f"{recorte}\n\n"
        "Relatório gerado automaticamente pelo Gov Hub. Em caso de divergência, "
        "procure a equipe responsável pelo produto de dados.\n"
    )


def build_relatorio_dag(
    dag_id: str,
    orgao: str,
    relatorio: str,
    titulo: str,
    consulta: str,
    caminho_plano: Path,
    schedule: str,
    start_date: datetime = datetime(2024, 1, 1),
    # A Gold vive no warehouse, não no banco de apoio do Airflow: o padrão
    # aponta para a connection do warehouse (criada por `make dev`).
    postgres_conn_key: str = "postgres_dw",
    owner: str | None = None,
    retries: int = 2,
    tags: Sequence[str] | None = None,
    description: str = "",
):
    """Monta a DAG de um relatório periódico a partir do plano de acesso.

    `consulta` é o SQL do relatório e precisa conter a marca ``{recorte}``, que
    a factory substitui pelo filtro de linhas de cada consumidor.
    """
    if MARCA_RECORTE not in consulta:
        raise ErroRelatorio(
            f"A consulta de '{dag_id}' não contém a marca '{MARCA_RECORTE}'. "
            "Sem ela, todo consumidor receberia as linhas de todos os órgãos."
        )

    default_args = {
        "owner": owner or orgao,
        "queue": orgao,
        "retries": retries,
        "retry_delay": timedelta(minutes=5),
    }

    @dag(
        dag_id=dag_id,
        schedule=schedule,
        start_date=start_date,
        catchup=False,
        default_args=default_args,
        description=description or f"Entrega o relatório '{relatorio}' ({titulo}).",
        tags=list(tags or []),
    )
    def _relatorio_dag() -> None:
        @task
        def listar_entregas() -> list[dict[str, Any]]:
            entregas = carregar_entregas(caminho_plano, relatorio)
            log.info(
                "[relatorio] %s: %s entrega(s) — %s",
                relatorio,
                len(entregas),
                ", ".join(e["consumidor"] for e in entregas),
            )
            return entregas

        @task
        def entregar(entrega: dict[str, Any], **contexto: Any) -> dict[str, Any]:
            consumidor = entrega["consumidor"]
            formato = entrega["formato"]
            destinos = entrega["destinos"]
            data = contexto.get("logical_date") or datetime.now()

            dados = consultar(
                montar_consulta(consulta, entrega["clausula"]), postgres_conn_key
            )
            conteudo = renderizar(dados, formato)
            log.info(
                "[relatorio] %s/%s: %s linha(s), %s bytes.",
                relatorio,
                consumidor,
                len(dados),
                len(conteudo),
            )

            resultado: dict[str, Any] = {
                "consumidor": consumidor,
                "linhas": len(dados),
                "caminho": None,
                "destinatarios": 0,
            }

            if "storage" in destinos:
                resultado["caminho"] = gravar_no_storage(
                    conteudo,
                    caminho_no_storage(orgao, relatorio, consumidor, data, formato),
                )

            if "email" in destinos:
                destinatarios = destinatarios_de(
                    entrega.get("destinatarios_variavel"), consumidor
                )
                if not destinatarios:
                    # Não é falha: um órgão pode consumir só pelo Superset ou
                    # ainda não ter informado a lista. O aviso deixa isso visível
                    # sem derrubar a entrega dos demais.
                    log.warning(
                        "[relatorio] %s/%s sem destinatários na Variable '%s'; "
                        "e-mail não enviado.",
                        relatorio,
                        consumidor,
                        entrega.get("destinatarios_variavel"),
                    )
                else:
                    enviar_email(
                        credenciais=credenciais_smtp(),
                        destinatarios=destinatarios,
                        assunto=f"{titulo} — {data:%m/%Y}",
                        corpo=corpo_do_email(
                            titulo,
                            consumidor,
                            len(dados),
                            data,
                            recortado=bool(entrega["clausula"]),
                        ),
                        anexos=[
                            (
                                nome_do_arquivo(relatorio, consumidor, data, formato),
                                conteudo,
                            )
                        ],
                    )
                    resultado["destinatarios"] = len(destinatarios)

            return resultado

        entregar.expand(entrega=listar_entregas())

    return _relatorio_dag()
