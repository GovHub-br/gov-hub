"""Cliente da API do Superset usado pelas DAGs de publicação (ADR-0019).

Cobre só o que a publicação precisa e faz isso de forma idempotente: importar
um bundle de ativos exportado do Superset, garantir os papéis do plano de
acesso, conceder a cada papel os datasets que ele alcança e instalar o recorte
de linhas (Row Level Security) de quem não tem abrangência total.

Nenhuma operação assume estado anterior — rodar a DAG duas vezes seguidas leva
o Superset ao mesmo lugar. É o que permite tratar o repositório como fonte de
verdade da publicação, e não como um passo manual documentado.

Escrito contra a API v1 do Superset da linha 4.x — é a versão da imagem do
compose (perfil `bi`).
"""

from __future__ import annotations

import io
import json
import logging
import os
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import requests
import yaml

log = logging.getLogger(__name__)

TIMEOUT_PADRAO = 120

# Permissão do Superset que dá acesso de leitura a um dataset.
PERMISSAO_DATASET = "datasource_access"
# Nome do view_menu de um dataset, na convenção do próprio Superset
# (SqlaTable.get_perm): "[database].[tabela](id:N)".
VIEW_MENU_DATASET = "[{database}].[{tabela}](id:{id_dataset})"

PASTA_DATABASES = "databases"


class ErroSuperset(RuntimeError):
    """Falha de comunicação com o Superset ou resposta inesperada."""


def senhas_do_bundle(caminho_bundle: Path) -> dict[str, str]:
    """Mapa ``{arquivo_no_zip: senha}`` que o import do Superset espera.

    A senha do warehouse não é versionada em lugar nenhum: ela viaja fora do
    bundle, no campo ``passwords`` do próprio import, lida do ambiente.
    """
    senha = os.environ.get("SUPERSET_DW_PASSWORD", "")
    if not senha:
        return {}
    return {
        f"{PASTA_DATABASES}/{arquivo.name}": senha
        for arquivo in sorted((caminho_bundle / PASTA_DATABASES).glob("*.yaml"))
    }


def montar_zip(
    caminho_bundle: Path, uri: str | None = None, raiz: str | None = None
) -> bytes:
    """Empacota um bundle exportado (pasta de YAML) no zip que o import espera.

    O Superset exige que todo arquivo esteja sob uma pasta raiz única dentro do
    zip — é dela que ele deriva o nome do import.

    Quando ``uri`` é informada, a conexão declarada no bundle é reescrita para
    ela **na memória**: o bundle versionado traz uma URI de placeholder, porque
    host e usuário mudam entre compose local, homologação e produção. O arquivo
    em disco nunca é alterado.
    """
    if not caminho_bundle.is_dir():
        raise ErroSuperset(f"Bundle não encontrado: {caminho_bundle}")

    nome_raiz = raiz or caminho_bundle.name
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_bundle:
        for arquivo in sorted(caminho_bundle.rglob("*")):
            if not arquivo.is_file() or arquivo.suffix not in (".yaml", ".yml"):
                continue
            relativo = arquivo.relative_to(caminho_bundle).as_posix()
            bruto = arquivo.read_bytes()
            if uri and relativo.startswith(f"{PASTA_DATABASES}/"):
                conteudo = yaml.safe_load(bruto.decode("utf-8")) or {}
                conteudo["sqlalchemy_uri"] = uri
                bruto = yaml.safe_dump(
                    conteudo, sort_keys=False, allow_unicode=True
                ).encode("utf-8")
            zip_bundle.writestr(f"{nome_raiz}/{relativo}", bruto)
    return buffer.getvalue()


