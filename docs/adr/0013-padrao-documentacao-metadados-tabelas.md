# ADR-0013: Padrão de documentação de metadados de tabelas

- **Status**: Proposto
- **Data**: 2026-08-07
- **Autores**: -
- **Revisores**: -

## Introdução ao problema

As decisões anteriores já definem *onde* uma tabela vive e *como* ela se
chama: o [ADR-0006](./0006-arquitetura-medallion.md) estabelece o contrato
de qualidade por camada, o
[ADR-0009](./0009-nomenclatura-pastas-arquivos-dbt.md) a organização dos
modelos dbt e o
[ADR-0010](./0010-nomenclatura-schemas-tabelas-bronze-silver-gold.md) a
nomenclatura de schemas, tabelas e colunas. Nenhuma delas define **o que
precisa estar escrito sobre uma tabela** para que ela seja publicável.

O resultado é um acervo que cresce mais rápido que o entendimento sobre
ele:

- **Colunas indecifráveis.** Dados de sistemas estruturantes do governo
  federal chegam com nomes de coluna herdados de sistemas legados, muitas
  vezes abreviados e sem significado óbvio fora do sistema de origem.
  Quando esse nome atravessa a Bronze sem uma descrição associada, o
  conhecimento sobre o que a coluna significa fica apenas com quem escreveu
  a ingestão.
- **Ninguém sabe a quem perguntar.** Sem responsável declarado, uma dúvida
  sobre uma tabela (ou um dado suspeito) vira uma busca no histórico do
  Git para descobrir quem a criou — pessoa que frequentemente já não está
  no projeto. Isso é agravado pela rotatividade de equipes, risco já
  levantado nos ADRs [0001](./0001-airflow-como-orquestrador-de-fluxos-de-dados.md)
  e [0002](./0002-dbt-como-ferramenta-de-transformacao-de-dados.md).
- **Sensibilidade não declarada.** O framework trata dados públicos, mas
  não apenas: fontes de pessoal e de beneficiários carregam dados pessoais
  sujeitos à LGPD. Sem uma marcação explícita de sensibilidade **na
  definição da tabela**, a decisão sobre o que pode ser exposto em um
  dashboard, aberto como dado público ou concedido a um usuário fica a
  critério de quem estiver construindo cada consumo — exatamente o risco de
  governança inconsistente que motivou o
  [ADR-0003](./0003-govhub-como-framework-compartilhado-de-dados.md).
- **Documentação que nasce desatualizada.** Quando a descrição de uma
  tabela vive fora do repositório (wiki, planilha, documento), ela deixa de
  acompanhar a mudança do modelo já no primeiro PR que altera uma coluna.

Essa decisão precisa ser tomada agora porque a documentação é
retroativamente cara: descrever uma coluna no momento em que ela é criada
custa uma linha de YAML, e descrevê-la dois anos depois custa uma
investigação arqueológica no sistema de origem.

## Decisão

A documentação de uma tabela é **parte da definição da tabela**: vive no
`schema.yml` do modelo dbt correspondente, no mesmo repositório e no mesmo
PR que cria ou altera o modelo. Não há fonte de verdade de metadados fora do
código.

### Campos obrigatórios

Todo modelo declarado em `schema.yml` carrega:

| Campo | Onde | Conteúdo |
|---|---|---|
| `description` | modelo | O que a tabela representa, o recorte (período, escopo, unidade) e a granularidade — uma linha representa o quê. |
| `meta.owner` | modelo | Time responsável, no mesmo vocabulário de órgão/time usado pelo `CODEOWNERS` (ADR-0004). Pessoa nomeada não é aceita como owner. |
| `meta.sistema_origem` | modelo | Sistema de origem do dado, no mesmo vocabulário de `{sistema_origem}` usado por DAGs de ingestão (ADR-0007) e schemas Bronze (ADR-0010). |
| `meta.classificacao` | modelo e coluna | Classificação de sensibilidade (tabela abaixo). No modelo, a classificação mais restritiva entre suas colunas. |
| `description` | coluna | O que a coluna significa, em português, sem repetir o nome da coluna. Inclui a unidade quando numérica e o significado dos códigos quando for domínio fechado. |

### Vocabulário de classificação

| Valor | Significado |
|---|---|
| `publico` | Pode ser aberto como dado público, sem restrição. |
| `interno` | Uso interno do órgão; não é dado pessoal, mas não é para publicação. |
| `pessoal` | Dado pessoal sob LGPD (ex.: nome, matrícula, CPF, lotação identificável). |
| `pessoal_sensivel` | Dado pessoal sensível sob o art. 5º, II da LGPD (ex.: saúde, raça/cor, filiação sindical, biometria). |

