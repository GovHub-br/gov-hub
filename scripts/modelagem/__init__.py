"""Ferramentas de modelagem a partir do catálogo de sistemas estruturantes.

O catálogo (``catalogo/``) declara quais entidades cada sistema estruturante
expõe e por quais chaves conformadas elas podem ser cruzadas. Este pacote lê
esse catálogo e o transforma em três coisas úteis:

- ``catalogo``: carregamento e validação (ADR-0017);
- ``mapa``: o mapa de cruzamento entre sistemas;
- ``gerador``: geração de modelos dbt e de metadados (ADR-0009, ADR-0013).
"""
