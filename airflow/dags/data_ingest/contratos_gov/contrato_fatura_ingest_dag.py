"""
DAG de ingestão das faturas dos contratos do Contratos.gov.br.

Endpoint: GET /api/contrato/{contrato_id}/faturas
Fonte: https://contratos.comprasnet.gov.br (API aberta, sem autenticação)

Mesmo desenho da contrato_publicacao_ingest_dag e contrato_historico_ingest_dag:
o endpoint não pagina nem filtra por período, então cada execução consulta, uma
vez cada, os contratos de contrato_ativo e contrato_inativo que pertencem aos
órgãos da Variable contratos_gov_escopo_orgaos (docs/notas/contratos-gov-ingestao.md).
O recorte temporal fica para a Silver, pelos campos de data do payload (emissao,
vencimento, data_liquidacao, mesref/anoref).

Por que distinct_raw_rows, e não distinct_raw_values só com id?
    O recorte por órgão precisa de orgao_codigo ao lado de cada id; com só o id
    não haveria como restringir ao escopo antes de criar as chamadas. Ids
    repetidos entre ativos e inativos (contrato inativado entre varreduras)
    viram um só no conjunto.

Por que contrato_id é conferido contra a URL?
    O payload de fatura traz o campo contrato_id. O cliente confere se o valor
    devolvido coincide com o {contrato_id} da URL (injetando se vier nulo) e
    falha em caso de divergência. A função _deduplicar_faturas repete essa
    validação como barreira de integridade antes da escrita.

Por que a chave primária é só id?
    Cada fatura/instrumento de cobrança tem id numérico global no sistema de
    origem. No backend warehouse, write_raw faz upsert por `id`; no
    object_storage a raw é append-only e a Silver deduplica por dt_ingest.

Por que listas aninhadas ficam como JSON na raw?
    O payload traz dados_empenho, dados_item_faturado e dados_referencia
    aninhados. A raw preserva a estrutura como veio da fonte para que a Silver
    faça a explosão e tipagem analítica.

Por que cada contrato grava com run_id próprio?
    No object_storage, o arquivo da raw é nomeado pelo run_id, e esta DAG grava
    uma vez por contrato dentro do mesmo run: com o run_id da execução, cada
    contrato sobrescreveria o arquivo do anterior e só o último sobreviveria.
    O sufixo __contrato_{id} dá um arquivo por contrato; o retry do mesmo
    contrato reescreve o mesmo arquivo com o mesmo conteúdo. No warehouse o
    run_id não é usado.

Por que contrato sem fatura não falha a DAG?
    Contrato sem fatura emitida responde 200 []. A ausência de faturas é normal
    para contratos recém-assinados ou sem execução financeira. A execução inteira
    sem nenhuma fatura só é tratada como anomalia da fonte quando cobriu pelo
    menos MIN_CONTRATOS_PARA_EXIGIR_FATURA contratos.

Por que blocos em vez de .expand() sobre os contratos?
    Expandir sobre a lista crua criaria uma task instance por contrato e
    estouraria o core.max_map_length (1024). Cada bloco itera internamente
    (airflow/helpers/batching.py), e o tamanho do bloco cresce se o escopo
    passar de MAX_BLOCOS blocos.

Por que não roda inteira na máquina do desenvolvedor?
    A varredura completa são milhares de chamadas, estimadas em horas. No
    compose, INGEST_MAX_CONTRATOS (local.env) trunca a lista e é com essa
    amostra que a DAG é validada; a primeira execução completa acontece em
    homologação. Com o INGEST_MAX_UGS local, a raw de cabeçalhos pode não ter
    contrato de nenhum órgão do escopo: aí a DAG falha dizendo isso, em vez de
    seguir sem ter o que consultar.

Horário: sábado às 13:30, no escalonamento de 30 em 30 minutos dos sub-recursos
    a partir das 12:00 (histórico #20 às 12:00, itens #21 às 12:30, empenhos #22
    às 13:00, faturas #23 às 13:30, cronograma #24 às 14:00, publicações #25 às 14:30).
"""

import logging
from datetime import datetime, timedelta
from math import ceil
from typing import Any

