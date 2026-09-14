import http
import logging
from typing import Any

from cliente_base import ClienteBase

# Cliente da API pública de Dados Abertos do Senado Federal. Cobre as quatro
# entidades do sistema senado_federal: senadores, as filiações partidárias de
# cada senador (simplificadas e em formato bruto) e as legislaturas.
#
# Portado de data-application-mir (plugins/cliente_senadores.py).


class ClienteSenadoFederal(ClienteBase):
    """Cliente para a API de Dados Abertos do Senado Federal."""

    BASE_URL = "https://legis.senado.leg.br/dadosabertos"
    BASE_HEADER = {"accept": "application/json"}

    def __init__(self) -> None:
        super().__init__(base_url=self.BASE_URL)

    def get_senadores_por_legislatura(self) -> list:
        """Todos os senadores (ativos e inativos) desde a legislatura 0."""
        status, data = self.request(
            http.HTTPMethod.GET,
            "/senador/lista/legislatura/0/100",
            headers=self.BASE_HEADER,
        )
        if status != http.HTTPStatus.OK or not isinstance(data, dict):
            logging.warning(
                "[cliente_senado_federal] Falha ao buscar senadores por legislatura: status=%s",
                status,
            )
            return []
        try:
            raiz = data.get("ListaParlamentarLegislatura", {})
            parlamentares = raiz.get("Parlamentares", {}).get("Parlamentar", [])
            if isinstance(parlamentares, dict):
                parlamentares = [parlamentares]
            return parlamentares
        except Exception as exc:
            logging.error(
                "[cliente_senado_federal] Erro ao parsear senadores por legislatura: %s",
                exc,
            )
            return []

    def get_senadores_atuais(self) -> list:
        """Senadores em exercício."""
        status, data = self.request(
            http.HTTPMethod.GET, "/senador/lista/atual", headers=self.BASE_HEADER
        )
        if status != http.HTTPStatus.OK or not isinstance(data, dict):
            logging.warning(
                "[cliente_senado_federal] Falha ao buscar senadores atuais: status=%s",
                status,
            )
            return []
        try:
            raiz = data.get("ListaParlamentarEmExercicio", {})
            parlamentares = raiz.get("Parlamentares", {}).get("Parlamentar", [])
            if isinstance(parlamentares, dict):
                parlamentares = [parlamentares]
            return parlamentares
        except Exception as exc:
            logging.error(
                "[cliente_senado_federal] Erro ao parsear senadores atuais: %s", exc
            )
            return []

    def get_filiacoes_senador(self, senador_id: int | str) -> list[dict[str, Any]] | None:
        """Histórico bruto de filiações partidárias de um senador."""
        status, data = self.request(
            http.HTTPMethod.GET,
            f"/senador/{senador_id}/filiacoes",
            headers=self.BASE_HEADER,
            params={"v": 5},
        )
        if status != http.HTTPStatus.OK or not isinstance(data, dict):
            logging.warning(
                "[cliente_senado_federal] Falha ao buscar filiações de senador_id=%s: status=%s",
                senador_id,
                status,
            )
            return None
        try:
            raiz = data.get(
                "FiliacaoParlamentar", data.get("ListaFiliacoesParlamentar", {})
            )
            parlamentar = raiz.get("Parlamentar")
            if isinstance(parlamentar, dict):
                raiz = parlamentar
            filiacao = raiz.get("Filiacoes", {}).get("Filiacao", [])
            if isinstance(filiacao, dict):
                return [filiacao]
            if isinstance(filiacao, list) and filiacao:
                return filiacao
            return None
        except Exception as exc:
            logging.error(
                "[cliente_senado_federal] Erro ao parsear filiações de senador_id=%s: %s",
                senador_id,
                exc,
            )
            return None

    def get_periodo_legislacao(self) -> list:
        """Período de vigência e data de eleição de cada legislatura."""
        status, data = self.request(
            http.HTTPMethod.GET, "/dados/ListaLegislatura.json", headers=self.BASE_HEADER
        )
        if status != http.HTTPStatus.OK or not isinstance(data, dict):
            logging.warning(
                "[cliente_senado_federal] Falha ao buscar legislaturas: status=%s", status
            )
            return []
        try:
            raiz = data.get("ListaLegislatura", {})
            legislaturas = raiz.get("Legislaturas", {}).get("Legislatura", [])
            if isinstance(legislaturas, dict):
                legislaturas = [legislaturas]
            return legislaturas
        except Exception as exc:
            logging.error(
                "[cliente_senado_federal] Erro ao parsear legislaturas: %s", exc
            )
            return []
