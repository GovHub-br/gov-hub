# ADR-0023: Sigla de camada no nome dos modelos dbt de Silver e Gold

- **Status**: Proposto
- **Data**: 2026-11-18
- **Autores**: -
- **Revisores**: -

## Introdução ao problema

O [ADR-0009](./0009-nomenclatura-pastas-arquivos-dbt.md) define que o arquivo
de um modelo dbt se chama `{entidade}.sql`, sem prefixo de camada, e que o nome
do arquivo coincide com o da tabela materializada. Isso funcionava enquanto
cada entidade existia numa camada só dentro do pacote. O
[ADR-0022](./0022-transformacao-parquet-com-duckdb-e-assets.md) mudou isso: a
Bronze em Parquet passou a ser um modelo dbt (`bronze/arp.sql`), e a Silver da
mesma entidade fica no mesmo pacote. Pelo ADR-0009, as duas se chamariam
`arp.sql`.

Dois limites de ferramenta tornam isso impossível:

- **O dbt recusa dois modelos com o mesmo nome no mesmo pacote.** A Bronze
  `arp` e a Silver `arp` do `compras_gov` não podem coexistir.
- **O Cosmos identifica o nó só pelo nome do modelo.** Entre pacotes
  diferentes o dbt aceita nomes repetidos, mas o Cosmos monta o id da task, o
  `group_id` do grupo do modelo e o `--select` dos testes apenas com o nome,
  sem o pacote (astronomer-cosmos 1.15.1, `cosmos/airflow/graph.py`). Com dois
  modelos `x` em pacotes que o mesmo projeto importa, a DAG cai com
  `DuplicateTaskIdFound` quando os dois têm testes (dois grupos `x`) e, pelo
  código do Cosmos, também quando nenhum tem (duas tasks `x_run`). Com teste em
  só um deles, a DAG carrega sem erro, com o grupo `x` e a task `x_run`, e o
  `--select x` dos testes casa os modelos dos dois pacotes. Quem impede isso no
  CI é a guarda `test_nome_de_modelo_unico_entre_pacotes`, não o Airflow.

A primeira Silver da ARP contornou o problema pondo camada e sistema no nome:
`silver_compras_gov_arp.sql`. Sem macro de alias, esse também era o nome da
tabela, o que contraria o
[ADR-0010](./0010-nomenclatura-schemas-tabelas-bronze-silver-gold.md): a
tabela deve ser `{entidade}`, sem prefixo de camada, porque a camada já está
no schema. É esse nome que o Superset, os bundles de dashboard e o catálogo
enxergam.

A decisão precisa ser tomada agora porque a ARP é o primeiro domínio com
Bronze e Silver da mesma entidade no mesmo pacote. Os próximos domínios em
Parquet repetem o par, e as cinco Silvers legadas do `compras_gov` vão precisar
de Bronze própria quando migrarem.

## Decisão

**No pacote `compras_gov`, o modelo de Silver se chama `slv_<entidade>` e o de
Gold `gld_<entidade>`. A tabela continua `<entidade>`, porque o
`generate_alias_name` do pacote tira a sigla. A Bronze não leva sigla.**

| Camada | Arquivo | Tabela | ARP |
|---|---|---|---|
| Bronze | `models/bronze/<entidade>.sql` | `001_bnz_compras_gov.<entidade>` | `bronze/arp.sql` → `001_bnz_compras_gov.arp` |
| Silver | `models/silver/<dominio>/slv_<entidade>.sql` | `002_slv_<dominio>.<entidade>` | `silver/arp/slv_arp.sql` → `002_slv_arp.arp` |
| Gold | `models/gold/<produto>/gld_<entidade>.sql` | `003_gld_<produto>.<entidade>` | — |

O `compras_gov` não tem Gold hoje; a regra vale para a primeira que for criada
nele.

### O macro tira a sigla da tabela

