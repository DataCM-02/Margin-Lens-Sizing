"""PostgreSQL connection helpers for the MarginLens generator."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg import Connection

from data_generator.config import DatabaseConfig


@contextmanager
def get_connection(
    config: DatabaseConfig | None = None,
) -> Iterator[Connection[Any]]:
    """Open a PostgreSQL connection and close it safely after use."""

    database_config = config or DatabaseConfig.from_env()

    with psycopg.connect(
        **database_config.connection_kwargs(),
    ) as connection:
        yield connection


def get_connection_summary() -> dict[str, str]:
    """Return non-sensitive information about the connected database."""

    query = """
        SELECT
            current_database() AS database_name,
            current_user AS database_user,
            current_schema() AS current_schema,
            version() AS postgres_version
    """

    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(query)
        row = cursor.fetchone()

    if row is None:
        raise RuntimeError("PostgreSQL returned no connection information.")

    return {
        "database_name": row[0],
        "database_user": row[1],
        "current_schema": row[2],
        "postgres_version": row[3],
    }


def main() -> None:
    """Run a safe connection test from the command line."""

    summary = get_connection_summary()

    print("Database connection successful")
    print(f"Database: {summary['database_name']}")
    print(f"User: {summary['database_user']}")
    print(f"Current schema: {summary['current_schema']}")
    print(f"Server: {summary['postgres_version'].split(',')[0]}")


if __name__ == "__main__":
    main()