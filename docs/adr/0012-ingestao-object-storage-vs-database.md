# ADR-0012: Ingestão em object storage em vez de banco diretamente

- **Status**: Backlog
- **Data**: 2026-07-15
- **Autores**: -
- **Revisores**: -

> Este ADR ainda não foi escrito — o número foi reservado para mapear a
> necessidade de documentação. Ao iniciar a redação, substitua este
> conteúdo pelo de [`template.md`](./template.md) e preencha todas as
> seções obrigatórias.

## Escopo (rascunho)

Por que ingerir dados brutos em um object storage (ex.: S3/MinIO) como
camada intermediária, em vez de escrever diretamente no banco de dados
analítico usado pelos projetos consumidores.
