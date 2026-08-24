# ADR-0017: Chaves conformadas e catálogo de cruzamento entre sistemas estruturantes

- **Status**: Proposto
- **Data**: 2026-08-24
- **Autores**: -
- **Revisores**: -

## Introdução ao problema

Os ADRs anteriores definem onde um dado vive ([ADR-0006](./0006-arquitetura-medallion.md)),
como o modelo dbt que o produz é organizado
([ADR-0009](./0009-nomenclatura-pastas-arquivos-dbt.md)), como o schema e a
tabela se chamam ([ADR-0010](./0010-nomenclatura-schemas-tabelas-bronze-silver-gold.md))
e o que precisa estar escrito sobre ele
([ADR-0013](./0013-padrao-documentacao-metadados-tabelas.md)). Nenhum deles
define **como dois sistemas estruturantes se ligam** — que é a razão de existir
da camada Gold, onde o ADR-0006 prevê "joins multi-domínio".

O valor de uma plataforma de dados públicos não está em ter compras, orçamento e
pessoal ingeridos lado a lado; está em conseguir responder perguntas que
atravessam os três. E esse cruzamento hoje não tem nenhum apoio no framework:

- **A chave de junção é redescoberta a cada modelo.** Que o código de órgão liga
  compras a orçamento é conhecimento que existe na cabeça de quem já fez o join
  uma vez. O próximo modelo o redescobre — e frequentemente o redescobre errado.
- **O cruzamento falha por formato, não por semântica.** O mesmo código de UASG
  chega como inteiro em um sistema, como texto com zeros à esquerda em outro e
  com máscara em um terceiro. Um `join` direto entre colunas cruas produz
  silenciosamente zero linhas — ou, pior, poucas linhas, o que parece plausível.
- **Equivalências aproximadas viram fatos.** UASG e unidade gestora do SIAFI
  coincidem na maioria dos casos, não em todos. Sem um lugar para registrar
  *quanto* uma ponte vale, a ressalva se perde no primeiro modelo que a usa, e a
  aproximação passa a ser tratada como identidade.
- **Não há inventário do que é cruzável.** Para saber se duas entidades se ligam,
  hoje é preciso abrir a ingestão de ambas e comparar colunas na mão.
- **O custo de modelar é pago inteiro, toda vez.** Criar um modelo Silver que
  respeite ADR-0009, ADR-0010 e ADR-0013 é meia hora de trabalho mecânico —
  pasta certa, normalização de chave, deduplicação, `schema.yml` com quatro
  campos obrigatórios por coluna. Trabalho mecânico feito à mão é trabalho feito
  de forma inconsistente.

A decisão precisa ser tomada agora porque a pasta `dbt/` do monorepo está vazia:
todo o acervo de modelos ainda será escrito. Estabelecer o mecanismo antes do
primeiro modelo custa um catálogo; estabelecê-lo depois custa uma migração.

## Decisão

O cruzamento entre sistemas estruturantes é declarado em um **catálogo
versionado** (`catalogo/`), e não escrito à mão em cada modelo. O catálogo é a
fonte de verdade a partir da qual modelos, metadados e macros são gerados.

### Chave conformada

Uma **chave conformada** é um identificador que significa a mesma coisa em mais
de um sistema estruturante — `co_orgao`, `co_uasg`, `nu_cnpj`,
`nu_matricula_siape`. Cada uma é declarada uma única vez em
`catalogo/chaves.yml` com sua normalização (`digitos` ou `texto`, com `tamanho`
opcional para completar com zeros à esquerda), seu sistema de referência e sua
classificação de sensibilidade no vocabulário do ADR-0013.

Cada sistema declara, em `catalogo/sistemas/<sistema>.yml`, quais colunas suas
expõem cada chave. Um mapeamento carrega `verificado: true|false`: `false`
significa hipótese ainda não confirmada contra o dado ingerido.

**Nenhum modelo cruza sistemas por coluna crua.** O cruzamento é sempre sobre a
chave conformada, normalizada pelo macro `chave_conformada()`, que lê a
definição do catálogo. É isso que impede a classe de erro em que o join falha
por formato e o resultado vazio passa por resultado legítimo.

### Ponte

Uma **ponte** declara uma equivalência ou derivação entre duas chaves distintas
— `co_uasg → co_ug_siafi`, ou `nu_ni → nu_cnpj` quando o NI tem 14 dígitos —
com uma `confiabilidade` explícita:

