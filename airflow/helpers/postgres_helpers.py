import logging

from airflow.providers.postgres.hooks.postgres import PostgresHook


def get_postgres_conn(data_base_name: str = "postgres_default") -> str:
    try:
        hook = PostgresHook(postgres_conn_id=data_base_name)
        connection = hook.get_connection(data_base_name)
        schema = connection.schema
        logging.info(
            f"[postgres_helpers] Obtained PostgreSQL connection: "
            f"dbname={schema}, user={connection.login},"
            f"host={connection.host}, port={connection.port}"
        )
        return (
            f"dbname={schema} user={connection.login} password={connection.password} "
            f"host={connection.host} port={connection.port}"
        )
    except Exception as e:
        logging.error(f"Failed to obtain PostgreSQL connection: {e}")
        raise
