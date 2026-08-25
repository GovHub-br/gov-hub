FROM apache/superset:4.1.1

# A imagem oficial do Superset não traz driver de banco algum além do SQLite do
# próprio metastore. Sem psycopg2, o import do bundle falha ao criar a conexão
# com o warehouse — com um erro que a API devolve como "Import failed for an
# unknown reason", sem dizer que o driver é que está faltando.
#
# O driver de cada banco que as dashboards consultarem precisa entrar aqui.
USER root
RUN pip install --no-cache-dir psycopg2-binary==2.9.10
USER superset

# Config que habilita a API de papéis usada pela DAG de publicação.
COPY superset_config.py /app/pythonpath/superset_config.py