| Confiabilidade | Significado |
|---|---|
| `total` | Vale sempre; pode ser aplicada direto em Silver. |
| `parcial` | Vale na maioria dos casos; exige tratar a exceção e documentá-la no modelo. |
| `indicio` | Hipótese não verificada contra os dados; não use em Gold. |

A ponte é o lugar onde uma aproximação fica registrada **como** aproximação. Um
modelo gerado a partir de uma ponte não-total carrega, no próprio SQL, o aviso
de que sua cobertura não é total.

### Bronze é `source`, não modelo

O ADR-0009 previu `models/bronze/{entidade}.sql`. Esta decisão **substitui esse
ponto**: a Bronze é declarada como `source` dbt
(`models/bronze/sources.yml`, gerado a partir do catálogo), não como modelo.
Três razões:

1. **Colisão de nome.** ADR-0009 exige nome de arquivo igual ao nome da entidade,
   sem prefixo de camada; ADR-0010 exige nome de tabela sem prefixo de camada.
   Juntas, as duas regras produzem `bronze/contratos.sql` e
   `silver/<dominio>/contratos.sql` no mesmo pacote — e dbt exige nome de modelo
   único dentro de um pacote. A convenção, como escrita, não é implementável.
2. **Redundância.** A Bronze já é materializada pelas DAGs de ingestão
   (ADR-0006: fiel à fonte, imutável). Um modelo dbt que apenas a copia cria uma
   segunda cópia do dado bruto sem acrescentar nada.
3. **Direção já sinalizada.** O [ADR-0016](./0016-tipagem-parquet-staging-bronze.md)
   avalia manter a Bronze fora do warehouse. Tratá-la como `source` deixa essa
   migração como troca da definição do source, sem tocar em nenhum modelo.

As demais regras do ADR-0009 (pastas por camada e domínio, nome de arquivo igual
ao da entidade) permanecem inalteradas.

### Geração a partir do catálogo

`make modelo` gera, a partir do catálogo:

- o `sources.yml` da Bronze, com `identifier` apontando para a tabela que a DAG
  de ingestão grava hoje;
- o modelo Silver, na pasta do ADR-0009, com as chaves conformadas normalizadas
  e a deduplicação por chave primária já escritas;
- o modelo Gold, com o plano de join resolvido pelo catálogo — incluindo
  ligações transitivas e por ponte. Entidade que não se liga a nenhuma anterior
  **interrompe a geração com erro**, em vez de produzir um produto cartesiano
  silencioso;
- a entrada de `schema.yml` com os campos obrigatórios do ADR-0013, incluindo a
  classificação do modelo derivada da coluna mais restritiva.

O gerado é ponto de partida, não produto final: nenhum arquivo é sobrescrito sem
`--forcar`, e o que o gerador não pode saber vem marcado como `PREENCHER`.

`make mapa` responde, do catálogo, o que se liga a quê e por qual chave —
marcando o que é verificado, o que é hipótese e o que depende de ponte.

Dois artefatos são **derivados** e não se editam à mão: `sources.yml` e o macro
`chaves_geradas.sql` (regerado por `make catalogo-sync`). `make lint` reprova
quando o macro diverge do catálogo, no mesmo espírito do `requirements.txt`.

### Enforcement

`make catalogo-validar`, incluído em `make lint` e portanto no CI, reprova o
build em caso de inconsistência: chave inexistente, entidade sem descrição ou
granularidade, classificação fora do vocabulário do ADR-0013, sistema fora da
nomenclatura do ADR-0010, ponte para chave inexistente. Mapeamento não
verificado gera **aviso**, não erro: registrar uma hipótese explicitamente é
melhor que deixá-la implícita no SQL de alguém.

## Alternativas consideradas

### Alternativa A: Convenção documentada, sem catálogo executável

- Descrição: documentar em prosa quais são as chaves de cruzamento e como
  normalizá-las, deixando a aplicação a cargo de quem escreve cada modelo.
- Prós: nenhum código novo para manter; nenhuma ferramenta a aprender.
- Contras: é a Alternativa C do ADR-0013 aplicada a outro problema — um
  requisito que depende só de disciplina é, na prática, opcional. Pior aqui: a
  divergência de normalização não aparece como erro, aparece como resultado
  vazio ou incompleto, que é indistinguível de um dado legitimamente ausente.

### Alternativa B: Macro de normalização sem catálogo

