"""Validate generated source data persisted in the raw schema."""

from dataclasses import dataclass
from typing import Any

import pandas as pd
from psycopg import Connection, sql

from data_generator.database import get_connection
from data_generator.generate_all import (
    TABLE_LOAD_ORDER,
    generate_all_tables,
)

RAW_SCHEMA = "raw"


@dataclass(frozen=True)
class QualityCheck:
    """Represent a data-quality query that must return zero."""

    name: str
    query: str


QUALITY_CHECKS = (
    QualityCheck(
        name="invalid sales quantities",
        query="""
            SELECT COUNT(*)
            FROM raw.sales_order_items
            WHERE ordered_quantity <= 0
               OR invoiced_quantity < 0
               OR invoiced_quantity > ordered_quantity
        """,
    ),
    QualityCheck(
        name="incorrect realized prices",
        query="""
            SELECT COUNT(*)
            FROM raw.sales_order_items
            WHERE ABS(
                realized_unit_price_brl
                - ROUND(
                    list_unit_price_brl
                    * (1 - discount_rate),
                    4
                )
            ) > 0.0001
        """,
    ),
    QualityCheck(
        name="inconsistent sales item statuses",
        query="""
            SELECT COUNT(*)
            FROM raw.sales_order_items
            WHERE (
                item_status = 'INVOICED'
                AND invoiced_quantity <> ordered_quantity
            )
            OR (
                item_status = 'PARTIALLY_INVOICED'
                AND NOT (
                    invoiced_quantity > 0
                    AND invoiced_quantity < ordered_quantity
                )
            )
            OR (
                item_status IN ('OPEN', 'CANCELLED')
                AND invoiced_quantity <> 0
            )
        """,
    ),
    QualityCheck(
        name="invoiced items without reconciled shipment",
        query="""
            WITH shipped AS (
                SELECT
                    sales_order_item_id,
                    SUM(shipped_quantity) AS shipped_quantity
                FROM raw.shipment_items
                GROUP BY sales_order_item_id
            )
            SELECT COUNT(*)
            FROM raw.sales_order_items AS item
            LEFT JOIN shipped
                ON shipped.sales_order_item_id
                = item.sales_order_item_id
            WHERE item.invoiced_quantity > 0
              AND (
                  shipped.sales_order_item_id IS NULL
                  OR ABS(
                      shipped.shipped_quantity
                      - item.invoiced_quantity
                  ) > 0.000001
              )
        """,
    ),
    QualityCheck(
        name="shipments for non-invoiced items",
        query="""
            SELECT COUNT(*)
            FROM raw.shipment_items AS shipment_item
            INNER JOIN raw.sales_order_items AS item
                ON item.sales_order_item_id
                = shipment_item.sales_order_item_id
            WHERE item.invoiced_quantity <= 0
        """,
    ),
    QualityCheck(
        name="unreconciled return dispositions",
        query="""
            SELECT COUNT(*)
            FROM raw.sales_returns
            WHERE ABS(
                returned_quantity
                - restocked_quantity
                - rework_quantity
                - scrapped_quantity
                - unknown_disposition_quantity
            ) > 0.000001
        """,
    ),
    QualityCheck(
        name="returns exceeding invoiced quantities",
        query="""
            SELECT COUNT(*)
            FROM raw.sales_returns AS return_item
            INNER JOIN raw.sales_order_items AS item
                ON item.sales_order_item_id
                = return_item.original_sales_order_item_id
            WHERE return_item.returned_quantity
                > item.invoiced_quantity + 0.000001
        """,
    ),
    QualityCheck(
        name="lot allocations exceeding invoiced quantities",
        query="""
            SELECT COUNT(*)
            FROM (
                SELECT
                    allocation.sales_order_item_id
                FROM raw.sales_lot_allocations AS allocation
                INNER JOIN raw.sales_order_items AS item
                    ON item.sales_order_item_id
                    = allocation.sales_order_item_id
                GROUP BY
                    allocation.sales_order_item_id,
                    item.invoiced_quantity
                HAVING SUM(allocation.allocated_quantity)
                    > item.invoiced_quantity + 0.000001
            ) AS violations
        """,
    ),
    QualityCheck(
        name="allocations before lot release",
        query="""
            SELECT COUNT(*)
            FROM raw.sales_lot_allocations AS allocation
            INNER JOIN raw.production_lots AS lot
                ON lot.production_lot_id
                = allocation.production_lot_id
            WHERE allocation.allocated_at::date
                < lot.released_date
        """,
    ),
)


def get_row_count(
    connection: Connection[Any],
    table_name: str,
) -> int:
    """Return the persisted row count for one raw table."""

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
            f"No row count returned for "
            f"{RAW_SCHEMA}.{table_name}"
        )

    return int(row[0])


