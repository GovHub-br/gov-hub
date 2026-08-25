# ADR-0020: Níveis de acesso derivados da classificação de sensibilidade

- **Status**: Proposto
- **Data**: 2026-08-24
- **Autores**: -
- **Revisores**: -

## Introdução ao problema

O [ADR-0013](./0013-padrao-documentacao-metadados-tabelas.md) fez com que toda
coluna carregue uma classificação de sensibilidade — `publico`, `interno`,
`pessoal`, `pessoal_sensivel` — declarada no `schema.yml` do modelo que a
produz. Ele registrou também por que isso importa: sem marcação explícita, *"a
decisão sobre o que pode ser exposto em um dashboard (…) fica a critério de
quem estiver construindo cada consumo"*.

O [ADR-0019](./0019-publicacao-dashboards-relatorios.md) trouxe o consumo para
dentro do repositório, mas deixou em aberto justamente essa ponta: a
classificação existe, o consumo existe, e nada liga um ao outro. Hoje, quem
concede acesso no Superset concede clicando, e o critério é o entendimento de
quem clicou.

O problema fica agudo porque o produto de dados é **federado**: uma tabela como
`contratos_por_orgao` cobre todos os órgãos ao mesmo tempo. Dar a um instituto
acesso a essa dashboard, sem mais nada, é dar a ele a execução de todos os
demais. Não é um risco hipotético — é o comportamento padrão de qualquer
ferramenta de BI diante de uma tabela federada.

São, portanto, duas perguntas distintas que precisam de resposta declarada:

- **quais colunas** uma pessoa pode ver, que é uma pergunta sobre
  sensibilidade; e
- **quais linhas** ela pode ver, que é uma pergunta sobre competência
  institucional.

Responder as duas na interface, um usuário por vez, tem os problemas
conhecidos de qualquer controle manual: não é revisável, não é reproduzível
entre ambientes, não é auditável depois do fato e degrada com rotatividade de
equipe — risco já registrado nos ADRs
[0001](./0001-airflow-como-orquestrador-de-fluxos-de-dados.md) e
[0002](./0002-dbt-como-ferramenta-de-transformacao-de-dados.md).

## Decisão

**Nível de acesso é derivado da classificação do dado, e concedido por órgão
consumidor. Nenhum papel é criado à mão na ferramenta de BI.**

### O vocabulário de níveis

`catalogo/acesso.yml` declara os níveis e, para cada um, exatamente quais
classificações do ADR-0013 ele enxerga:

| Nível | Vê |
|---|---|
| `publico` | `publico` |
| `interno` | `publico`, `interno` |
| `pessoal` | `publico`, `interno`, `pessoal` |
| `pessoal_sensivel` | tudo |

O nível não é uma etiqueta de confiança genérica: ele é *a lista de
classificações que a pessoa pode ver*. É o que permite decidir, sem julgamento
caso a caso, se uma coluna pode aparecer em um consumo.

### Papéis por órgão consumidor

Cada consumidor declarado em `catalogo/publicacao/<orgao>.yml` vira um papel
`{prefixo}_{orgao_consumidor}_{nivel}` no Superset, herdando do papel nativo de
consulta e recebendo permissão apenas sobre os datasets das dashboards que lhe
foram atribuídas. O papel é criado e atualizado pela DAG de publicação, a partir
de um plano gerado (`make publicacao-sync`) e versionado ao lado dos bundles.

A concessão de permissões é **aditiva**: a DAG faz a união com o que o papel já
tem, em vez de substituir a lista. Publicar uma dashboard nova não pode revogar
um acesso concedido por outro processo.

### Recorte de linhas por órgão

Todo consumidor declara sua `abrangencia`:

- `proprio` — recebe um filtro de linhas (Row Level Security) sobre a chave
  conformada `co_orgao` (ADR-0017), com o código do seu órgão. Ele vê a
  dashboard federada, mas só as suas linhas.
- `total` — dispensa o filtro. Só se justifica para órgão com competência
  declarada sobre a base inteira, e a validação emite aviso a cada uso, para
  que a exceção seja sempre uma escolha visível e não um esquecimento.

O mesmo recorte vale para o relatório periódico do ADR-0019: a entrega de cada
órgão é gerada com a mesma cláusula que ele teria na dashboard. Um relatório
não pode ser a porta dos fundos do controle de acesso.

### Verificação no CI

O `make publicacao-validar` cruza as duas fontes e reprova o build quando:

- uma coluna exposta em um dataset publicado é classificada acima do nível
  declarado do dataset;
- uma coluna exposta **não está documentada** no `schema.yml` do modelo — sem
  classificação declarada ela vale como `pessoal` (ADR-0013), então ou o nível
  do dataset a comporta, ou é erro;
- um consumidor recebe dashboard ou relatório de nível acima do dele;
- um dataset pede recorte por `co_orgao` mas não expõe essa coluna — caso em
  que o filtro não teria onde se aplicar e o recorte seria uma ilusão;
- o código de órgão de um consumidor não é numérico (aviso quando ainda não foi
  verificado contra a tabela de órgãos ingerida).

## Alternativas consideradas

### Alternativa A: acesso concedido manualmente no Superset

- Descrição: administradores criam papéis e concedem datasets pela interface,
  seguindo a documentação.
- Prós: nenhum código; flexibilidade total para casos que fogem do padrão.
- Contras: não é revisável nem reproduzível — o estado de produção não existe em
  lugar nenhum além da própria produção. Auditar "quem via o quê em março" fica
  impossível, e reconstruir o ambiente significa reconstituir dezenas de
  concessões de memória.

### Alternativa B: um papel por dashboard

