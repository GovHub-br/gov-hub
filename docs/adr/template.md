# ADR-NNNN: Título da decisão

- **Status**: Proposto <!-- Proposto | Aceito | Rejeitado | Substituído por ADR-XXXX | Depreciado -->
- **Data**: AAAA-MM-DD
- **Autores**: Nome (time/projeto)
- **Revisores**: Nome (time/projeto)

## Introdução ao problema

Descreva o problema ou a força motriz que exige uma decisão. Responda:

- Qual é o contexto (técnico, organizacional, de negócio) em que a decisão
  surge?
- Qual dor, limitação ou oportunidade está sendo endereçada?
- Por que essa decisão precisa ser tomada *agora*, e por que ela é relevante
  para o framework como um todo (e não apenas para um projeto consumidor)?
- Quais restrições já são conhecidas (técnicas, de prazo, de recursos,
  regulatórias — ex.: LGPD, dados públicos)?

## Decisão

Declare a decisão tomada em uma ou duas frases, de forma direta. Detalhe em
seguida o suficiente para que outro time consiga implementá-la ou adotá-la
sem precisar perguntar novamente.

## Alternativas consideradas

Liste as opções avaliadas, incluindo a opção de "não fazer nada" quando
aplicável. Para cada alternativa, explique brevemente por que foi ou não
escolhida.

### Alternativa A: `<nome>`

- Descrição breve.
- Prós.
- Contras.

### Alternativa B: `<nome>`

- Descrição breve.
- Prós.
- Contras.

### Não fazer nada / manter status quo

- Descrição do que aconteceria se nenhuma decisão fosse tomada.
- Por que essa opção foi ou não aceitável.

## Tradeoffs

Explicite o que se ganha e o que se perde com a decisão escolhida. Nenhuma
decisão arquitetural é gratuita — esta seção existe para tornar esse custo
visível e evitar que ele seja redescoberto (com dor) mais tarde.

Liste vantagens e desvantagens em listas separadas, não pareadas por
dimensão — nem toda vantagem tem uma desvantagem correspondente de peso
equivalente, e forçar esse pareamento (ex.: em uma tabela 1-para-1) esconde
quando os custos pesam mais que os ganhos, ou vice-versa. Marque cada item
com `[Alto impacto]`, `[Médio impacto]` ou `[Baixo impacto]` para este
contexto específico, e feche com uma **Avaliação** que declare explicitamente
o julgamento — por que os ganhos superam os custos (ou não) — em vez de
deixar o leitor inferir isso sozinho.

### Vantagens

- **[Alto/Médio/Baixo impacto]** ...
- **[Alto/Médio/Baixo impacto]** ...

### Desvantagens

- **[Alto/Médio/Baixo impacto]** ...
- **[Alto/Médio/Baixo impacto]** ...

### Avaliação

Declare o julgamento: os ganhos superam os custos neste contexto? Por quê?
Quais desvantagens permanecem como risco ativo a mitigar, mesmo com a
decisão tomada?

## Consequências

- **Positivas**: o que melhora a partir desta decisão.
- **Negativas**: o que piora, ou qual débito técnico/organizacional é criado.
- **Ações decorrentes**: migrações, comunicação a times consumidores, mudanças
  de processo necessárias.

## Referências

- Links para discussões, RFCs, issues, benchmarks ou documentação externa que
  embasaram a decisão.