- Descrição: criar apenas os macros (`normaliza_cnpj`, `normaliza_uasg`) e
  deixar cada modelo escolher qual aplicar, sem declarar chaves nem mapeamentos.
- Prós: resolve o problema de formato com muito menos maquinário; nenhum YAML a
  manter.
- Contras: resolve o sintoma mais barato e deixa os outros quatro. Continua sem
  inventário do que é cruzável, sem registro de confiabilidade das
  equivalências e sem geração de modelo — e a escolha do macro certo volta a ser
  conhecimento tácito de quem escreve o join.

### Alternativa C: Dimensões conformadas materializadas em `000_ref_*`

- Descrição: em vez de declarar chaves, materializar tabelas de referência
  (órgãos, UASGs, naturezas de despesa) no schema `000_ref_*` previsto pelo
  ADR-0010, e obrigar todo cruzamento a passar por elas.
- Prós: modelagem dimensional clássica, familiar a quem vem de data warehouse;
  entrega junto o dado de referência, não só a chave.
- Contras: exige uma fonte autoritativa para cada dimensão — que, para vários
  sistemas estruturantes, o framework ainda não ingere. Adotá-la agora
  significaria fabricar tabelas de referência a partir do sistema que por acaso
  foi ingerido primeiro, promovendo um recorte parcial a verdade institucional.
  Não é excludente com esta decisão: quando a fonte autoritativa existir, a
  dimensão em `000_ref_*` passa a ser mais uma entidade catalogada.

### Não fazer nada / manter status quo

- Descrição: cada projeto consumidor resolve o cruzamento no SQL de cada modelo
  Gold.
- Consequência: o conhecimento sobre como os sistemas se ligam permanece
  distribuído entre pessoas, com perda garantida a cada troca de equipe — o
  mesmo risco de rotatividade já registrado nos ADRs 0001, 0002 e 0013 — e as
  equivalências aproximadas continuam sendo tratadas como identidades.

## Tradeoffs

### Vantagens

- **[Alto impacto]** Elimina a classe de erro mais perigosa do cruzamento entre
  sistemas estruturantes: o join que falha por diferença de formato e devolve um
  resultado plausível, porém errado.
- **[Alto impacto]** O conhecimento sobre como os sistemas se ligam passa a ser
  um artefato versionado e revisável em PR, em vez de conhecimento tácito.
- **[Alto impacto]** A distinção entre equivalência exata e aproximação fica
  registrada com granularidade (`total`/`parcial`/`indicio`) e chega ao SQL
  gerado como aviso, em vez de se perder na primeira reutilização.
- **[Médio impacto]** O custo de criar um modelo em conformidade com ADR-0009,
  0010 e 0013 cai de trabalho manual repetitivo para um comando — o que torna a
  conformidade o caminho mais fácil, e não o mais caro.
- **[Médio impacto]** `make mapa` dá um inventário de cruzabilidade que hoje não
  existe em lugar nenhum, útil inclusive para priorizar roadmap de ingestão.
- **[Médio impacto]** Resolve a ação decorrente do ADR-0010 sobre configurar o
  `generate_schema_name`: o schema passa a ser derivado da pasta do modelo, sem
  ninguém digitar `001_bnz_`, `002_slv_` ou `003_gld_` à mão.
- **[Baixo impacto]** O catálogo é insumo direto para publicação em catálogo de
  metadados, sem redigitação.

### Desvantagens

- **[Alto impacto]** Cria um artefato que só tem valor se for mantido. Um
  catálogo que envelhece em relação às DAGs de ingestão é pior que catálogo
  nenhum, porque passa a ser consultado como se estivesse correto. O CI valida
  consistência interna, **não** correspondência com o dado real — nada detecta
  automaticamente que uma coluna mudou de nome na origem.
- **[Médio impacto]** `verificado` depende de alguém de fato conferir contra o
  dado ingerido. O risco previsível é que `false` vire o valor permanente por
  omissão, esvaziando a marcação — o mesmo risco que o ADR-0013 registrou para a
  classificação de sensibilidade.
- **[Médio impacto]** Substituir um ponto do ADR-0009 seis semanas depois de
  escrito mostra que a convenção foi definida sem ser implementada. O custo real
  é baixo porque não há acervo a migrar, mas o padrão de decidir antes de provar
  é o que precisa mudar.
