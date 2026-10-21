"""Load all generated synthetic source tables into PostgreSQL."""

from typing import Any

import numpy as np
import pandas as pd
from psycopg import Connection, sql

from data_generator.database import get_connection
from data_generator.generate_all import generate_all_tables

RAW_SCHEMA = "raw"


def normalize_value(value: object) -> object | None:
    """Convert pandas and NumPy values into psycopg-compatible values."""

    if value is None or pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()

    if isinstance(value, (float, np.floating)):
        normalized_float = float(value)

        if normalized_float.is_integer():
            return int(normalized_float)

        return normalized_float

    if isinstance(value, np.generic):
        return value.item()

    return value


def get_database_columns(
    connection: Connection[Any],
    table_name: str,
) -> tuple[str, ...]:
    """Return the physical columns of a raw PostgreSQL table."""

    query = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
        ORDER BY ordinal_position
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                RAW_SCHEMA,
                table_name,
            ),
        )
        rows = cursor.fetchall()

    return tuple(str(row[0]) for row in rows)


def validate_target_tables(
    connection: Connection[Any],
    tables: dict[str, pd.DataFrame],
) -> None:
    """Validate table existence and column compatibility before truncation."""

    for table_name, dataframe in tables.items():
        database_columns = get_database_columns(
            connection,
            table_name,
        )

        if not database_columns:
            raise RuntimeError(
                f"Target table does not exist: "
                f"{RAW_SCHEMA}.{table_name}"
            )

        generated_columns = tuple(
            str(column)
            for column in dataframe.columns
        )

        if len(generated_columns) != len(
            set(generated_columns)
        ):
            raise RuntimeError(
                f"Duplicate generated columns in table: "
                f"{table_name}"
            )

        missing_columns = (
            set(generated_columns)
            - set(database_columns)
        )
        unexpected_columns = (
            set(database_columns)
            - set(generated_columns)
        )

        if missing_columns or unexpected_columns:
            details = []

            if missing_columns:
                details.append(
                    "missing in PostgreSQL: "
                    + ", ".join(
                        sorted(missing_columns)
                    )
                )

            if unexpected_columns:
                details.append(
                    "not generated: "
                    + ", ".join(
                        sorted(unexpected_columns)
                    )
                )

            raise RuntimeError(
                f"Column mismatch for "
                f"{RAW_SCHEMA}.{table_name}: "
                + "; ".join(details)
            )


def truncate_target_tables(
    connection: Connection[Any],
    table_names: tuple[str, ...],
) -> None:
    """Truncate all target tables in one foreign-key-safe statement."""

    qualified_tables = [
        sql.Identifier(
            RAW_SCHEMA,
            table_name,
        )
        for table_name in table_names
    ]

    statement = sql.SQL(
        "TRUNCATE TABLE {} RESTART IDENTITY"
    ).format(
        sql.SQL(", ").join(
            qualified_tables
        )
    )

    with connection.cursor() as cursor:
        cursor.execute(statement)


def copy_dataframe(
    connection: Connection[Any],
    table_name: str,
    dataframe: pd.DataFrame,
) -> None:
    """Bulk-load one DataFrame into its corresponding PostgreSQL table."""

    columns = tuple(
        str(column)
        for column in dataframe.columns
    )

    copy_statement = sql.SQL(
        "COPY {} ({}) FROM STDIN"
    ).format(
        sql.Identifier(
            RAW_SCHEMA,
            table_name,
        ),
        sql.SQL(", ").join(
            sql.Identifier(column)
            for column in columns
        ),
    )

    with (
        connection.cursor() as cursor,
        cursor.copy(copy_statement) as copy,
    ):
        for row in dataframe.itertuples(
            index=False,
            name=None,
        ):
            copy.write_row(
                tuple(
                    normalize_value(value)
                    for value in row
                )
            )


def get_loaded_row_count(
    connection: Connection[Any],
    table_name: str,
) -> int:
    """Return the current row count for one loaded table."""

    query = sql.SQL(
        "SELECT COUNT(*) FROM {}"
    ).format(
        sql.Identifier(
            RAW_SCHEMA,
            table_name,
        )
    )

    with connection.cursor() as cursor:
        cursor.execute(query)
        row = cursor.fetchone()

    if row is None:
        raise RuntimeError(
            f"PostgreSQL returned no count for "
            f"{RAW_SCHEMA}.{table_name}"
        )

    return int(row[0])


def validate_loaded_counts(
    connection: Connection[Any],
    tables: dict[str, pd.DataFrame],
) -> None:
    """Reconcile generated and persisted row counts."""

    for table_name, dataframe in tables.items():
        expected_count = len(dataframe)
        loaded_count = get_loaded_row_count(
            connection,
            table_name,
        )

        if loaded_count != expected_count:
            raise RuntimeError(
                f"Row-count mismatch for "
                f"{RAW_SCHEMA}.{table_name}: "
                f"expected {expected_count}, "
                f"loaded {loaded_count}"
            )


def load_all_tables() -> None:
    """Generate and atomically load all raw source tables."""

    tables = generate_all_tables()
    total_rows = sum(
        len(dataframe)
        for dataframe in tables.values()
    )

    print(
        f"Generated {len(tables)} tables "
        f"with {total_rows} rows"
    )

    with get_connection() as connection:
        validate_target_tables(
            connection,
            tables,
        )

        print("Target tables and columns validated")

        truncate_target_tables(
            connection,
            tuple(tables),
        )

        print("Existing raw data truncated")

        for table_name, dataframe in tables.items():
            copy_dataframe(
                connection,
                table_name,
                dataframe,
            )

            print(
                f"{table_name}: "
                f"{len(dataframe)} rows loaded"
            )

        validate_loaded_counts(
            connection,
            tables,
        )

        print("Database row counts reconciled")

    print("PostgreSQL load completed successfully")


def main() -> None:
    """Run the complete PostgreSQL loading process."""

    load_all_tables()


if __name__ == "__main__":
    main()