A classificação é **declarada na coluna** e propagada para o modelo pelo
valor mais restritivo. Uma coluna sem classificação explícita é tratada
como `pessoal` até que alguém a classifique — o padrão falha para o lado
restritivo, não para o permissivo.

### Exigência por camada

O rigor acompanha o contrato de qualidade do ADR-0006:

| Camada | Exigência |
|---|---|
| **Bronze** | `description` do modelo, `meta.owner`, `meta.sistema_origem` e `meta.classificacao`. Descrição por coluna é **recomendada, não obrigatória** — a Bronze é fiel à fonte, e exigir descrição de cada coluna herdada de um sistema legado bloquearia a ingestão por um trabalho que pertence à Silver. |
| **Silver** | Tudo da Bronze, mais `description` **obrigatória em todas as colunas**. É a camada onde o nome da fonte é traduzido para o vocabulário do domínio, então é onde o significado precisa ficar registrado. |
| **Gold** | Tudo da Silver, mais: a `description` do modelo declara a pergunta de negócio que a tabela responde, e colunas calculadas (KPIs, agregações) descrevem a regra de cálculo, não apenas o resultado. |

### Enforcement

A exigência é verificada no CI, não apenas em revisão de código: um modelo
que não satisfaça a exigência da sua camada reprova o build. Um requisito
que depende só de disciplina humana é, na prática, opcional — e a lacuna de
enforcement automático é um risco já registrado no ADR-0006.

## Alternativas consideradas

### Alternativa A: Documentação em ferramenta externa (wiki, planilha, catálogo)

- Descrição: as descrições de tabelas e colunas são mantidas em uma
  ferramenta fora do repositório, editada pela interface da ferramenta.
- Prós: interface amigável para pessoas não técnicas; permite documentar
  tabelas que não são geradas por dbt; não trava PRs por falta de
  documentação.
- Contras: a documentação e o modelo divergem no primeiro PR que altera uma
  coluna sem que alguém lembre de atualizar a ferramenta — e nada sinaliza
  essa divergência. Além disso, a informação de sensibilidade fica fora do
  alcance de qualquer verificação automática do CI, que é onde ela precisa
  estar para bloquear publicação indevida.

### Alternativa B: Documentação obrigatória e idêntica em todas as camadas

- Descrição: exigir descrição de todas as colunas em Bronze, Silver e Gold,
  com o mesmo rigor.
- Prós: regra única, sem exceção para memorizar; cobertura total do acervo.
- Contras: torna o custo de ingerir uma fonte nova proporcional ao número de
  colunas que ela tem, incluindo colunas que o projeto sequer usará. Em
  fontes governamentais com dezenas ou centenas de colunas herdadas, isso
  transforma a documentação em obstáculo à ingestão — e o resultado
  previsível é o preenchimento de descrições vazias só para passar no CI,
  que é pior que a ausência declarada.

### Alternativa C: Documentação recomendada, sem verificação automática

- Descrição: definir o padrão e confiar na revisão de código para aplicá-lo.
- Prós: nenhum custo de implementação; nenhuma fricção no CI.
- Contras: é o status quo com um documento a mais. A cobertura passa a
  depender da atenção do revisor, e a classificação de sensibilidade — que
  é o campo com consequência regulatória — vira o mais fácil de esquecer,
  por não ter efeito visível em nenhum lugar.

### Não fazer nada / manter status quo

- Descrição: cada projeto documenta o que julgar necessário, no formato que
  preferir.
- Consequência: o acervo continua crescendo mais rápido que o entendimento
  sobre ele, e o conhecimento sobre o significado das colunas permanece
  distribuído entre pessoas em vez de registrado — com perda garantida a
  cada troca de equipe.

## Tradeoffs

### Vantagens

- **[Alto impacto]** A classificação de sensibilidade passa a ser um dado
  estruturado e verificável por máquina, e não uma convenção informal —
  base necessária para qualquer controle automatizado de exposição de dado
  pessoal sob LGPD.
- **[Alto impacto]** Documentação e modelo não divergem: como vivem no mesmo
  arquivo e no mesmo PR, alterar a coluna sem revisitar sua descrição é uma
  mudança visível na revisão.
- **[Médio impacto]** O significado das colunas de sistemas legados fica
  registrado no momento em que alguém ainda o conhece, reduzindo a
  dependência de pessoas específicas.
- **[Médio impacto]** `meta.owner` por time dá um destinatário determinístico
  para dúvidas e incidentes de dados, alinhado ao `CODEOWNERS` do monorepo.
