"""Orchestrate the complete deterministic synthetic-data generation."""

import pandas as pd

from data_generator.generators.commercial_master_data import (
    generate_commercial_master_data,
)
from data_generator.generators.costing_and_bom import (
    generate_costing_and_bom,
)
from data_generator.generators.fulfillment_and_traceability import (
    generate_fulfillment_and_traceability,
)
from data_generator.generators.industrial_master_data import (
    generate_industrial_master_data,
)
from data_generator.generators.manufacturing_transactions import (
    generate_manufacturing_transactions,
)
from data_generator.generators.pricing_and_sales import (
    generate_pricing_and_sales,
)
from data_generator.generators.procurement_transactions import (
    generate_procurement_transactions,
)
from data_generator.random_context import RandomContext

TABLE_LOAD_ORDER = (
    "plants",
    "production_lines",
    "product_families",
    "products",
    "component_categories",
    "components",
    "suppliers",
    "customer_segments",
    "customers",
    "sales_channels",
    "salespeople",
    "exchange_rates",
    "component_standard_cost_history",
    "component_cost_history",
    "bill_of_materials",
    "bill_of_material_items",
    "standard_conversion_costs",
    "purchase_orders",
    "purchase_order_items",
    "component_receipts",
    "production_orders",
    "production_lots",
    "production_material_consumption",
    "production_conversion_costs",
    "production_quality_events",
    "price_lists",
    "price_list_items",
    "discount_policies",
    "approved_discount_exceptions",
    "sales_orders",
    "sales_order_items",
    "shipments",
    "shipment_items",
    "shipment_freight_costs",
    "sales_commissions",
    "sales_variable_expenses",
    "sales_returns",
    "sales_lot_allocations",
)


def generate_all_tables() -> dict[str, pd.DataFrame]:
    """Generate all raw source tables in dependency order."""

    context = RandomContext()

    industrial_tables = (
        generate_industrial_master_data(
            context
        )
    )

    commercial_tables = (
        generate_commercial_master_data(
            context
        )
    )

    costing_tables = generate_costing_and_bom(
        context,
        industrial_tables,
    )

    procurement_tables = (
        generate_procurement_transactions(
            context,
            industrial_tables,
            costing_tables,
        )
    )

    manufacturing_tables = (
        generate_manufacturing_transactions(
            context,
            industrial_tables,
            costing_tables,
            procurement_tables,
        )
    )

    pricing_and_sales_tables = (
        generate_pricing_and_sales(
            context,
            industrial_tables,
            commercial_tables,
            costing_tables,
        )
    )

    fulfillment_tables = (
        generate_fulfillment_and_traceability(
            context,
            industrial_tables,
            commercial_tables,
            manufacturing_tables,
            pricing_and_sales_tables,
        )
    )

    # Procurement expands the initial component-cost
    # balance with receipt-driven moving-average history.
    final_costing_tables = {
        **costing_tables,
        "component_cost_history": (
            procurement_tables[
                "component_cost_history"
            ]
        ),
    }

    procurement_source_tables = {
        table_name: dataframe
        for table_name, dataframe in (
            procurement_tables.items()
        )
        if table_name != "component_cost_history"
    }

    generated_groups = (
        industrial_tables,
        commercial_tables,
        final_costing_tables,
        procurement_source_tables,
        manufacturing_tables,
        pricing_and_sales_tables,
        fulfillment_tables,
    )

    unordered_tables = {}

    for group in generated_groups:
        duplicate_tables = (
            set(unordered_tables)
            & set(group)
        )

        if duplicate_tables:
            duplicates = ", ".join(
                sorted(duplicate_tables)
            )
            raise ValueError(
                "Duplicate generated tables: "
                f"{duplicates}"
            )

        unordered_tables.update(group)

    missing_tables = (
        set(TABLE_LOAD_ORDER)
        - set(unordered_tables)
    )
    unexpected_tables = (
        set(unordered_tables)
        - set(TABLE_LOAD_ORDER)
    )

    if missing_tables:
        missing = ", ".join(
            sorted(missing_tables)
        )
        raise ValueError(
            f"Missing generated tables: {missing}"
        )

    if unexpected_tables:
        unexpected = ", ".join(
            sorted(unexpected_tables)
        )
        raise ValueError(
            "Unexpected generated tables: "
            f"{unexpected}"
        )

    return {
        table_name: unordered_tables[
            table_name
        ]
        for table_name in TABLE_LOAD_ORDER
    }


def main() -> None:
    """Generate all tables and print a row-count manifest."""

    tables = generate_all_tables()

    total_rows = 0

    for table_name, dataframe in tables.items():
        row_count = len(dataframe)
        total_rows += row_count

        print(
            f"{table_name}: {row_count} rows"
        )

    print(
        f"total_tables: {len(tables)}"
    )
    print(
        f"total_rows: {total_rows}"
    )

if __name__ == "__main__":
    main()