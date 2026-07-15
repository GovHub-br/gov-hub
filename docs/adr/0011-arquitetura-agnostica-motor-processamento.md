# ADR-0011: Arquitetura agnóstica a motor de processamento de dados

- **Status**: Backlog
- **Data**: 2026-07-15
- **Autores**: -
- **Revisores**: -

> Este ADR ainda não foi escrito — o número foi reservado para mapear a
> necessidade de documentação. Ao iniciar a redação, substitua este
> conteúdo pelo de [`template.md`](./template.md) e preencha todas as
> seções obrigatórias.

## Escopo (rascunho)

Decisão sobre manter o framework agnóstico ao motor de processamento de
dados (ex.: não acoplar a um motor específico como Spark, Trino ou DuckDB),
permitindo trocar o motor sem reescrever pipelines de transformação.
