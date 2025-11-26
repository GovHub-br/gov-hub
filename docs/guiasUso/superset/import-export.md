# Exportações de Dashboard no Superset

Existem **duas exportações diferentes**:

1. **Export (pacote .zip de metadados)** – usado para **migrar/reutilizar** o dashboard em outra instância do Superset (ou para versionar no repositório).
2. **Download (snapshot do dashboard)** – usado para **compartilhar como arquivo estático**, em **PDF** ou **Imagem (PNG)**, com os filtros aplicados.

Abaixo, o guia de cada uma.

---

## 1) Export (metadados) — pela lista de Dashboards

![Superset](../../../assets/images/export.png)

**Quando usar:**

* Migrar um dashboard entre ambientes (dev → prod).
* Fazer backup/versionamento do dashboard e dos charts associados.
* Entregar o pacote para alguém importar no Superset dele.

**O que sai no arquivo:**

* Um **.zip** contendo os **metadados** do dashboard e dos **charts** referenciados (JSON/YAML interno do Superset).
* **Não** inclui dados de tabelas, apenas **definições** (layout, filtros, métricas, queries, referências a datasets).
* **Não** exporta conexões de banco, permissões/roles, nem Row Level Security.

**Passo a passo:**

1. Acesse **Dashboards** no topo do Superset.
2. Encontre o dashboard desejado na listagem.
3. Na coluna **Actions**, clique no ícone de **seta para cima** (tooltip “Export”) — conforme a imagem da lista.
4. O browser fará o download de um arquivo do tipo **`dashboard_export_<data>.zip`**.
5. (Opcional) Para exportar **vários** de uma vez: clique em **BULK SELECT**, marque os desejados e use **Export**.


---

## 2) Download de snapshot — dentro do dashboard (PDF ou Imagem)

![Superset](../../../assets/images/export_pdf.png)

**Quando usar:**

* Compartilhar uma **versão estática** do dashboard em uma apresentação, e-mail, ou relatório.
* Gerar material com **filtros e período aplicados** naquele momento.

**Tipos:**

* **Export to PDF** → um PDF do dashboard, com o layout atual.
* **Download as Image** → um **PNG** com captura do dashboard renderizado.

**Passo a passo (PDF e PNG):**

1. **Abra o dashboard** (ex.: “Visão Geral – Faturas”).
2. **Aplique os filtros** que você quer refletidos na exportação (ex.: Nº do contrato, Ano de emissão, Situação etc.).
3. No canto superior direito, clique no botão de **reticências (⋯)**.
4. Passe o mouse em **Download** para abrir o submenu.
5. Escolha **Export to PDF** **ou** **Download as Image**.
6. Aguarde a geração. O arquivo baixa no seu navegador:

    * **PDF**: `dashboard_<nome>_<timestamp>.pdf`
    * **PNG**: `dashboard_<nome>_<timestamp>.png`

**Boas práticas para um snapshot mais limpo:**

* **Defina os filtros** antes do download (o snapshot respeita o estado atual).
* (Opcional) Clique em **Enter fullscreen** antes de exportar para reduzir elementos visuais e aproveitar mais o espaço.
* **Colapse a barra de filtros** se ela não for necessária no PDF/PNG final (para dar mais área aos gráficos).
* Se o dashboard for **muito longo**, considere **dividir em seções/abas** (Tabs) — o PDF/PNG fica mais legível e evita cortes.

**Observações úteis:**

* **PDF/Imagem ≠ Export (metadados)**: aqui você não leva o dashboard para outro Superset; você gera **arquivo estático** para leitura.
* O download reflete **exatamente o que está na tela** (temas, descrições, textos Markdown, KPIs, ordem dos charts, etc.).
* Se a opção **Export to PDF** não aparecer, pode ser **restrição de permissão** ou **configuração do servidor** (fale com o admin).

---

| Tipo                    | Onde fica                                               | Saída            | Conteúdo                                                   | Uso recomendado                             |
| ----------------------- | ------------------------------------------------------- | ---------------- | ---------------------------------------------------------- | ------------------------------------------- |
| **Export** (metadados)  | Lista de **Dashboards** → **Actions → Export**          | `.zip`           | JSON/YAML com **layout + charts** (sem dados)              | Migrar, versionar, backup                   |
| **Download** (snapshot) | Dentro do **dashboard** → **⋯ → Download → PDF/Imagem** | `.pdf` ou `.png` | **Imagem estática** do dashboard com **filtros aplicados** | Relatórios, apresentações, compartilhamento |

---

# Importação de Dashboards no Superset

![Superset](../../../assets/images/import.png)

## Passo a passo

### 1. Acessar a tela de Dashboards

* No menu superior do Superset, clique em **Dashboards**.
* Você será direcionado para a listagem de dashboards existentes.

### 2. Localizar a opção de importação

* No canto superior direito da tela, ao lado do botão **+ DASHBOARD**, clique no ícone de seta para baixo.
* Passe o mouse sobre o ícone e confirme que aparece a opção **Import dashboards**.

### 3. Iniciar o processo de importação

* Clique em **Import dashboards**.
* Uma janela será aberta para seleção do arquivo.

### 4. Selecionar o arquivo de exportação

* Escolha o arquivo `.zip` previamente exportado (por exemplo, `dashboard_export_data.zip`).
* Esse arquivo deve ter sido gerado a partir da função de exportação do Superset.

### 5. Confirmar a importação

* Clique em **Abrir** para carregar o arquivo no Superset.
* Aguarde o processamento.
* O sistema importará o layout do dashboard e os gráficos associados.

### 6. Verificar o dashboard importado

* Após a conclusão, o dashboard aparecerá automaticamente na lista de dashboards.
* Clique sobre o nome do dashboard para confirmar que todos os gráficos estão sendo exibidos corretamente.


