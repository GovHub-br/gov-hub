"""Testes da DAG base de relatório (ADR-0019).

O que se testa aqui é sobretudo o recorte: um relatório entregue a vários
órgãos com a cláusula errada vaza a execução de um órgão para outro, e esse é
um erro que não aparece em nenhum log — o arquivo chega bonito, com dados de
quem não devia.
"""

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

import relatorio_dag_factory as factory

pytestmark = pytest.mark.unit

RAIZ = Path(__file__).resolve().parents[2]
PLANO_MGI = RAIZ / "airflow" / "dags" / "superset" / "mgi" / "acesso.yml"

CONSULTA = "select co_orgao from tabela where {recorte}"


class TestRecorteNaConsulta:
    def test_aplica_a_clausula_do_consumidor(self) -> None:
        assert (
            factory.montar_consulta(CONSULTA, "co_orgao = '25206'")
            == "select co_orgao from tabela where co_orgao = '25206'"
        )

    def test_abrangencia_total_vira_predicado_verdadeiro(self) -> None:
        assert factory.montar_consulta(CONSULTA, None).endswith("where true")

    def test_consulta_sem_a_marca_e_recusada(self) -> None:
        with pytest.raises(factory.ErroRelatorio) as erro:
            factory.montar_consulta("select 1 from tabela", "co_orgao = '1'")
        assert "{recorte}" in str(erro.value)

    def test_dag_sem_a_marca_nao_e_construida(self) -> None:
        """Falha na construção, não em execução: o erro precisa aparecer no CI."""
        with pytest.raises(factory.ErroRelatorio):
            factory.build_relatorio_dag(
                dag_id="x_mgi_report_dag",
                orgao="mgi",
                relatorio="x",
                titulo="X",
                consulta="select 1",
                caminho_plano=PLANO_MGI,
                schedule="@monthly",
            )


class TestEntregasDoPlano:
    def test_le_uma_entrega_por_consumidor(self) -> None:
        entregas = factory.carregar_entregas(PLANO_MGI, "contratacoes_mensal")
        assert {e["consumidor"] for e in entregas} == {"ipea", "mgi"}

    def test_traz_o_recorte_de_cada_um(self) -> None:
        entregas = {
            e["consumidor"]: e["clausula"]
            for e in factory.carregar_entregas(PLANO_MGI, "contratacoes_mensal")
        }
        assert entregas["ipea"] == "co_orgao = '25206'"
        assert entregas["mgi"] is None

    def test_traz_formato_e_destinos_declarados(self) -> None:
        # Os valores esperados são os declarados em catalogo/publicacao/mgi.yml e
        # regerados em acesso.yml por `make publicacao-sync`: mudou lá, muda aqui.
        # `destinatarios_variavel` segue declarada mesmo sem o destino `email`,
        # que a factory só lê quando o destino está presente.
        entrega = factory.carregar_entregas(PLANO_MGI, "contratacoes_mensal")[0]
        assert entrega["formato"] == "csv"
        assert set(entrega["destinos"]) == {"storage"}
        assert entrega["destinatarios_variavel"]

    def test_relatorio_fora_do_plano_falha(self) -> None:
        with pytest.raises(factory.ErroRelatorio):
            factory.carregar_entregas(PLANO_MGI, "relatorio_inventado")

    def test_plano_ausente_indica_o_comando_que_o_gera(self, tmp_path: Path) -> None:
        with pytest.raises(factory.ErroRelatorio) as erro:
            factory.carregar_entregas(tmp_path / "acesso.yml", "qualquer")
        assert "publicacao-sync" in str(erro.value)