- Descrição: cada dashboard tem seu papel, e as pessoas acumulam papéis.
- Prós: granularidade máxima; conceder é trivialmente "adicionar o papel".
- Contras: o critério volta a ser dashboard a dashboard, sem relação com a
  sensibilidade do dado — duas dashboards sobre a mesma coluna `pessoal` podem
  acabar com regras diferentes. E o número de papéis cresce com o número de
  dashboards, não com o número de decisões reais de acesso.

### Alternativa C: segurança no warehouse, com uma view por órgão

- Descrição: criar no banco uma view por órgão consumidor e conceder acesso a
  ela; a ferramenta de BI não sabe de nada.
- Prós: o controle fica no ponto mais baixo da pilha, valendo também para quem
  acessa o banco direto — que é uma vantagem real.
- Contras: multiplica objetos no warehouse por órgão × produto de dados, e cada
  coluna nova precisa ser propagada a todas as views. Além disso, empurra para
  o dbt uma decisão de consumo, quebrando a separação de camadas do
  [ADR-0006](./0006-arquitetura-medallion.md). Continua sendo o caminho certo
  para acesso direto ao banco, mas não substitui o controle na ferramenta de BI.

### Não fazer nada / manter status quo

Publicar dashboards versionadas (ADR-0019) sem decidir níveis de acesso
significaria automatizar a exposição e deixar o controle manual — o pior dos
dois mundos, porque a facilidade de publicar cresce e a de verificar não.

## Tradeoffs

### Vantagens

- **[Alto impacto]** A pergunta "quem pode ver esta coluna?" passa a ter uma
  resposta derivada da classificação declarada no modelo, e não do julgamento de
  quem montou a dashboard.
- **[Alto impacto]** Um instituto que recebe uma dashboard federada vê apenas as
  suas linhas por construção — o recorte é padrão, e a exceção é que precisa ser
  declarada.
- **[Alto impacto]** Exposição indevida vira erro de build: a comparação entre
  coluna publicada e classificação roda no CI, antes do merge.
- **[Médio impacto]** O estado de acesso é reproduzível: reconstruir o ambiente
  é reexecutar a DAG de publicação.
- **[Médio impacto]** A matriz de acesso (`make acesso`) responde, sem abrir a
  ferramenta, quem enxerga o quê e com que recorte.

### Desvantagens

- **[Alto impacto]** A garantia depende inteiramente da qualidade da
  classificação no `schema.yml`. Coluna classificada errado gera acesso errado
  com a mesma eficiência com que geraria acesso certo — o CI verifica coerência,
  não verdade.
- **[Médio impacto]** Row Level Security do Superset protege o que passa pela
  ferramenta; quem tiver acesso direto ao banco não é afetado. O controle no
  warehouse continua sendo necessário e não está resolvido aqui.
- **[Médio impacto]** Conceder acesso deixa de ser um clique e passa a ser um
  PR no catálogo, com a latência de revisão que isso implica.
- **[Baixo impacto]** Papéis criados fora do catálogo continuam existindo e não
  são revogados pela DAG — a concessão aditiva, que protege contra revogação
  acidental, também impede a limpeza automática.

### Avaliação

Os ganhos superam os custos. A desvantagem de fundo — depender da classificação
declarada — não é um custo desta decisão, e sim a razão de ela existir: o
ADR-0013 já tinha decidido que a classificação é a fonte de verdade, e o que
faltava era alguém consumi-la. Transformar acesso em PR é mais lento que
clicar, e é exatamente esse o objetivo em um framework que trata dado pessoal
de órgãos distintos.

Permanecem como risco ativo: o acesso direto ao banco, fora do alcance do
recorte, e os papéis legados criados na interface, que só uma revisão manual
identifica.

## Consequências

- **Positivas**: níveis de acesso passam a ser derivados, versionados e
  verificados; institutos podem compartilhar um produto de dados federado sem
  compartilhar linhas; auditar acesso passa a ser ler o repositório.
- **Negativas**: acesso passa a depender do ciclo de revisão de PR, e a garantia
  fica limitada ao que a ferramenta de BI intermedia.
- **Ações decorrentes**:
  - Verificar os códigos de órgão dos consumidores contra a tabela de órgãos
    ingerida e marcá-los como verificados no catálogo.
  - Levar o mesmo recorte para o acesso direto ao warehouse (papéis e views no
    banco), que segue sem cobertura.
  - Revisar, no primeiro deployment, os papéis pré-existentes no Superset que
    não vieram do catálogo.
  - Habilitar `FAB_ADD_SECURITY_API` na configuração do Superset de cada
    ambiente: a API de papéis e permissões não é registrada por padrão, e sem
    ela a DAG de publicação não consegue criar papel nem conceder dataset.
  - Definir o processo pelo qual um órgão solicita elevação de nível — o
    catálogo registra a decisão, mas não o pedido nem a base legal que a
    sustenta.

## Referências

- [Superset — Row Level Security](https://superset.apache.org/docs/using-superset/creating-your-first-dashboard/#row-level-security)
- [Lei nº 13.709/2018 (LGPD), art. 5º, II](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
- [ADR-0006 — Arquitetura medallion (bronze/silver/gold)](./0006-arquitetura-medallion.md)
- [ADR-0013 — Padrão de documentação de metadados de tabelas](./0013-padrao-documentacao-metadados-tabelas.md)
- [ADR-0017 — Chaves conformadas e catálogo de cruzamento entre sistemas estruturantes](./0017-chaves-conformadas-cruzamento-sistemas-estruturantes.md)
- [ADR-0019 — Publicação de produtos de dados](./0019-publicacao-dashboards-relatorios.md)