def validate_table_set(
    connection: Connection[Any],
) -> None:
    """Confirm that the raw schema contains the expected tables."""

    query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = %s
          AND table_type = 'BASE TABLE'
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (RAW_SCHEMA,),
        )
        rows = cursor.fetchall()

    actual_tables = {
        str(row[0])
        for row in rows
    }
    expected_tables = set(
        TABLE_LOAD_ORDER
    )

    if actual_tables != expected_tables:
        missing = (
            expected_tables
            - actual_tables
        )
        unexpected = (
            actual_tables
            - expected_tables
        )

        raise RuntimeError(
            "Raw table-set mismatch. "
            f"Missing: {sorted(missing)}. "
            f"Unexpected: {sorted(unexpected)}."
        )


def validate_row_counts(
    connection: Connection[Any],
    expected_tables: dict[str, pd.DataFrame],
) -> int:
    """Compare PostgreSQL counts with deterministic generated counts."""

    total_rows = 0

    for table_name, dataframe in expected_tables.items():
        expected_count = len(dataframe)
        actual_count = get_row_count(
            connection,
            table_name,
        )

        if actual_count != expected_count:
            raise RuntimeError(
                f"Row-count mismatch for "
                f"{RAW_SCHEMA}.{table_name}: "
                f"expected {expected_count}, "
                f"found {actual_count}"
            )

        total_rows += actual_count

    return total_rows


def run_quality_checks(
    connection: Connection[Any],
) -> None:
    """Run business-rule checks that must return zero violations."""

    for check in QUALITY_CHECKS:
        with connection.cursor() as cursor:
            cursor.execute(check.query)
            row = cursor.fetchone()

        if row is None:
            raise RuntimeError(
                f"No result returned for check: "
                f"{check.name}"
            )

        violation_count = int(row[0])

        print(
            f"{check.name}: "
            f"{violation_count} violations"
        )

        if violation_count != 0:
            raise RuntimeError(
                f"Quality check failed: "
                f"{check.name}"
            )


def percentage(
    numerator: int,
    denominator: int,
) -> float:
    """Return a safe percentage."""

    if denominator == 0:
        return 0.0

    return (
        numerator
        / denominator
        * 100
    )


def print_business_metrics(
    connection: Connection[Any],
) -> None:
    """Print the main generated-data distribution metrics."""

    with connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT
                    COUNT(*) FILTER (
                        WHERE order_status = 'CANCELLED'
                    ),
                    COUNT(*)
                FROM raw.sales_orders
            """
        )
        order_row = cursor.fetchone()

        cursor.execute(
            """
                SELECT COUNT(*)
                FROM raw.sales_order_items
                WHERE invoiced_quantity > 0
            """
        )
        invoiced_row = cursor.fetchone()

        cursor.execute(
            "SELECT COUNT(*) FROM raw.sales_returns"
        )
        return_row = cursor.fetchone()

        cursor.execute(
            """
                SELECT COUNT(
                    DISTINCT sales_order_item_id
                )
                FROM raw.sales_lot_allocations
            """
        )
        traceability_row = cursor.fetchone()

        cursor.execute(
            """
                SELECT
                    EXTRACT(
                        YEAR FROM sales_order.order_date
                    )::integer AS order_year,
                    AVG(item.discount_rate)
                FROM raw.sales_order_items AS item
                INNER JOIN raw.sales_orders AS sales_order
                    ON sales_order.sales_order_id
                    = item.sales_order_id
                INNER JOIN raw.customers AS customer
                    ON customer.customer_id
                    = sales_order.customer_id
                WHERE customer.customer_code = 'CUS-0007'
                GROUP BY order_year
                ORDER BY order_year
            """
        )
        discount_rows = cursor.fetchall()

    if (
        order_row is None
        or invoiced_row is None
        or return_row is None
        or traceability_row is None
    ):
        raise RuntimeError(
            "PostgreSQL returned incomplete business metrics."
        )

    cancelled_orders = int(order_row[0])
    total_orders = int(order_row[1])
    invoiced_items = int(invoiced_row[0])
    returned_items = int(return_row[0])
    traced_items = int(traceability_row[0])

    print("\nBusiness distributions")
    print(
        "Cancellation rate: "
        f"{percentage(cancelled_orders, total_orders):.2f}%"
    )
    print(
        "Return rate: "
        f"{percentage(returned_items, invoiced_items):.2f}%"
    )
    print(
        "Traceability coverage: "
        f"{percentage(traced_items, invoiced_items):.2f}%"
    )

    for order_year, average_discount in discount_rows:
        print(
            f"CUS-0007 average discount in "
            f"{int(order_year)}: "
            f"{float(average_discount) * 100:.2f}%"
        )


def main() -> None:
    """Validate table structure, counts, and business rules."""

    print("Regenerating deterministic reference data")

    expected_tables = generate_all_tables()

    with get_connection() as connection:
        validate_table_set(
            connection
        )

        print(
            f"Raw table set validated: "
            f"{len(TABLE_LOAD_ORDER)} tables"
        )

        total_rows = validate_row_counts(
            connection,
            expected_tables,
        )

        print(
            f"Row counts reconciled: "
            f"{total_rows} rows"
        )

        run_quality_checks(
            connection
        )
        print_business_metrics(
            connection
        )

    print("\nRaw data validation completed successfully")


if __name__ == "__main__":
    main()