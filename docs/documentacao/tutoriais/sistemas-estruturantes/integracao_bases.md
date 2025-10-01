# Guia de Integração de Nova Base – GovHub

# 1) Visão geral (como o projeto é organizado)

O GovHub é estruturado em módulos bem definidos dentro do repositório, cada um com uma responsabilidade clara. Isso facilita para qualquer pessoa nova entender **onde olhar** e **como começar** ao integrar uma nova base de dados.

#### **1.1. Orquestração – DAGs no Airflow**

* Local: `airflow_lappis/dags/**`
* Aqui ficam os **arquivos das DAGs**, que são os fluxos de execução no Airflow.
* Cada DAG define:

  * **Quando** rodar (agendamento com `schedule_interval`).
  * **Quais tarefas** executar (normalmente funções decoradas com `@task`).
  * **Dependência entre tarefas** (ordem de execução).
* Exemplo: uma DAG pode ter uma tarefa para buscar dados de uma API, outra para salvar no banco, e outra para disparar o processamento analítico.

---

#### **1.2. Clientes de APIs – Plugins**

* Local: `airflow_lappis/plugins/**`
* Cada sistema externo (PNCP, ComprasNet, SIAPE, etc.) tem seu próprio cliente, nomeado como `cliente_<sistema>.py`.
* A ideia é **encapsular toda a lógica de comunicação com o provedor** em uma classe separada, deixando a DAG mais limpa.
* Estrutura comum:

  * Herança de uma classe base (`cliente_base.py`) que já implementa comportamentos padrão: timeout, retries, logging básico.
  * Métodos específicos para endpoints da API (ex.: `get_contratacoes_publicacao` no cliente do PNCP).

---

#### **1.3. Helpers reutilizáveis**

* Local: `airflow_lappis/helpers/**`
* São **utilitários genéricos** que podem ser usados por qualquer cliente ou DAG.
* Exemplos:

  * `safe_request.py`: função para chamadas HTTP mais seguras (tratando erros, retornos vazios ou conteúdo não-JSON).
  * Funções de parsing, formatação de datas, manipulação de parâmetros.
* O objetivo é evitar duplicação de código: se você precisa de retry customizado ou de algo que já existe, basta importar o helper.

---

#### **1.4. Persistência – Banco de dados**

* Arquivos principais:

  * `cliente_postgres.py`: classe cliente para inserir dados no Postgres.
  * `postgres_helpers.py`: utilitários como a string de conexão (`get_postgres_conn`) e funções auxiliares para criar schema/tabelas.
* Normalmente, quando se integra uma nova base, você:

  * Usa o cliente da API para buscar os dados.
  * Usa o cliente do Postgres para criar um **novo schema** (um namespace no banco).
  * Insere os dados em uma **tabela correspondente** (com suporte a upsert, chaves primárias, etc.).

---

#### **1.5. Modelagem analítica (opcional)**

* Local: `airflow_lappis/dags/dbt/**`
* Após a ingestão bruta no Postgres, pode-se criar **modelos analíticos** usando dbt.
* Isso permite aplicar transformações em camadas (bronze, silver, gold) e preparar os dados para dashboards, relatórios e análises mais avançadas.
* É opcional: se a integração só precisa carregar dados brutos, não há necessidade de mexer no dbt.

---

#### **1.6. Logs – Monitoramento**

* O projeto usa `logging` em todas as classes e DAGs.
* Cada etapa da execução gera logs detalhados (tentativas de requisição, parâmetros usados, quantidade de registros coletados/inseridos).
* Isso garante rastreabilidade: você consegue saber exatamente onde falhou (na API, no banco, ou no parser) sem precisar adivinhar.

---

### Estrutura essencial (resumo do repositório)

```bash
airflow_lappis/
  ├── dags/
  │   ├── data_ingest/...       # Suas DAGs de ingestão
  │   └── dbt/                  # Modelagem analítica (dbt models)
  ├── helpers/
  │   ├── postgres_helpers.py   # Conexão e utilitários para Postgres
  │   └── safe_request.py       # Funções seguras para chamadas HTTP
  └── plugins/
      ├── cliente_base.py       # Classe base para APIs REST (httpx)
      ├── cliente_postgres.py   # Cliente para persistir dados no Postgres
      └── cliente_<nova_base>.py # Cliente que você cria ao integrar nova base
```


