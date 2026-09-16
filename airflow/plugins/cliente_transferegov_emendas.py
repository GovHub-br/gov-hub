import http
import logging
from typing import Optional

from cliente_base import ClienteBase

# Cliente da API de Transferências Especiais (emendas parlamentares
# individuais) do TransfereGov. API PostgREST 100% nacional/genérica — nenhum
# endpoint aceita ou exige filtro de órgão (ver catalogo/sistemas/
# transferegov_emendas.yml para o racional de onde as DAGs de ingestão
# vivem). Portado de data-application-mir (plugins/cliente_transferegov_
# emendas.py), consolidando os pares get_<entidade>/get_all_<entidade>
# (paginação manual + paginação automática) em dois métodos genéricos.


class ClienteTransfereGov(ClienteBase):
    """Cliente para a API de Transferências Especiais do TransfereGov."""

    BASE_URL = "https://api.transferegov.gestao.gov.br/transferenciasespeciais/"
    BASE_HEADER = {"accept": "application/json", "User-Agent": "Airflow-GovHub/1.0"}

    def __init__(self) -> None:
        super().__init__(base_url=ClienteTransfereGov.BASE_URL)

    def _get_pagina(
        self, endpoint: str, order_by: Optional[str], limit: int, offset: int
    ) -> Optional[list]:
        """Uma página de um endpoint PostgREST, ordenada pela chave informada."""
        params: dict = {"select": "*", "limit": limit, "offset": offset}
        if order_by:
            params["order"] = f"{order_by}.asc"

        status, data = self.request(
            http.HTTPMethod.GET, endpoint, headers=self.BASE_HEADER, params=params
        )
        if status == http.HTTPStatus.OK and isinstance(data, list):
            return data
        logging.warning(
            "[cliente_transferegov_emendas] Falha ao buscar %s (offset=%s): status=%s",
            endpoint,
            offset,
            status,
        )
        return None

    def _get_todos(
        self, endpoint: str, order_by: Optional[str], page_size: int = 1000
    ) -> list:
        """Pagina automaticamente um endpoint até esgotar os registros."""
        all_data: list = []
        offset = 0
        page = 1
        while True:
            pagina = self._get_pagina(endpoint, order_by, page_size, offset)
            if not pagina:
                break
            all_data.extend(pagina)
            logging.info(
                "[cliente_transferegov_emendas] %s: página %s (%s registros, total %s)",
                endpoint,
                page,
                len(pagina),
                len(all_data),
            )
            if len(pagina) < page_size:
                break
            offset += page_size
            page += 1
        return all_data

    def get_all_programas_especiais(self, page_size: int = 1000) -> list:
        """Todos os programas especiais (transferências especiais nacionais)."""
        return self._get_todos("programa_especial", "id_programa", page_size)

    def get_all_executores_especiais(self, page_size: int = 1000) -> list:
        """Todos os executores especiais, globalmente."""
        return self._get_todos("executor_especial", "id_executor", page_size)

    def get_all_empenhos_especiais(self, page_size: int = 1000) -> list:
        """Todos os empenhos especiais, globalmente."""
        return self._get_todos("empenho_especial", "id_empenho", page_size)

    def get_all_relatorio_gestao_especial(self, page_size: int = 1000) -> list:
        """Todos os relatórios de gestão (situação e parecer final)."""
        return self._get_todos(
            "relatorio_gestao_especial", "id_relatorio_gestao", page_size
        )

    def get_all_documentos_habeis_especiais(self, page_size: int = 1000) -> list:
        """Todos os documentos hábeis especiais, globalmente."""
        return self._get_todos("documento_habil_especial", "id_dh", page_size)

    def get_all_metas_especiais(self, page_size: int = 1000) -> list:
        """Todas as metas físicas/financeiras por executor."""
        return self._get_todos("meta_especial", "id_meta", page_size)

    def get_all_finalidades_especiais(self, page_size: int = 1000) -> list:
        """Todas as finalidades (áreas de política pública) por executor."""
        return self._get_todos("finalidade_especial", "id_executor", page_size)

    def get_all_ordens_bancarias_especiais(self, page_size: int = 1000) -> list:
        """Todas as ordens de pagamento/ordens bancárias, globalmente."""
        return self._get_todos(
            "ordem_pagamento_ordem_bancaria_especial", "id_op_ob", page_size
        )

    def get_all_relatorios_gestao_novo_especial(self, page_size: int = 1000) -> list:
        """Todos os registros do novo relatório de gestão, globalmente."""
        return self._get_todos(
            "relatorio_gestao_novo_especial", "id_relatorio_gestao_novo", page_size
        )

    def get_all_plano_trabalho_especial(self, page_size: int = 1000) -> list:
        """Todos os planos de trabalho especiais, globalmente."""
        return self._get_todos("plano_trabalho_especial", "id_plano_trabalho", page_size)

    def get_all_historico_pagamentos_especiais(self, page_size: int = 1000) -> list:
        """Todo o histórico de eventos das ordens de pagamento, globalmente."""
        return self._get_todos(
            "historico_pagamento_especial", "id_historico_op_ob", page_size
        )

    def get_all_planos_acao_especiais_by_programa(
        self, id_programa: int, page_size: int = 1000
    ) -> list:
        """Todos os planos de ação especiais de um programa (a API não expõe
        um endpoint "todos os programas" para plano_acao_especial — é
        preciso iterar por id_programa)."""
        return self._get_todos(
            f"plano_acao_especial?id_programa=eq.{id_programa}", None, page_size
        )