@dataclass
class ClienteSuperset:
    """Sessão autenticada na API do Superset."""

    base_url: str
    usuario: str
    senha: str
    provider: str = "db"
    timeout: int = TIMEOUT_PADRAO
    sessao: requests.Session = field(default_factory=requests.Session)
    _token: str | None = field(default=None, init=False, repr=False)
    _csrf: str | None = field(default=None, init=False, repr=False)
    _permissoes: dict[str, int] | None = field(default=None, init=False, repr=False)

    # ----------------------------------------------------------------- base

    def _url(self, caminho: str) -> str:
        return f"{self.base_url.rstrip('/')}{caminho}"

    def autenticar(self) -> None:
        """Obtém o token de acesso e o token CSRF, nessa ordem.

        O CSRF só é emitido para uma sessão já autenticada, e o Superset exige
        os dois em toda escrita.
        """
        resposta = self.sessao.post(
            self._url("/api/v1/security/login"),
            json={
                "username": self.usuario,
                "password": self.senha,
                "provider": self.provider,
                "refresh": True,
            },
            timeout=self.timeout,
        )
        if resposta.status_code != 200:
            raise ErroSuperset(
                f"Login no Superset falhou ({resposta.status_code}): {resposta.text[:300]}"
            )
        self._token = resposta.json().get("access_token")
        if not self._token:
            raise ErroSuperset("Login no Superset não devolveu access_token.")

        csrf = self.sessao.get(
            self._url("/api/v1/security/csrf_token/"),
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=self.timeout,
        )
        if csrf.status_code != 200:
            raise ErroSuperset(
                f"Não foi possível obter o token CSRF ({csrf.status_code}): {csrf.text[:300]}"
            )
        self._csrf = csrf.json().get("result")
        log.info(
            "[cliente_superset] Autenticado em %s como %s.", self.base_url, self.usuario
        )

    def _cabecalhos(self) -> dict[str, str]:
        if not self._token:
            self.autenticar()
        cabecalhos = {"Authorization": f"Bearer {self._token}"}
        if self._csrf:
            cabecalhos["X-CSRFToken"] = self._csrf
            cabecalhos["Referer"] = self.base_url
        return cabecalhos

    def requisitar(self, metodo: str, caminho: str, **kwargs: Any) -> dict[str, Any]:
        cabecalhos = {**self._cabecalhos(), **kwargs.pop("headers", {})}
        resposta = self.sessao.request(
            metodo,
            self._url(caminho),
            headers=cabecalhos,
            timeout=kwargs.pop("timeout", self.timeout),
            **kwargs,
        )
        if resposta.status_code >= 400:
            raise ErroSuperset(
                f"{metodo} {caminho} falhou ({resposta.status_code}): {resposta.text[:500]}"
            )
        if not resposta.content:
            return {}
        try:
            return resposta.json()
        except ValueError:
            return {"texto": resposta.text}

    @staticmethod
    def _filtro(coluna: str, valor: str) -> str:
        """Monta o Rison de filtro que a API do Superset espera em `q`."""
        return f"(filters:!((col:{coluna},opr:eq,value:'{valor}')))"

    # -------------------------------------------------------------- ativos

    def importar_bundle(
        self,
        caminho_bundle: Path,
        uri_database: str | None = None,
        sobrescrever: bool = True,
    ) -> None:
        """Importa um bundle de ativos (databases, datasets, gráficos, dashboards)."""
        conteudo = montar_zip(caminho_bundle, uri_database)
        senhas = senhas_do_bundle(caminho_bundle)

        dados: dict[str, str] = {"overwrite": "true" if sobrescrever else "false"}
        if senhas:
            dados["passwords"] = json.dumps(senhas)

        self.requisitar(
            "POST",
            "/api/v1/assets/import/",
            files={"bundle": (f"{caminho_bundle.name}.zip", conteudo, "application/zip")},
            data=dados,
        )
        log.info("[cliente_superset] Bundle '%s' importado.", caminho_bundle.name)

    # ------------------------------------------------------------ datasets

    def id_do_dataset(self, tabela: str, schema: str | None = None) -> int | None:
        """Id do dataset pelo nome da tabela (e schema, quando informado)."""
        filtros = [f"(col:table_name,opr:eq,value:'{tabela}')"]
        if schema:
            filtros.append(f"(col:schema,opr:eq,value:'{schema}')")
        consulta = f"(filters:!({','.join(filtros)}))"
        resultado = self.requisitar("GET", f"/api/v1/dataset/?q={consulta}")
        for item in resultado.get("result", []):
            return int(item["id"])
        return None

    # -------------------------------------------------------------- papéis

    def id_do_papel(self, nome: str) -> int | None:
        resultado = self.requisitar(
            "GET", f"/api/v1/security/roles/?q={self._filtro('name', nome)}"
        )
        for item in resultado.get("result", []):
            return int(item["id"])
        return None

    def garantir_papel(self, nome: str) -> int:
        """Cria o papel se ele não existir; devolve o id em qualquer caso."""
        existente = self.id_do_papel(nome)
        if existente is not None:
            return existente
        criado = self.requisitar("POST", "/api/v1/security/roles/", json={"name": nome})
        id_papel = criado.get("id")
        if id_papel is None:
            raise ErroSuperset(f"Criação do papel '{nome}' não devolveu id: {criado}")
        log.info("[cliente_superset] Papel '%s' criado (id %s).", nome, id_papel)
        return int(id_papel)

    def _mapa_de_permissoes(self, recarregar: bool = False) -> dict[str, int]:
        """Mapa ``view_menu -> id`` das permissões de acesso a dataset.

        A API não filtra permissão por nome de view_menu, então a lista é
        paginada inteira uma vez e guardada na instância — a DAG concede
        permissão a vários papéis na mesma execução.
        """
        if self._permissoes is not None and not recarregar:
            return self._permissoes

        mapa: dict[str, int] = {}
        pagina = 0
        while True:
            consulta = f"(page:{pagina},page_size:100)"
            resultado = self.requisitar(
                "GET", f"/api/v1/security/permissions-resources/?q={consulta}"
            )
            itens = resultado.get("result", [])
            for item in itens:
                permissao = (item.get("permission") or {}).get("name")
                view_menu = (item.get("view_menu") or {}).get("name")
                if permissao == PERMISSAO_DATASET and view_menu:
                    mapa[view_menu] = int(item["id"])
            if len(itens) < 100:
                break
            pagina += 1
        self._permissoes = mapa
        return mapa

    def permissao_do_dataset(
        self, database: str, tabela: str, id_dataset: int
    ) -> int | None:
        nome = VIEW_MENU_DATASET.format(
            database=database, tabela=tabela, id_dataset=id_dataset
        )
        return self._mapa_de_permissoes().get(nome)

    def permissoes_do_papel(self, id_papel: int) -> set[int]:
        resultado = self.requisitar(
            "GET", f"/api/v1/security/roles/{id_papel}/permissions/"
        )
        return {int(item["id"]) for item in resultado.get("result", [])}

    def conceder_permissoes(
        self, id_papel: int, ids_permissao: Iterable[int]
    ) -> set[int]:
        """Acrescenta permissões ao papel, preservando as que ele já tem.

        A API do Superset substitui a lista inteira, então a união é feita aqui:
        publicar uma dashboard nova não pode revogar o acesso que outra DAG (ou
        um administrador) já concedeu ao mesmo papel.
        """
        atuais = self.permissoes_do_papel(id_papel)
        final = atuais | set(ids_permissao)
        if final == atuais:
            return atuais
        self.requisitar(
            "POST",
            f"/api/v1/security/roles/{id_papel}/permissions",
            json={"permission_view_menu_ids": sorted(final)},
        )
        log.info(
            "[cliente_superset] Papel %s: %s permissão(ões) concedida(s).",
            id_papel,
            len(final - atuais),
        )
        return final

    # -------------------------------------------------------- recorte (RLS)

    def id_do_recorte(self, nome: str) -> int | None:
        resultado = self.requisitar(
            "GET", f"/api/v1/rowlevelsecurity/?q={self._filtro('name', nome)}"
        )
        for item in resultado.get("result", []):
            return int(item["id"])
        return None

    def garantir_recorte(
        self,
        nome: str,
        clausula: str,
        ids_dataset: list[int],
        ids_papel: list[int],
        descricao: str = "",
    ) -> int:
        """Cria ou atualiza um filtro de linhas. Idempotente por nome."""
        corpo = {
            "name": nome,
            "description": descricao,
            "filter_type": "Regular",
            "clause": clausula,
            "tables": sorted(ids_dataset),
            "roles": sorted(ids_papel),
            "group_key": "",
        }
        existente = self.id_do_recorte(nome)
        if existente is None:
            criado = self.requisitar("POST", "/api/v1/rowlevelsecurity/", json=corpo)
            id_recorte = criado.get("id")
            if id_recorte is None:
                raise ErroSuperset(
                    f"Criação do recorte '{nome}' não devolveu id: {criado}"
                )
            log.info("[cliente_superset] Recorte '%s' criado (id %s).", nome, id_recorte)
            return int(id_recorte)

        self.requisitar("PUT", f"/api/v1/rowlevelsecurity/{existente}", json=corpo)
        log.info("[cliente_superset] Recorte '%s' atualizado (id %s).", nome, existente)
        return existente
