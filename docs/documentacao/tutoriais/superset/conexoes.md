# Conexão do Superset com Banco de Dados Local

## 1. Acessar a seção de conexões de banco

![Superset](../../../assets/images/db_connection.png)

1. No menu superior direito, clique em **Settings**.
2. No menu suspenso, em **Data**, selecione **Database Connections**.
3. Você será direcionado para a página de **Databases**, onde estão listadas as conexões já existentes.

---

## 2. Criar uma nova conexão

1. Na página de **Databases**, clique no botão azul **+ DATABASE**.
2. Será aberta a tela **Connect a database**.
3. Escolha o tipo de banco que deseja conectar. Exemplos:

    * PostgreSQL
    * MySQL
    * Presto
    * SQLite

No caso de exemplo, foi selecionado **PostgreSQL**.

---

## 3. Inserir credenciais do banco

![Superset](../../../assets/images/db_credentials.png)


Na etapa de configuração do PostgreSQL, preencha os campos obrigatórios:

* **Host**: endereço do servidor do banco. Para conexão local, utilize `127.0.0.1`.
* **Port**: porta de conexão do banco. O padrão do PostgreSQL é `5432`.
* **Database Name**: nome do banco que será acessado (exemplo: `analytics`, `meu_banco`).
* **Username**: usuário do banco de dados.
* **Password**: senha do usuário informado.
* **Display Name**: nome amigável que será exibido dentro do Superset (exemplo: `PostgreSQL Local`).

Campos adicionais:

* **Additional Parameters**: usado apenas em casos especiais para configurar parâmetros extras de conexão.
* **SSL**: habilite apenas se o banco exigir conexão segura por SSL.

---

## 4. Conectar

1. Após preencher os dados, clique em **CONNECT**.
2. O Superset testará a conexão com o banco.
3. Se os dados estiverem corretos, a conexão será criada e o banco aparecerá na lista de **Databases**.

---

## 5. Verificar datasets disponíveis

1. Após a conexão, vá até a aba **Datasets** no menu superior.
2. Verifique se os esquemas e tabelas do banco conectado estão disponíveis.
3. Agora é possível criar visualizações e dashboards utilizando esses dados.

---

## Observações importantes

* O usuário e senha informados devem ter permissão de leitura no banco para que o Superset consiga consultar os dados.
* Em ambientes locais, certifique-se de que o banco está rodando e acessível na porta configurada.
* Se o banco estiver em container (Docker), verifique se a porta foi exposta corretamente (`-p 5432:5432` para PostgreSQL, por exemplo).