`airflow/dags/dbt/compras_gov/macros/generate_alias_name.sql` devolve o nome do
modelo sem `slv_` ou `gld_`. Modelo sem sigla (a Bronze e as Silvers legadas)
mantém o próprio nome. O macro vale para os modelos do pacote também quando o
projeto raiz é o de um órgão, como o `mgi` nas DAGs do Cosmos: o dbt usa o
`generate_*_name` de um pacote instalado nos modelos desse pacote, com
precedência sobre o da raiz (dbt-core 1.12, `dbt/parser/base.py`,
`RelationUpdate`). O projeto do órgão não precisa de cópia.

Um `alias` explícito na configuração ainda teria precedência sobre o macro,
como no padrão do dbt, mas foge da convenção e é proibido por teste.

### A Bronze não leva sigla

O nome do modelo da Bronze é a entidade da raw. É dele que o ADR-0022 tira o
caminho do Parquet (`gov_bricks.bronze_parquet` usa o nome do modelo) e o Asset
que agenda a DAG DuckDB (a DAG usa o nome do arquivo). Uma sigla na Bronze
quebraria essa convenção.

### O sistema não entra no nome

O sistema já é o pacote (`dbt/<sistema>/`), e a pasta da Silver é o domínio,
que também vira o schema. Repetir o sistema no nome do modelo só alongaria o
nome.

### Unicidade garantida por teste

`tests/unit/test_nomenclatura_modelos_dbt.py` aplica a regra:

- Silver e Gold do `compras_gov` levam a sigla da camada; as demais camadas
  não levam;
- a tabela é o nome do modelo sem a sigla;
- o pacote tem `generate_schema_name` e `generate_alias_name`;
- o nome de modelo é único em todo o monorepo, entre pacotes;
- a tabela física (schema e tabela) é única em todo o monorepo;
- nenhum modelo do pacote fixa `alias` à mão.

### Exceção temporária: as Silvers legadas

`contratos`, `contratos_item`, `fornecedor`, `orgao` e `uasg` continuam sem
sigla e estão em `LEGADO_SEM_PREFIXO`, no mesmo teste. A lista só pode
diminuir, e quem migra uma dessas Silvers precisa tirá-la de lá. Essas Silvers
leem a raw direto por `source()`, sem Bronze materializada.

### O gerador de modelos

`make modelo --camada silver` gera `slv_<entidade>.sql` quando o pacote tem o
`generate_alias_name`, e lê a Bronze por `ref()` quando
`models/bronze/<entidade>.sql` já existe. O gerador de Gold ainda não emite
`gld_`.

### Fora do escopo

A regra vale só para o `compras_gov`. A Gold dos projetos de órgão
(`dbt/<orgao>/`) fica fora: esses projetos não têm `generate_alias_name`, e lá
um `gld_x.sql` criaria a tabela `gld_x`.

### Relacionadas

Este ADR altera regras do ADR-0009 sem editá-lo:

- **ADR-0009, Decisão, terceiro item da lista**: "Nome do arquivo de modelo
  (`{entidade}.sql`) é o nome da entidade em `snake_case`, sem prefixo de
  camada". No `compras_gov`, passa a valer só para a Bronze e para as Silvers
  legadas. Silver e Gold levam `slv_` e `gld_`.
- **ADR-0009, Regras gerais de nomenclatura, terceiro item**: "Nome de arquivo
  de modelo dbt deve coincidir com o nome da tabela/view materializada por
  ele". Deixa de valer para Silver e Gold com sigla no `compras_gov`: a tabela
  é o nome do arquivo sem a sigla.
- **ADR-0009, árvore de pastas da Decisão**: os `{entidade}.sql` sob
  `silver/<dominio>/` e `gold/<produto_dados>/` de `dbt/<sistema>/` leem-se,
  no `compras_gov`, `slv_{entidade}.sql` e `gld_{entidade}.sql`.

Do ADR-0009 continuam valendo a organização de pastas por camada e por
domínio ou sistema e os caracteres permitidos. A ação decorrente que pedia
verificar a correspondência entre nome de arquivo e objeto materializado passa
a ser cumprida pelo teste "tabela = nome do modelo sem a sigla".

