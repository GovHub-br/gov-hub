"""Utilitários de particionamento para o fan-out das DAGs de ingestão.

O Airflow materializa uma task instance por elemento passado a `.expand()`.
Expandir sobre uma lista grande — os ~10 mil órgãos, por exemplo — cria
milhares de TIs numa única execução: estoura o `core.max_map_length` (1024 por
padrão) e sobrecarrega o scheduler e o banco de metadados. Estas funções
transformam a lista em poucos blocos, e a task itera dentro de cada bloco.
"""

import logging
import os
from typing import TypeVar

T = TypeVar("T")


def chunked(items: list[T], size: int) -> list[list[T]]:
    """Divide `items` em blocos de até `size` elementos, na ordem original.

    Ex.: chunked([1, 2, 3, 4, 5], 2) → [[1, 2], [3, 4], [5]]. Use quando a DAG
    expande sobre uma lista já materializada (órgãos, itens de catálogo): cada
    bloco vira uma task instance que itera sobre seus elementos.
    """
    if size < 1:
        raise ValueError(f"size deve ser >= 1, recebido {size}")
    return [items[i : i + size] for i in range(0, len(items), size)]


def page_starts(total_pages: int, block_size: int, start: int = 1) -> list[int]:
    """Páginas iniciais de cada bloco, para DAGs que paginam a fonte.

    Ex.: page_starts(40, 15) → [1, 16, 31]. Cada task cobre `block_size`
    páginas a partir do valor retornado.
    """
    if block_size < 1:
        raise ValueError(f"block_size deve ser >= 1, recebido {block_size}")
    return list(range(start, total_pages + start, block_size))


def block_offsets(total: int, block_size: int) -> list[int]:
    """Offsets iniciais de cada bloco sobre uma sequência de `total` itens.

    Ex.: block_offsets(400, 150) → [0, 150, 300]. Cada task fatia a sequência
    em `[offset : offset + block_size]`.
    """
    if block_size < 1:
        raise ValueError(f"block_size deve ser >= 1, recebido {block_size}")
    return list(range(0, total, block_size))


def limit_local(items: list[T], env_var: str, label: str = "itens") -> list[T]:
    """Trunca a lista quando `env_var` define um teto — só para rodar local.

    Em produção a variável fica ausente e a lista passa intacta. No compose
    local, definir `env_var` (ex.: INGEST_MAX_ORGAOS=10) encurta a ingestão
    para caber num teste rápido. Um valor não inteiro ou negativo é ignorado.
    """
    teto = os.getenv(env_var)
    if not teto:
        return items
    try:
        n = int(teto)
    except ValueError:
        logging.warning("[batching] %s='%s' não é inteiro; ignorando.", env_var, teto)
        return items
    if n < 0 or len(items) <= n:
        return items
    logging.warning(
        "[batching] %s=%s ativo: limitando %s de %s para %s (execução local).",
        env_var,
        n,
        label,
        len(items),
        n,
    )
    return items[:n]
