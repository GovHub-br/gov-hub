"""Indicadores de monitoramento do MIR (ADR-0022).

Cada módulo porta um script entregue pela equipe de BI como funções puras
(``list[dict] -> list[dict]``), sem I/O. A leitura dos modelos já
materializados e a gravação dos resultados ficam a cargo das DAGs em
``dags/data_indicators/<orgao>/``.
"""