- **[Médio impacto]** Mais uma ferramenta no onboarding: além de Airflow e dbt,
  o contribuidor precisa aprender o catálogo e o gerador.
- **[Baixo impacto]** O SQL gerado precisa de `make format` depois, porque a
  formatação canônica é do `sqlfmt` e o gerador não a reproduz.
- **[Baixo impacto]** O plano de join escolhe a primeira ligação viável, não a
  melhor: cruzamentos com mais de um caminho possível exigem revisão humana.

### Avaliação

Os ganhos superam os custos, e a assimetria está no tipo de erro que cada lado
produz. Sem esta decisão, o erro típico é um cruzamento silenciosamente errado
publicado como produto de dados — caro de detectar e de reverter, especialmente
em dados públicos sujeitos a auditoria. Com ela, o erro típico é um catálogo
desatualizado, que é visível, corrigível em um PR e limitado ao momento em que
alguém tenta usá-lo. Trocar erro silencioso por erro visível é o cerne do que se
compra aqui.

O momento também favorece: com a pasta `dbt/` vazia, não há acervo a migrar, e o
custo é integralmente de construção — que é a hora mais barata de pagá-lo.

Permanecem como **riscos ativos**: (i) o CI valida a consistência interna do
catálogo, não sua correspondência com o dado real, então a decadência silenciosa
continua possível e depende de revisão humana; e (ii) `verificado: false` pode
se tornar o padrão permanente por omissão, transformando a marcação em ruído em
vez de sinal.

## Consequências

- **Positivas**: o cruzamento entre sistemas estruturantes deixa de ser
  conhecimento tácito e passa a ser artefato versionado, executável e testado;
  criar um modelo em conformidade com os ADRs anteriores passa a ser mais barato
  que criá-lo fora deles; o `generate_schema_name` do ADR-0010 sai do papel.
- **Negativas**: o framework ganha um artefato de manutenção contínua cujo
  apodrecimento não é detectável automaticamente; o desenho de Bronze do
  ADR-0009 muda para quem já o tinha lido.
- **Ações decorrentes**:
  - Verificar contra o dado ingerido os mapeamentos hoje marcados como
    `verificado: false` (`compras_gov.uasg.co_orgao` e
    `compras_gov.natureza_despesa_material.co_natureza_despesa`), e medir a taxa
    de não-correspondência da ponte `co_uasg → co_ug_siafi` quando houver dado do
    SIAFI para compará-la.
  - Catalogar os demais sistemas estruturantes conforme forem ingeridos,
    começando pelos que mais se cruzam com compras — orçamento/financeiro e
    pessoal.
  - Migrar as DAGs de ingestão do schema `compras_gov.raw_*` para o
    `001_bnz_compras_gov` do ADR-0010, atualizando `origem_atual` no catálogo;
    até lá, o `sources.yml` gerado aponta para o schema atual.
  - Criar a DAG de transformação que executa os projetos dbt via Cosmos, e
    definir o padrão de nomenclatura de DAGs de transformação, deixado em aberto
    pelo ADR-0007.
  - Avaliar, quando houver fonte autoritativa, promover as entidades de
    referência a dimensões conformadas em `000_ref_*` (Alternativa C).

## Referências

- [ADR-0004 — Monorepo como estratégia de organização de código](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)
- [ADR-0006 — Arquitetura medallion (bronze/silver/gold)](./0006-arquitetura-medallion.md)
- [ADR-0007 — Padrão de nomenclatura das pastas/arquivos de DAGs de ingestão](./0007-nomenclatura-pastas-dags-ingestao.md)
- [ADR-0009 — Padrão de nomenclatura das pastas/arquivos de projetos dbt](./0009-nomenclatura-pastas-arquivos-dbt.md)
- [ADR-0010 — Padrão de nomenclatura de schemas e tabelas bronze/silver/gold](./0010-nomenclatura-schemas-tabelas-bronze-silver-gold.md)
- [ADR-0013 — Padrão de documentação de metadados de tabelas](./0013-padrao-documentacao-metadados-tabelas.md)
- [ADR-0016 — Tipagem de Parquet: promover Staging (MinIO) → Bronze](./0016-tipagem-parquet-staging-bronze.md)
- [Padrão de Arquitetura de Dados — MGI/SEGES/CDATA, v3.0](./arquitetura_dados_mgi.pdf)
  (documento interno de referência, ambiente DEV).
- [Catálogo de sistemas estruturantes](../../catalogo/README.md)
