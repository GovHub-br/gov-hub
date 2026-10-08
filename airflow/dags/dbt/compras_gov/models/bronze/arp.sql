{{ config(materialized="table", database="data_warehouse", schema="001_bnz_compras_gov") }}

select *
from read_parquet('s3://data-lake/compras_gov/arp/**/*.parquet', union_by_name = true)