---


# 2) Checklist de integração (ordem recomendada)

### (a) Estudo inicial da API do provedor<br>

Antes de escrever qualquer código, é fundamental **entender bem a API** que será integrada. Isso envolve:

* **Base URL**: qual é a raiz dos endpoints (ex.: `https://contratos.comprasnet.gov.br/api`).
* **Autenticação**: é aberta ou precisa de token/certificado/usuário e senha?
* **Formato de resposta**: retorna sempre JSON? Pode devolver XML, CSV ou até HTML em caso de erro?
* **Paginação**: a API retorna todos os dados de uma vez ou exige navegar página por página (parâmetros como `pagina=1,2,...`)?
* **Headers obrigatórios**: geralmente `accept: application/json`, mas pode haver exigências de chave de API, user-agent, etc.
* **Limites de uso (rate limits)**: existe limite de chamadas por minuto/hora? Se sim, precisamos considerar `sleep` ou retentativas.

Essa etapa é essencial porque define a forma como vamos estruturar o cliente e o fluxo da DAG.
A dica prática é: **testar manualmente a API** com `curl`, Postman ou até `requests` em Python antes de começar a codar.

---

### (b) Criação do **cliente** da base (`plugins/cliente_<nova_base>.py`)<br>

O cliente é a camada que encapsula todas as chamadas à API. Ele **herda de `ClienteBase`** (classe comum que já configura `httpx`, timeout e retries) e define métodos específicos para cada endpoint.

##### Estrutura típica

1. **Definições principais**:

    * `BASE_URL`: raiz da API.
    * `BASE_HEADER`: headers padrão.

2. **Construtor (`__init__`)**:

    * Chama o `super().__init__` passando a `BASE_URL`.
    * Registra logs para indicar a inicialização do cliente.

3. **Métodos por endpoint**:

    * Nomeados com clareza, ex.: `get_contratos_by_ug`, `get_faturas_by_contrato_id`.
    * Fazem a chamada com `self.request` (já herdado do `ClienteBase`).
    * Validam o status da resposta.
    * Retornam a lista ou `None`.

---

##### Exemplo (trecho simplificado do `cliente_contratos`)

```python
class ClienteContratos(ClienteBase):
    BASE_URL = "https://contratos.comprasnet.gov.br/api"
    BASE_HEADER = {"accept": "application/json"}

    def __init__(self) -> None:
        super().__init__(base_url=ClienteContratos.BASE_URL)
        logging.info(f"[cliente_contratos.py] Initialized with base_url {self.BASE_URL}")

    def get_contratos_by_ug(self, ug_code: str) -> list | None:
        endpoint = f"/contrato/ug/{ug_code}"
        status, data = self.request(http.HTTPMethod.GET, endpoint, headers=self.BASE_HEADER)
        if status == http.HTTPStatus.OK and isinstance(data, list):
            return data
        return None
```

A ideia é que qualquer pessoa saiba olhar o cliente e entender:

* **como a API é chamada**,
* **como o retorno é tratado**,
* e **onde estão os pontos de log**.

---

### (c) Criação da **DAG** no Airflow (`dags/<nova_base>_dag.py`)<br>

A DAG orquestra a ingestão dos dados. Ela é responsável por:

1. **Agendamento**: definido no decorator `@dag` (ex.: `@daily`, `@weekly`).
2. **Variáveis de configuração**: lidas do Airflow (`Variable.get`) para parametrizar a execução.
3. **Tasks**: funções anotadas com `@task` que:

    * Instanciam o cliente da API.
    * Instanciam o cliente Postgres (`ClientPostgresDB`).
    * Buscam os dados via cliente da API.
    * Inserem os dados no banco, adicionando campos como `dt_ingest`.

##### Exemplo simplificado

```python
@dag(
    schedule_interval="@daily",
    start_date=datetime(2023, 1, 1),
    catchup=False,
    tags=["contratos_api"],
)
def api_contratos_dag():
    @task
    def fetch_and_store():
        api = ClienteContratos()
        db = ClientPostgresDB(get_postgres_conn())
        contratos = api.get_contratos_by_ug("113601")
        if contratos:
            for c in contratos:
                c["dt_ingest"] = datetime.now().isoformat()
            db.insert_data(contratos, "contratos", schema="compras_gov", conflict_fields=["id"], primary_key=["id"])
    fetch_and_store()
```

