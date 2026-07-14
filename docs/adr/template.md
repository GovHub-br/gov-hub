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

| Dimensão | Ganho | Custo/Risco |
|---|---|---|
| Ex.: Complexidade operacional | ... | ... |
| Ex.: Curva de aprendizado para times consumidores | ... | ... |
| Ex.: Acoplamento entre projetos | ... | ... |
| Ex.: Custo de manutenção de longo prazo | ... | ... |

## Consequências

- **Positivas**: o que melhora a partir desta decisão.
- **Negativas**: o que piora, ou qual débito técnico/organizacional é criado.
- **Ações decorrentes**: migrações, comunicação a times consumidores, mudanças
  de processo necessárias.

## Referências

- Links para discussões, RFCs, issues, benchmarks ou documentação externa que
  embasaram a decisão.