class TestRenderizacao:
    def _dados(self) -> pd.DataFrame:
        return pd.DataFrame({"co_orgao": ["25206"], "numerocontrato": ["12/2026"]})

    def test_csv_tem_cabecalho_e_linha(self) -> None:
        conteudo = factory.renderizar(self._dados(), "csv").decode("utf-8")
        assert conteudo.splitlines()[0] == "co_orgao,numerocontrato"
        assert "25206" in conteudo

    def test_parquet_volta_igual(self) -> None:
        from io import BytesIO

        conteudo = factory.renderizar(self._dados(), "parquet")
        assert pd.read_parquet(BytesIO(conteudo)).equals(self._dados())

    def test_formato_desconhecido_falha(self) -> None:
        with pytest.raises(factory.ErroRelatorio):
            factory.renderizar(self._dados(), "xlsx")


class TestDestinoEEnvio:
    def test_caminho_no_storage_e_particionado_por_data(self, monkeypatch) -> None:
        monkeypatch.setattr(factory, "get_bucket", lambda: "data-lake")
        caminho = factory.caminho_no_storage(
            "mgi", "contratacoes_mensal", "ipea", datetime(2026, 3, 1), "csv"
        )
        assert caminho == (
            "data-lake/relatorios/mgi/contratacoes_mensal/2026/03/01/"
            "contratacoes_mensal_ipea_2026-03-01.csv"
        )

    def test_destinatarios_vem_da_variable_por_consumidor(self, monkeypatch) -> None:
        class VariableFalsa:
            @staticmethod
            def get(nome, default_var=None):
                return '{"ipea": ["dados@ipea.gov.br"], "mgi": []}'

        monkeypatch.setattr(factory, "Variable", VariableFalsa)
        assert factory.destinatarios_de("qualquer", "ipea") == ["dados@ipea.gov.br"]
        assert factory.destinatarios_de("qualquer", "mgi") == []
        assert factory.destinatarios_de("qualquer", "desconhecido") == []

    def test_sem_variable_declarada_nao_ha_destinatario(self) -> None:
        assert factory.destinatarios_de(None, "ipea") == []

    def test_variable_invalida_falha_com_mensagem_clara(self, monkeypatch) -> None:
        class VariableFalsa:
            @staticmethod
            def get(nome, default_var=None):
                return "isto não é json"

        monkeypatch.setattr(factory, "Variable", VariableFalsa)
        with pytest.raises(factory.ErroRelatorio):
            factory.destinatarios_de("qualquer", "ipea")

    def test_corpo_do_email_diz_se_houve_recorte(self) -> None:
        com = factory.corpo_do_email("T", "ipea", 3, datetime(2026, 3, 1), recortado=True)
        sem = factory.corpo_do_email("T", "mgi", 3, datetime(2026, 3, 1), recortado=False)
        assert "restritos ao seu órgão" in com
        assert "todos os órgãos" in sem


class TestCredenciaisSmtp:
    def test_ausencia_da_variable_diz_o_que_configurar(self, monkeypatch) -> None:
        class VariableFalsa:
            @staticmethod
            def get(nome, default_var=None):
                return default_var

        monkeypatch.setattr(factory, "Variable", VariableFalsa)
        with pytest.raises(factory.ErroRelatorio) as erro:
            factory.credenciais_smtp()
        assert factory.VARIAVEL_SMTP in str(erro.value)
        assert "destinos" in str(erro.value)

    def test_json_invalido_falha_com_mensagem_clara(self, monkeypatch) -> None:
        class VariableFalsa:
            @staticmethod
            def get(nome, default_var=None):
                return "{isto não é json}"

        monkeypatch.setattr(factory, "Variable", VariableFalsa)
        with pytest.raises(factory.ErroRelatorio):
            factory.credenciais_smtp()

    def test_devolve_as_credenciais_declaradas(self, monkeypatch) -> None:
        class VariableFalsa:
            @staticmethod
            def get(nome, default_var=None):
                return '{"host": "smtp.exemplo.gov.br", "port": 587}'

        monkeypatch.setattr(factory, "Variable", VariableFalsa)
        assert factory.credenciais_smtp() == {"host": "smtp.exemplo.gov.br", "port": 587}