---

### (d) Modelagem analítica com **dbt**<br>

Depois de coletar e armazenar os dados no Postgres, usamos o **dbt** para organizar as camadas:

* **Bronze**: tabelas mais próximas da fonte, com padronização mínima (tipagem, normalização de campos nulos, etc.).
* **Silver**: tabelas transformadas e enriquecidas, com junções entre diferentes fontes (ex.: contratos + empenhos).
* **Gold**: dados prontos para consumo em dashboards e relatórios. Aqui já está no formato esperado pelo BI (Superset, Power BI, etc.).

A organização do dbt no projeto segue a lógica de pastas por **schema** (`models/<schema>`), e dentro delas as subpastas **bronze**, **silver** e **gold**.

---

### (e) Logging e variáveis do Airflow<br>

##### Logging

O **logging** é essencial para a rastreabilidade.
Quando rodamos uma DAG no Airflow, todos os logs das tasks ficam registrados na interface. Isso permite identificar:

* Parâmetros usados na execução.
* Quantidade de registros processados.
* Erros e exceções.

Por isso, é boa prática logar:

* Início e fim de cada chamada.
* Totais de registros.
* Avisos quando o retorno estiver vazio.

##### Variáveis do Airflow

É recomendável usar **variáveis do Airflow** para guardar:

* Códigos de órgãos.
* CNPJs.
* Tokens de acesso (quando não forem credenciais sensíveis).

Assim conseguimos alterar o comportamento da DAG **sem precisar mexer no código**, apenas ajustando variáveis no painel do Airflow.

---

# 3) Reaproveitando ao máximo

Ao integrar uma nova base no GovHub, **não é necessário reinventar a roda**. Já existem clientes e helpers que podem (e devem) ser reutilizados. Isso garante padronização, menos bugs e menos código duplicado.

---

## Clientes e helpers

* **`cliente_base.py`**
  Esse arquivo é a fundação para qualquer cliente de API. Ele já implementa:

    * Conexão com `httpx`.
    * Timeout padrão (10 segundos).
    * Retentativas automáticas (até 3, com backoff).

  **Quando usar?**
  Se a sua API **sempre retorna JSON válido** e segue um padrão consistente, você pode simplesmente herdar de `ClienteBase` e chamar o método `self.request`. Isso já resolve 90% dos casos.

* **`helpers/safe_request.py`**
  Esse helper foi criado para APIs menos previsíveis. Ele trata situações como:

    * A API responde com **204 (sem conteúdo)**.
    * O **Content-Type** não é `application/json` (às vezes vem HTML ou CSV).
    * O corpo da resposta está vazio ou contém JSON inválido.

  **Quando usar?**
  Se a API não é confiável e pode quebrar o fluxo ao tentar `json()`.
  Nesse caso, o `request_safe` não lança exceções: em vez disso, retorna um `str` ou `None`, permitindo que sua DAG continue rodando sem travar.

---

## Postgres

Outra parte que já está pronta para você reaproveitar é a persistência dos dados.

* **`cliente_postgres.py`** + **`postgres_helpers.py`**
  Juntos, eles facilitam toda a interação com o banco:

    * **Conexão**: use `get_postgres_conn()` para obter a string de conexão.
    * **Inserção**: use `insert_data()` para inserir registros em tabelas, com suporte a:

        * **Upsert** (evita duplicação de dados).
        * Definição de chave primária (`primary_key`).
        * Conflitos (`conflict_fields`).

---


## Criação de schemas e tabelas (dinâmica com o `ClientPostgresDB`)

Quando usamos o método `insert_data()` do `ClientPostgresDB`, não precisamos nos preocupar em criar tabelas manualmente antes.
Isso acontece porque a lógica da classe já inclui duas etapas internas:

--> **Garantir o schema**

   O método `create_table_if_not_exists` roda automaticamente:

```sql
CREATE SCHEMA IF NOT EXISTS <schema>;
```

   Ou seja, se você passar `schema="compras_gov"`, ele vai criar esse schema caso ele ainda não exista.

