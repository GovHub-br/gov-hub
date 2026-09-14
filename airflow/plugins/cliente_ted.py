import http
import logging

from cliente_base import ClienteBase

# Cliente da API de TED (Termo de Execução Descentralizada) do TransfereGov.
# Diferente da API de Transferências Especiais (cliente_transferegov_emendas.py),
# esta API é consumida com escopo real de órgão: `get_programas_by_sigla_
# unidade_descentralizadora` filtra explicitamente pela sigla (ver
# catalogo/sistemas/transferegov_ted.yml para o racional de onde as DAGs de
# ingestão vivem). Portado de data-application-mir (plugins/cliente_ted.py),
# mantendo só os métodos usados pelas 4 DAGs de ingestão deste sistema.


class ClienteTed(ClienteBase):
    """Cliente para a API de TED (Termo de Execução Descentralizada) do TransfereGov."""

    BASE_URL = "https://api.transferegov.gestao.gov.br/ted/"
    BASE_HEADER = {"accept": "application/json"}

    def __init__(self) -> None:
        super().__init__(base_url=ClienteTed.BASE_URL)

    def _get(self, endpoint: str, contexto: str) -> list | None:
        status, data = self.request(
            http.HTTPMethod.GET, endpoint, headers=self.BASE_HEADER
        )
        if status == http.HTTPStatus.OK and isinstance(data, list):
            return data
        logging.warning("[cliente_ted] Falha ao buscar %s: status=%s", contexto, status)
        return None

    def get_programas_by_sigla_unidade_descentralizadora(self, sigla: str) -> list | None:
        """Programas de TED filtrados pela sigla da unidade descentralizadora."""
        endpoint = f"programa?sigla_unidade_descentralizadora=eq.{sigla}"
        return self._get(endpoint, f"programas (sigla={sigla})")

    def get_planos_acao_by_id_programa(self, id_programa: str) -> list | None:
        """Planos de ação de um programa de TED."""
        endpoint = f"plano_acao?id_programa=eq.{id_programa}"
        return self._get(endpoint, f"planos de ação (id_programa={id_programa})")

    def get_programacao_financeira_by_id_plano_acao(
        self, id_plano_acao: str
    ) -> list | None:
        """Programação financeira de um plano de ação de TED."""
        endpoint = f"programacao_financeira?id_plano_acao=eq.{id_plano_acao}"
        return self._get(
            endpoint, f"programação financeira (id_plano_acao={id_plano_acao})"
        )

    def get_notas_de_credito_by_id_plano_acao(self, id_plano_acao: str) -> list | None:
        """Notas de crédito de um plano de ação de TED."""
        endpoint = f"nota_credito?id_plano_acao=eq.{id_plano_acao}"
        return self._get(endpoint, f"notas de crédito (id_plano_acao={id_plano_acao})")
