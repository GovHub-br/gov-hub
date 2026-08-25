"""Ferramentas de publicação de produtos de dados (ADR-0019, ADR-0020).

O catálogo de publicação (``catalogo/publicacao/<orgao>.yml``) declara o que um
órgão publica — datasets, dashboards e relatórios — e quem consome cada coisa.
Este pacote lê essa declaração e a transforma em:

- ``validacao``: verificação de que o que está declarado corresponde ao que os
  bundles de dashboard realmente expõem, e de que nenhum consumidor alcança
  coluna acima do seu nível de acesso;
- ``acesso``: o plano de acesso (papéis, permissões e recorte de linhas)
  derivado do catálogo e aplicado no Superset pela DAG de publicação;
- ``bundle``: leitura dos bundles exportados do Superset versionados no repo.
"""