from airflow.sdk import Variable, dag, get_current_context, task
from batching import chunked, limit_local
from cliente_contratos_gov import ClienteContratosGov
from landing_zone import RawIndisponivel, distinct_raw_rows, write_raw

SISTEMA = "contratos_gov"
ENTIDADE = "contrato_fatura"
RECURSO = "faturas"
ENTIDADES_CONTRATO = ("contrato_ativo", "contrato_inativo")
PK = ["id"]
BLOCK_SIZE = 50
MAX_BLOCOS = 1024
MIN_CONTRATOS_PARA_EXIGIR_FATURA = 10
VARIAVEL_ESCOPO = "contratos_gov_escopo_orgaos"
ESCOPO_PADRAO = ["46000"]

default_args = {
    "owner": "mgi",
    "queue": "mgi",
    "retries": 3,
    "retry_delay": timedelta(minutes=10),
}


def _orgaos_no_escopo() -> set[str]:
    """Lê a Variable e recusa o que não for lista de códigos de órgão de 5 dígitos.

    Um código inválido (inteiro sem zero à esquerda, por exemplo) não casaria com
    nenhum orgao_codigo da raw, e a DAG concluiria sem consultar nada.
    """
    escopo = Variable.get(VARIAVEL_ESCOPO, default=ESCOPO_PADRAO, deserialize_json=True)
    if (
        not isinstance(escopo, list)
        or not escopo
        or any(
            not isinstance(codigo, str) or len(codigo) != 5 or not codigo.isdigit()
            for codigo in escopo
        )
    ):
        raise RuntimeError(
            f"Variable '{VARIAVEL_ESCOPO}' deve ser uma lista JSON não vazia de "
            'códigos de órgão com cinco dígitos, por exemplo ["46000"].'
        )
    return set(escopo)