Este ADR **não altera nenhuma regra do ADR-0010**. A tabela `{entidade}` sem
prefixo de camada (Decisão, quarto item da lista) e os schemas `001_bnz_*`,
`002_slv_*` e `003_gld_*` continuam como estão. O macro existe justamente para
preservar a regra das tabelas.

Com o **ADR-0017**, a relação é de resposta. A seção "Bronze é `source`, não
modelo" tinha como primeira razão a colisão de nome entre
`bronze/<entidade>.sql` e `silver/<dominio>/<entidade>.sql` no mesmo pacote.
O ADR-0022 reverteu essa decisão para os domínios em Parquet, e a sigla deste
ADR é o que resolve a colisão.

Com o **ADR-0022**, a relação é de complemento: a Bronze sem sigla é exigência
da convenção de caminho e de Asset definida lá.

## Alternativas consideradas

### Alternativa A: sigla no arquivo e na tabela, sem macro

- Descrição: `slv_arp.sql` cria a tabela `002_slv_arp.slv_arp`.
- Prós: o arquivo continua igual à tabela, como pede o ADR-0009; nenhum macro
  para manter.
- Contras: contraria o ADR-0010, porque a sigla na tabela repete a camada que
  o schema já mostra. Muda o nome que o Superset e os bundles veem. É também o
  que acontece, sem aviso, num pacote que adota a sigla sem o macro.

### Alternativa B: sigla também na Bronze (`bnz_arp`)

- Descrição: todas as camadas levam sigla no nome do modelo.
- Prós: simetria entre as três camadas.
- Contras: o macro `bronze_parquet` usa o nome do modelo como entidade, e a DAG
  DuckDB usa o nome do arquivo para montar o Asset. Seria preciso tirar a sigla
  no macro, na DAG, nos testes e no `generate_alias_name`. E não resolve
  colisão entre pacotes: dois sistemas com a mesma entidade teriam o mesmo
  `bnz_<entidade>`.

### Alternativa C: sistema no nome da Silver

- Descrição: `silver_compras_gov_arp.sql` ou `slv_compras_gov_arp.sql`. Foi a
  forma da primeira Silver da ARP.
- Prós: unicidade entre pacotes sem depender de teste.
- Contras: repete o pacote no nome; alonga o nome diante do limite de 63 bytes
  do PostgreSQL para identificadores. Para manter a tabela `{entidade}`, o
  macro teria de tirar a sigla e o sistema. Diverge da Bronze e das Silvers
  legadas, que não levam sistema.

### Alternativa D: `alias` manual em cada modelo

- Descrição: `config(alias="arp")` em `slv_arp.sql`.
- Prós: nenhum macro; o mecanismo é o padrão do dbt.
- Contras: a convenção fica espalhada pelos arquivos, e um alias esquecido ou
  errado só aparece no banco. O teste de nomenclatura proíbe `alias` manual.

### Não fazer nada / manter status quo

Manter `{entidade}.sql` em todas as camadas faz a Bronze `arp` e a Silver
`arp` colidirem no mesmo pacote, e o dbt recusa o projeto. Não é aceitável a
partir do momento em que a Bronze vira modelo.

## Tradeoffs

### Vantagens

- **[Alto impacto]** Bronze e Silver da mesma entidade coexistem no pacote, e o
  Cosmos monta as DAGs sem `DuplicateTaskIdFound`.
- **[Médio impacto]** As tabelas seguem o ADR-0010, e, nas Silvers novas, os
  consumidores (Superset, bundles, catálogo) não mudam. A exceção é a Silver da
  ARP, cuja tabela muda de nome (ver Consequências).
- **[Médio impacto]** A regra é garantida por teste, e não por revisão.
- **[Baixo impacto]** A sigla mostra a camada no id da task do Airflow e no
  grafo do dbt.

### Desvantagens

- **[Médio impacto]** O nome do arquivo deixa de ser igual ao da tabela. Para
  ir da tabela ao modelo, é preciso acrescentar a sigla.
