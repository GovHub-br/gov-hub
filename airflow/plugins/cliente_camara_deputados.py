import http
import logging
from typing import Any

from cliente_base import ClienteBase

# Cliente da API pública de Dados Abertos da Câmara dos Deputados. Cobre as
# três entidades do sistema camara_deputados: deputados, o histórico de
# mandato de cada deputado, e o cadastro (com logo) de cada partido.
#
# Portado de data-application-mir (plugins/cliente_deputados.py e
# plugins/cliente_partidos.py) — os dois clientes antigos falavam com a mesma
# API (mesma base_url), então viraram métodos de uma única classe aqui.


class ClienteCamaraDeputados(ClienteBase):
    """Cliente para a API de Dados Abertos da Câmara dos Deputados."""

    BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"
    BASE_HEADER = {"accept": "application/json"}
    PAGE_SIZE = 100

    def __init__(self) -> None:
        super().__init__(base_url=self.BASE_URL)

    # ── Deputados ────────────────────────────────────────────────────────────

    def get_deputados(self, **params: Any) -> list | None:
        """Uma página de deputados."""
        status, data = self.request(
            http.HTTPMethod.GET, "/deputados", headers=self.BASE_HEADER, params=params
        )
        if status == http.HTTPStatus.OK and isinstance(data, dict):
            return data.get("dados", [])
        logging.warning(
            "[cliente_camara_deputados] Falha ao buscar deputados: status=%s", status
        )
        return None

    def get_all_deputados(self) -> list:
        """Todos os deputados já registrados na API (sem recorte de data)."""
        todos: list[dict[str, Any]] = []
        pagina = 1
        while True:
            deputados = self.get_deputados(
                pagina=pagina, itens=self.PAGE_SIZE, dataInicio="1823-01-01"
            )
            if not deputados:
                break
            todos.extend(deputados)
            if len(deputados) < self.PAGE_SIZE:
                break
            pagina += 1
        return todos

    def get_deputados_atuais(self) -> list[dict[str, Any]] | None:
        """Deputados em exercício (sem recorte histórico, ao contrário de
        `get_all_deputados`, que devolve todos os deputados desde 1823).

        Devolve `None` (e não `[]`) quando a API falhar, para que quem chama
        não confunda "falha ao buscar" com "snapshot atual vazio" — distinção
        que a lógica de controle de histórico depende (ver
        `parlamentares_controle.py`). Portado de data-application-mir
        (``cliente_deputados.py``).
        """
        todos: list[dict[str, Any]] = []
        pagina = 1
        while True:
            deputados = self.get_deputados(pagina=pagina, itens=self.PAGE_SIZE)
            if deputados is None:
                logging.error(
                    "[cliente_camara_deputados] Falha ao buscar deputados atuais "
                    "na página=%s; abortando snapshot de atuais",
                    pagina,
                )
                return None
            if not deputados:
                break
            todos.extend(deputados)
            if len(deputados) < self.PAGE_SIZE:
                break
            pagina += 1
        return todos

    def get_historico_deputado(
        self, deputado_id: int | str
    ) -> list[dict[str, Any]] | None:
        """Histórico de mandato (filiação, situação, condição eleitoral) de um deputado."""
        status, data = self.request(
            http.HTTPMethod.GET,
            f"/deputados/{deputado_id}/historico",
            headers=self.BASE_HEADER,
        )
        if status == http.HTTPStatus.OK and isinstance(data, dict):
            historico = data.get("dados", [])
            if isinstance(historico, dict):
                return [historico]
            if isinstance(historico, list):
                return historico
        logging.warning(
            "[cliente_camara_deputados] Falha ao buscar histórico de deputado_id=%s: status=%s",
            deputado_id,
            status,
        )
        return None

    # ── Partidos ─────────────────────────────────────────────────────────────

    def get_partidos(self, **params: Any) -> list | None:
        """Uma página de partidos."""
        status, data = self.request(
            http.HTTPMethod.GET, "/partidos", headers=self.BASE_HEADER, params=params
        )
        if status == http.HTTPStatus.OK and isinstance(data, dict):
            return data.get("dados", [])
        logging.warning(
            "[cliente_camara_deputados] Falha ao buscar partidos: status=%s", status
        )
        return None

    def get_all_partidos(self) -> list:
        """Todos os partidos cadastrados."""
        todos: list[dict[str, Any]] = []
        pagina = 1
        while True:
            partidos = self.get_partidos(
                pagina=pagina, itens=100, ordem="ASC", ordenarPor="sigla"
            )
            if not partidos:
                break
            todos.extend(partidos)
            if len(partidos) < 100:
                break
            pagina += 1
        return todos

    def get_partido_by_id(self, partido_id: int | str) -> dict | None:
        """Detalhe de um partido específico, incluindo a URL do logo."""
        status, data = self.request(
            http.HTTPMethod.GET, f"/partidos/{partido_id}", headers=self.BASE_HEADER
        )
        if status == http.HTTPStatus.OK and isinstance(data, dict):
            return data.get("dados", {})
        logging.warning(
            "[cliente_camara_deputados] Falha ao buscar partido_id=%s: status=%s",
            partido_id,
            status,
        )
        return None