def _deduplicar_faturas(
    contrato_id: str, registros: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Valida o lote antes da escrita.

    Linha idêntica repetida é descartada; o mesmo id com conteúdo diferente é
    anomalia da fonte e interrompe antes de gravar, porque o upsert por id
    manteria só uma das versões sem avisar.
    """
    unicos: dict[str, dict[str, Any]] = {}
    for indice, registro in enumerate(registros):
        if str(registro.get("contrato_id")) != contrato_id:
            raise RuntimeError(
                f"[/api/contrato/{contrato_id}/{RECURSO}] Registro {indice} com "
                f"contrato_id divergente da URL ({registro.get('contrato_id')!r} != {contrato_id!r})."
            )
        fatura_id = registro.get("id")
        if fatura_id is None:
            raise RuntimeError(
                f"[/api/contrato/{contrato_id}/{RECURSO}] Registro {indice} sem id; "
                "as faturas deste contrato não serão gravadas."
            )
        if unicos.setdefault(str(fatura_id), registro) != registro:
            raise RuntimeError(
                f"[/api/contrato/{contrato_id}/{RECURSO}] id {fatura_id!r} "
                "repetido na resposta com conteúdo diferente."
            )
    return list(unicos.values())


def _run_id_da_execucao() -> str | None:
    """run_id da execução em curso; None quando a task é chamada fora do Airflow.

    Sem contexto (em teste), write_raw gera sozinho um identificador.
    """
    try:
        return str(get_current_context()["run_id"])
    except Exception:
        return None


@dag(
    dag_id="contrato_fatura_ingest_dag",
    schedule="30 13 * * 6",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    description=(
        "Ingere as faturas dos contratos da API Contratos.gov.br "
        "(GET /api/contrato/{contrato_id}/faturas) para "
        "contratos_gov.raw_contrato_fatura, em blocos e no escopo dos órgãos "
        "consumidores."
    ),
    tags=["sistema:contratos_gov", "dominio:contratacoes"],
)
def contrato_fatura_dag() -> None:
    @task
    def get_contract_blocks() -> list[list[str]]:
        orgaos = _orgaos_no_escopo()
        ids: set[str] = set()
        for entidade in ENTIDADES_CONTRATO:
            try:
                linhas = distinct_raw_rows(SISTEMA, entidade, ["id", "orgao_codigo"])
            except RawIndisponivel as exc:
                raise RuntimeError(
                    f"Entidade '{entidade}' ainda não está na zona raw. Execute "
                    f"{entidade}_ingest_dag antes de contrato_fatura_ingest_dag."
                ) from exc
            except Exception as exc:
                raise RuntimeError(
                    f"Entidade '{entidade}' ainda não está na zona raw. Execute "
                    f"{entidade}_ingest_dag antes de contrato_fatura_ingest_dag."
                ) from exc

            for contrato_id, orgao_codigo in linhas:
                if str(orgao_codigo) not in orgaos:
                    continue
                if isinstance(contrato_id, bool) or not str(contrato_id).isdigit():
                    raise RuntimeError(
                        f"A raw de {entidade} tem id de contrato inválido para o "
                        f"órgão {orgao_codigo}: {contrato_id!r}."
                    )
                ids.add(str(contrato_id))

        if not ids:
            raise RuntimeError(
                f"Nenhum contrato dos órgãos {sorted(orgaos)} nas raws de "
                "contrato_ativo e contrato_inativo. Confira a Variable "
                f"'{VARIAVEL_ESCOPO}' e as DAGs de cabeçalho."
            )

        contratos = limit_local(sorted(ids, key=int), "INGEST_MAX_CONTRATOS", "contratos")
        if not contratos:
            raise RuntimeError(
                "INGEST_MAX_CONTRATOS deixou a lista vazia: configure um limite "
                "positivo para validar a ingestão local."
            )
        tamanho = max(BLOCK_SIZE, ceil(len(contratos) / MAX_BLOCOS))
        blocos = chunked(contratos, tamanho)
        logging.info(
            "Contratos a consultar: %s em %s blocos de até %s",
            len(contratos),
            len(blocos),
            tamanho,
        )
        return blocos

    @task(max_active_tis_per_dag=4)
    def ingest_contracts(contrato_ids: list[str]) -> dict[str, int]:
        api = ClienteContratosGov()
        run_id = _run_id_da_execucao()
        faturas = 0
        vazios = 0
        repetidas = 0

        for contrato_id in contrato_ids:
            registros = api.listar_subrecurso(contrato_id, RECURSO)
            if not registros:
                vazios += 1
                logging.info("Contrato %s: nenhuma fatura.", contrato_id)
                continue

            lote = _deduplicar_faturas(contrato_id, registros)
            if len(lote) < len(registros):
                repetidas += len(registros) - len(lote)
                logging.warning(
                    "Contrato %s: %s linha(s) idêntica(s) repetida(s) descartada(s).",
                    contrato_id,
                    len(registros) - len(lote),
                )

            write_raw(
                SISTEMA,
                ENTIDADE,
                lote,
                primary_key=PK,
                run_id=f"{run_id}__contrato_{contrato_id}" if run_id else None,
            )
            faturas += len(lote)
            logging.info("Contrato %s: faturas=%s", contrato_id, len(lote))

        return {
            "faturas": faturas,
            "contratos": len(contrato_ids),
            "contratos_vazios": vazios,
            "linhas_repetidas": repetidas,
        }

    @task
    def validate(results: Any) -> int:
        total = sum(r["faturas"] for r in results)
        contratos = sum(r["contratos"] for r in results)
        vazios = sum(r["contratos_vazios"] for r in results)
        repetidas = sum(r["linhas_repetidas"] for r in results)
        logging.info(
            "Faturas total: faturas=%s contratos=%s contratos_vazios=%s "
            "linhas_repetidas=%s blocos=%s",
            total,
            contratos,
            vazios,
            repetidas,
            len(results),
        )

        if total == 0:
            if contratos < MIN_CONTRATOS_PARA_EXIGIR_FATURA:
                logging.warning(
                    "Nenhuma fatura nos %s contratos consultados. Abaixo de %s "
                    "contratos isso é plausível, então a execução segue.",
                    contratos,
                    MIN_CONTRATOS_PARA_EXIGIR_FATURA,
                )
                return total
            raise RuntimeError(
                f"Nenhuma fatura em nenhum dos {contratos} contratos consultados. "
                "A fonte devolver tudo vazio é anomalia, não realidade: interrompendo "
                "antes de a Silver ler uma raw incompleta."
            )
        return total

    blocos = get_contract_blocks()
    validate(ingest_contracts.expand(contrato_ids=blocos))


contrato_fatura_dag()
