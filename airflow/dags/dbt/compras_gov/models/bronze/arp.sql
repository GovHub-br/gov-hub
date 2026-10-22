{{ config(materialized="table", database="data_warehouse", schema="001_bnz_compras_gov") }}

{% set bucket = env_var("MINIO_BUCKET", "data-lake") %}
{% set caminho = ("s3://" ~ bucket ~ "/compras_gov/arp/**/*.parquet") | replace("'", "''") %}

select *
from read_parquet('{{ caminho }}', union_by_name = true)