- **[Médio impacto]** A regra depende de um macro no pacote. Um pacote que
  adote a sigla sem o macro cria `slv_x` sem erro, e o teste de sigla só cobre
  o `compras_gov`.
- **[Médio impacto]** Cinco Silvers legadas convivem com a regra. Enquanto
  existirem, uma Bronze nova com o nome de uma delas colide com ela; o teste
  de unicidade acusa a colisão.
- **[Baixo impacto]** A sigla não resolve Bronzes homônimas em pacotes
  diferentes. Isso fica só a cargo do teste de unicidade.
- **[Baixo impacto]** O gerador de Gold ainda não acompanha a regra.

### Avaliação

Os ganhos superam os custos. Sem a sigla, a Bronze modelada pelo ADR-0022 não
cabe no mesmo pacote que a Silver da mesma entidade. Entre as alternativas que
resolvem a colisão, o macro de alias é a que menos se afasta do ADR-0009 e não
toca no ADR-0010: o desvio fica restrito ao nome do arquivo, e o nome que os
consumidores veem não muda nas Silvers novas. A exceção é a Silver da ARP,
anterior a este ADR, cuja tabela passa a `002_slv_arp.arp` (ver Consequências).

Permanecem como riscos ativos:

- a dependência de um macro por pacote, que só o `compras_gov` tem;
- as Silvers legadas, até a migração;
- o gerador de Gold, que ainda não segue a regra.

## Consequências

- **Positivas**: nomes de modelo únicos no monorepo, tabelas com nome estável
  para os consumidores nas Silvers novas e uma regra verificada a cada execução
  dos testes.
- **Negativas**: o nome do arquivo deixa de coincidir com o da tabela, e a
  dívida das cinco Silvers legadas fica registrada numa lista de exceções. A
  Silver da ARP, criada antes deste ADR como `silver_compras_gov_arp.sql`, vira
  `slv_arp.sql`, e a tabela dela passa de `002_slv_arp.silver_compras_gov_arp`
  para `002_slv_arp.arp`. O dbt não apaga a tabela antiga, que fica órfã no
  banco, e quem a consome precisa passar a ler `002_slv_arp.arp`.
- **Ações decorrentes**:
  - Migrar as cinco Silvers legadas para `slv_<entidade>`, com Bronze própria,
    até esvaziar `LEGADO_SEM_PREFIXO`.
  - Corrigir o gerador de Gold: ele escreve `ref("<sistema>", "<entidade>")`.
    Para uma Silver com sigla, esse `ref` aponta para a Bronze homônima (por
    exemplo, `compras_gov.arp`) ou falha quando ela não existe. Precisa apontar
    para `slv_<entidade>`.
  - Decidir se o `sources.yml` da Bronze materializada continua sendo gerado.
  - Avaliar marcar o ADR-0009 como parcialmente substituído por este ADR.

## Referências

- [ADR-0009 — Padrão de nomenclatura das pastas/arquivos de projetos dbt](./0009-nomenclatura-pastas-arquivos-dbt.md)
- [ADR-0010 — Padrão de nomenclatura de schemas e tabelas bronze/silver/gold](./0010-nomenclatura-schemas-tabelas-bronze-silver-gold.md)
- [ADR-0017 — Chaves conformadas e catálogo de cruzamento entre sistemas estruturantes](./0017-chaves-conformadas-cruzamento-sistemas-estruturantes.md)
- [ADR-0018 — Padrão de nomenclatura e execução das DAGs de transformação](./0018-nomenclatura-execucao-dags-transformacao.md)
- [ADR-0022 — Transformação da raw em Parquet com DuckDB e agendamento por Assets](./0022-transformacao-parquet-com-duckdb-e-assets.md)
- [dbt — custom aliases (`generate_alias_name`)](https://docs.getdbt.com/docs/build/custom-aliases)
- [Astronomer Cosmos — documentação](https://astronomer.github.io/astronomer-cosmos/)