- **[Médio impacto]** Graduar a exigência por camada mantém o custo de
  ingerir uma fonte nova baixo, concentrando o esforço de documentação onde
  a tradução para o domínio de fato acontece.
- **[Baixo impacto]** Metadados estruturados no `schema.yml` são insumo
  direto para publicação em catálogo de dados, sem redigitação.

### Desvantagens

- **[Alto impacto]** Adiciona fricção real a todo PR que cria ou altera
  modelo de Silver e Gold — e essa fricção recai desproporcionalmente sobre
  contribuições grandes, que são justamente as que mais precisam ser
  revisadas com calma.
- **[Médio impacto]** Descrição obrigatória verificada por CI é verificável
  em *existência*, não em *qualidade*: nada impede uma descrição que apenas
  reescreve o nome da coluna, e o CI a aceitará.
- **[Médio impacto]** Classificar sensibilidade exige um julgamento jurídico
  que nem todo contribuidor tem — e o padrão restritivo (`pessoal` quando
  não declarado) pode gerar classificação excessiva por precaução,
  restringindo dados que seriam legitimamente públicos.
- **[Baixo impacto]** A exigência só alcança tabelas geradas por dbt;
  objetos criados fora desse fluxo ficam sem cobertura.

### Avaliação

Os ganhos superam os custos, com uma ressalva de escopo. Para a
classificação de sensibilidade, o cálculo é claro: é um campo com
consequência regulatória, e o custo de declará-lo é uma linha por coluna
contra o custo de expor dado pessoal indevidamente. Para as descrições, o
ganho é real mas mais lento de se materializar, e é por isso que a exigência
é graduada por camada — cobrar tudo em Bronze converteria a regra em
obstáculo, com o efeito perverso previsto na Alternativa B.

Permanecem como **riscos ativos**: (i) o CI verifica presença, não
qualidade — descrições vazias de conteúdo continuarão passando, e apenas a
revisão humana as pega; e (ii) a classificação de sensibilidade depende de
um julgamento que o framework, sozinho, não qualifica — sem orientação
jurídica acessível aos times, o padrão restritivo tende a virar o valor
usado por omissão, esvaziando o significado da marcação.

## Consequências

- **Positivas**: o significado, a responsabilidade e a sensibilidade de cada
  tabela passam a estar registrados junto ao código, versionados e revisados
  como qualquer mudança; a classificação vira um dado consultável por
  máquina, viabilizando verificação automática de exposição indevida.
- **Negativas**: aumenta a fricção de contribuir com modelos Silver e Gold;
  cria a possibilidade de documentação formalmente presente e
  substancialmente vazia; exige dos times um julgamento de classificação
  para o qual nem sempre estarão preparados.
- **Ações decorrentes**:
  - Implementar a verificação no CI, com mensagem de erro que aponte o
    modelo, a coluna e a exigência não satisfeita.
  - Publicar um guia curto de classificação, com exemplos concretos de
    colunas típicas dos sistemas estruturantes em cada nível, para reduzir a
    dependência de julgamento caso a caso.
  - Definir o processo de migração do acervo já existente: aplicar a
    exigência a modelos novos e alterados de imediato, e tratar a cobertura
    retroativa como trabalho planejado por domínio, não como bloqueio geral.
  - Avaliar o uso da classificação como insumo para controle de acesso e
    para decisões de publicação como dado aberto — uso previsto, mas não
    definido por este ADR.

## Referências

- [ADR-0003 — GovHub como framework compartilhado de dados](./0003-govhub-como-framework-compartilhado-de-dados.md)
- [ADR-0004 — Monorepo como estratégia de organização de código](./0004-monorepo-como-estrategia-de-organizacao-de-codigo.md)
- [ADR-0006 — Arquitetura medallion (bronze/silver/gold)](./0006-arquitetura-medallion.md)
- [ADR-0009 — Padrão de nomenclatura das pastas/arquivos de projetos dbt](./0009-nomenclatura-pastas-arquivos-dbt.md)
- [ADR-0010 — Padrão de nomenclatura de schemas e tabelas bronze/silver/gold](./0010-nomenclatura-schemas-tabelas-bronze-silver-gold.md)
- [dbt — propriedades de modelos e colunas (`schema.yml`)](https://docs.getdbt.com/reference/model-properties)
- [Lei nº 13.709/2018 (LGPD) — art. 5º, I e II](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm)
- [Padrão de Arquitetura de Dados — MGI/SEGES/CDATA, v3.0](./arquitetura_dados_mgi.pdf)
  (documento interno de referência, ambiente DEV).
- [Estrutura de ADRs do repositório](./README.md)