1. **Criar a tabela conforme os dados**

    * Ele pega o **primeiro item do dataset** (`data[0]`) como amostra.
    * Usa o método `_flatten_data()` para achatar estruturas aninhadas (listas, dicionários dentro do JSON).
    * Para cada chave encontrada, cria uma coluna do tipo **TEXT** (ou outro mapeado, se especificado).
    * Se você indicar `primary_key=["id"]`, ele adiciona a constraint `PRIMARY KEY (id)`.
    * Por fim, dispara um `CREATE TABLE IF NOT EXISTS` garantindo que a tabela exista.

2. **Inserção com upsert**

    * Ele gera um `INSERT INTO … VALUES …`.
    * Se você passar `conflict_fields=["id"]`, ele constrói automaticamente um:

     ```sql
     ON CONFLICT (id) DO UPDATE SET ...
     ```

     Isso evita duplicações: se já existir uma linha com o mesmo `id`, os dados serão atualizados.

➡️ Resumindo: só de chamar `insert_data()`, você já garante que o **schema existe**, que a **tabela está criada** e que os dados serão inseridos/atualizados corretamente.

Isso elimina a necessidade de criar tabelas manualmente na maioria dos casos.


---

# 4) Variáveis do Airflow (parametrização)

* `Variable.get("airflow_orgao")`: seleciona um “contexto” (ex.: `ipea`).
* `airflow_variables`: YAML com configurações por órgão:

  ```yaml
  ipea:
    codigos_ug: [113601, ...]
    orgao_pncp:
      cnpj: "33892175000100"
      modalidades: [6]
  ```
- Carregue com `yaml.safe_load` e depois faça `get`:

  ```python
  orgaos_config = yaml.safe_load(Variable.get("airflow_variables", "{}"))
  cfg = orgaos_config.get(orgao_alvo, {})
  cnpj = cfg.get("orgao_pncp", {}).get("cnpj")
  modalidades = cfg.get("orgao_pncp", {}).get("modalidades", [])
  ```

> Por que `yaml.safe_load` e não `dict(...)`? Porque a variável vem como **string YAML**. yaml.`safe_load` converte para **objetos Python** (dict/list/str/…).

---

# 5) Entregáveis mínimos no PR

1. **Cliente** em `plugins/cliente_<nova_base>.py`

    * Métodos bem nomeados, docstring curta, logs.
    * Uso de `request_safe` (se necessário).

2. **DAG** em `dags/<nova_base>_dag.py`

    * Leitura de variáveis do Airflow.
    * Inserção no Postgres com `cliente_postgres`.
    * Boa instrumentação de logs.

3. **Schema/Tabelas**

    * SQL/DBT para criar tabelas (ou anotação clara de dependência).

4. **Documentação curta** (README do provedor)

    * Base URL, autenticação, endpoints usados, exemplos cURL.
    * Campos-chave usados como `conflict_fields`.

---

# 6) Exemplo de “ciclo de vida” resumido (como no PNCP)

1. **Cliente PNCP** criado em `plugins/cliente_pncp.py`

    * `get_contratacoes_publicacao` (uma página)
    * `get_contratacoes_publicacao_paginado` (agregando)
    * `get_*_semestral` (quebra temporal + paginação)

2. **Helper** `helpers/safe_request.py` para lidar com `204`/conteúdo não-JSON.
3. **DAG** `dags/pncp_dag.py` usando:

    * `Variable.get` + `yaml.safe_load` para ler `cnpj` e `modalidades`.
    * Cliente PNCP para coletar dados.
    * `ClientPostgresDB.insert_data()` para persistir (com `dt_ingest`).


---

# 7) Dicas finais

* **Não** duplique lógica que já existe em helpers (retry, request seguro, inserção).
* Mantenha o **cliente** pequeno, legível e com logs úteis (params, status, contagens).
* Ao lidar com **credenciais**, use variáveis do Airflow, nunca hardcode.
* Se precisar encadear DAGs (ex.: “ingestão” → “dbt”), use:

    * `TriggerDagRunOperator`, ou
    * `ExternalTaskSensor`, ou
    * **Datasets** (recomendado para baixo acoplamento).


