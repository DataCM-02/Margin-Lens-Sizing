"""Generate deterministic procurement and component receipt transactions."""

from datetime import date, timedelta

import pandas as pd

from data_generator.config import GENERATION_CONFIG
from data_generator.generators.costing_and_bom import (
    business_datetime,
    generate_costing_and_bom,
)
from data_generator.generators.industrial_master_data import (
    generate_industrial_master_data,
)
from data_generator.random_context import RandomContext

PURCHASE_QUANTITY_RANGES = {
    "PCB": (100, 500),
    "MCU": (200, 800),
    "COMM": (100, 600),
    "SENSOR": (300, 1_200),
    "POWER": (200, 700),
    "CONN": (1_000, 5_000),
    "ENC": (300, 1_200),
    "DISPLAY": (100, 500),
}


def generate_order_dates(
    context: RandomContext,
) -> list[date]:
    """Generate chronologically ordered purchase-order dates."""

    order_dates = [
        context.random_date(
            GENERATION_CONFIG.start_date,
            GENERATION_CONFIG.end_date,
        )
        for _ in range(
            GENERATION_CONFIG.purchase_order_count
        )
    ]

    return sorted(order_dates)


def build_order_status_sets(
    context: RandomContext,
) -> tuple[set[int], set[int], set[int]]:
    """Define exact cancelled, open, and partially received orders."""

    order_count = GENERATION_CONFIG.purchase_order_count

    cancelled_count = round(
        order_count
        * GENERATION_CONFIG.cancellation_target_rate
    )
    open_count = round(order_count * 0.02)
    partial_count = round(order_count * 0.03)

    open_start = order_count - open_count + 1
    partial_start = open_start - partial_count

    open_ids = set(
        range(
            open_start,
            order_count + 1,
        )
    )
    partial_ids = set(
        range(
            partial_start,
            open_start,
        )
    )

    cancellation_candidates = list(
        range(
            1,
            partial_start,
        )
    )

    cancelled_ids = {
        int(order_id)
        for order_id in context.rng.choice(
            cancellation_candidates,
            size=cancelled_count,
            replace=False,
        )
    }

    return cancelled_ids, open_ids, partial_ids


def purchase_quantity(
    context: RandomContext,
    category_code: str,
) -> float:
    """Generate a component purchase quantity."""

    minimum, maximum = PURCHASE_QUANTITY_RANGES[
        category_code
    ]

    raw_quantity = int(
        context.rng.integers(
            minimum,
            maximum + 1,
        )
    )

    rounded_quantity = max(
        10,
        round(raw_quantity / 10) * 10,
    )

    return float(rounded_quantity)


def first_day_next_month(value: date) -> date:
    """Return the first day of the month following a date."""

    if value.month == 12:
        return date(value.year + 1, 1, 1)

    return date(
        value.year,
        value.month + 1,
        1,
    )


def generate_procurement_base_tables(
    context: RandomContext,
    industrial_tables: dict[str, pd.DataFrame],
    costing_tables: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """Generate purchase orders, items, and component receipts."""

    components = industrial_tables["components"]
    categories = industrial_tables["component_categories"]
    suppliers = industrial_tables["suppliers"]

    component_catalog = (
        components.merge(
            categories[
                [
                    "component_category_id",
                    "category_code",
                ]
            ],
            on="component_category_id",
            how="left",
            validate="many_to_one",
        )
        .sort_values("component_id")
        .reset_index(drop=True)
    )

    exchange_rates = costing_tables["exchange_rates"]
    standard_costs = costing_tables[
        "component_standard_cost_history"
    ]

    rate_lookup = (
        exchange_rates.set_index(
            [
                "rate_date",
                "currency_code",
            ]
        )["rate_to_brl"]
        .astype(float)
        .to_dict()
    )

    opening_rates = {
        currency_code: float(
            rate_lookup[
                (
                    GENERATION_CONFIG.start_date,
                    currency_code,
                )
            ]
        )
        for currency_code in ("BRL", "USD", "EUR")
    }

    standard_2024 = standard_costs.loc[
        standard_costs["valid_from"].eq(
            date(2024, 1, 1)
        )
    ]

    standard_2024_lookup = (
        standard_2024.set_index("component_id")[
            "standard_unit_cost_brl"
        ]
        .astype(float)
        .to_dict()
    )

    order_dates = generate_order_dates(context)

    (
        cancelled_ids,
        open_ids,
        partial_ids,
    ) = build_order_status_sets(context)

    purchase_order_rows = []
    purchase_order_item_rows = []
    receipt_rows = []

    purchase_order_item_id = 1
    receipt_item_id = 1

    total_period_days = (
        GENERATION_CONFIG.end_date
        - GENERATION_CONFIG.start_date
    ).days

    for purchase_order_id, order_date in enumerate(
        order_dates,
        start=1,
    ):
        primary_index = (
            purchase_order_id - 1
        ) % len(component_catalog)

        primary_component = component_catalog.iloc[
            primary_index
        ]

        currency_code = str(
            primary_component["preferred_currency"]
        )

        supplier_candidates = suppliers.loc[
            suppliers["default_currency"].eq(
                currency_code
            )
            & suppliers["is_active"]
        ]

        if supplier_candidates.empty:
            raise ValueError(
                "No active supplier was found for currency "
                f"{currency_code}."
            )

        supplier_position = int(
            context.rng.integers(
                0,
                len(supplier_candidates),
            )
        )
        supplier_id = int(
            supplier_candidates.iloc[
                supplier_position
            ]["supplier_id"]
        )

        item_count = int(
            context.rng.choice(
                [1, 2, 3, 4],
                p=[0.25, 0.40, 0.25, 0.10],
            )
        )

        compatible_components = (
            component_catalog.loc[
                component_catalog[
                    "preferred_currency"
                ].eq(currency_code)
                & ~component_catalog[
                    "component_id"
                ].eq(
                    int(primary_component["component_id"])
                )
            ]
        )

        extra_count = min(
            item_count - 1,
            len(compatible_components),
        )

        if extra_count > 0:
            selected_positions = context.rng.choice(
                len(compatible_components),
                size=extra_count,
                replace=False,
            )

            extra_components = compatible_components.iloc[
                selected_positions
            ]

            selected_components = pd.concat(
                [
                    primary_component.to_frame().T,
                    extra_components,
                ],
                ignore_index=True,
            )
        else:
            selected_components = (
                primary_component.to_frame().T
            )

        maximum_lead_time = int(
            selected_components[
                "standard_lead_time_days"
            ]
            .astype(int)
            .max()
        )

        delivery_adjustment = int(
            context.rng.integers(-2, 8)
        )

        delivery_days = max(
            1,
            maximum_lead_time + delivery_adjustment,
        )

        expected_delivery_date = (
            order_date
            + timedelta(days=delivery_days)
        )

        if purchase_order_id in cancelled_ids:
            order_status = "CANCELLED"
        elif purchase_order_id in open_ids:
            order_status = "OPEN"
        elif purchase_order_id in partial_ids:
            order_status = "PARTIALLY_RECEIVED"
        else:
            order_status = "RECEIVED"

        created_at = business_datetime(
            order_date,
            9,
        )
        order_updated_at = created_at

        period_progress = (
            (order_date - GENERATION_CONFIG.start_date).days
            / total_period_days
        )

        for line_number, component in enumerate(
            selected_components.itertuples(index=False),
            start=1,
        ):
            component_id = int(component.component_id)
            component_code = str(component.component_code)
            category_code = str(component.category_code)

            standard_cost_2024 = float(
                standard_2024_lookup[component_id]
            )

            price_noise = float(
                context.rng.uniform(0.97, 1.03)
            )

            if (
                component_code
                == GENERATION_CONFIG.imported_component_scenario_code
            ):
                base_original_price = 21.50

                unit_price_original = (
                    base_original_price
                    * (1 + 0.20 * period_progress)
                    * price_noise
                )
            elif currency_code == "BRL":
                unit_price_original = (
                    standard_cost_2024
                    * 0.96
                    * (1 + 0.09 * period_progress)
                    * price_noise
                )
            else:
                base_original_price = (
                    standard_cost_2024
                    / opening_rates[currency_code]
                    * 0.82
                )

                unit_price_original = (
                    base_original_price
                    * (1 + 0.07 * period_progress)
                    * price_noise
                )

            unit_price_original = round(
                unit_price_original,
                6,
            )

            ordered_quantity = purchase_quantity(
                context,
                category_code,
            )

            item_updated_at = created_at

            current_item_id = (
                purchase_order_item_id
            )

            if order_status in {
                "RECEIVED",
                "PARTIALLY_RECEIVED",
            }:
                delivery_variation = int(
                    context.rng.integers(-3, 11)
                )

                receipt_date = (
                    expected_delivery_date
                    + timedelta(
                        days=delivery_variation
                    )
                )

                receipt_date = max(
                    order_date,
                    receipt_date,
                )
                receipt_date = min(
                    receipt_date,
                    GENERATION_CONFIG.end_date,
                )

                if order_status == "RECEIVED":
                    received_quantity = (
                        ordered_quantity
                    )
                else:
                    received_quantity = round(
                        ordered_quantity
                        * float(
                            context.rng.uniform(
                                0.55,
                                0.85,
                            )
                        ),
                        6,
                    )

                exchange_rate = float(
                    rate_lookup[
                        (
                            receipt_date,
                            currency_code,
                        )
                    ]
                )

                material_value_brl = (
                    received_quantity
                    * unit_price_original
                    * exchange_rate
                )

                if currency_code == "BRL":
                    international_freight = 0.0
                    insurance = 0.0
                    import_tax = 0.0

                    domestic_freight = (
                        material_value_brl
                        * float(
                            context.rng.uniform(
                                0.012,
                                0.035,
                            )
                        )
                    )

                    other_landed_cost = (
                        material_value_brl
                        * float(
                            context.rng.uniform(
                                0.000,
                                0.005,
                            )
                        )
                    )
                else:
                    international_freight = (
                        material_value_brl
                        * float(
                            context.rng.uniform(
                                0.050,
                                0.090,
                            )
                        )
                    )

                    insurance = (
                        material_value_brl
                        * float(
                            context.rng.uniform(
                                0.004,
                                0.012,
                            )
                        )
                    )

                    import_tax = (
                        material_value_brl
                        * float(
                            context.rng.uniform(
                                0.100,
                                0.180,
                            )
                        )
                    )

                    domestic_freight = (
                        material_value_brl
                        * float(
                            context.rng.uniform(
                                0.010,
                                0.025,
                            )
                        )
                    )

                    other_landed_cost = (
                        material_value_brl
                        * float(
                            context.rng.uniform(
                                0.003,
                                0.015,
                            )
                        )
                    )

                receipt_timestamp = (
                    business_datetime(
                        receipt_date,
                        15,
                    )
                )

                receipt_rows.append(
                    {
                        "receipt_item_id": (
                            receipt_item_id
                        ),
                        "purchase_order_item_id": (
                            current_item_id
                        ),
                        "receipt_number": (
                            f"RCV-{purchase_order_id:06d}"
                        ),
                        "receipt_line_number": (
                            line_number
                        ),
                        "receipt_date": receipt_date,
                        "received_quantity": (
                            received_quantity
                        ),
                        "exchange_rate_to_brl": round(
                            exchange_rate,
                            6,
                        ),
                        "international_freight_brl": round(
                            international_freight,
                            4,
                        ),
                        "insurance_brl": round(
                            insurance,
                            4,
                        ),
                        "nonrecoverable_import_tax_brl": round(
                            import_tax,
                            4,
                        ),
                        "domestic_freight_brl": round(
                            domestic_freight,
                            4,
                        ),
                        "other_landed_cost_brl": round(
                            other_landed_cost,
                            4,
                        ),
                        "created_at": receipt_timestamp,
                        "updated_at": receipt_timestamp,
                    }
                )

                receipt_item_id += 1
                item_updated_at = receipt_timestamp
                order_updated_at = max(
                    order_updated_at,
                    receipt_timestamp,
                )

            purchase_order_item_rows.append(
                {
                    "purchase_order_item_id": (
                        current_item_id
                    ),
                    "purchase_order_id": (
                        purchase_order_id
                    ),
                    "line_number": line_number,
                    "component_id": component_id,
                    "ordered_quantity": (
                        ordered_quantity
                    ),
                    "unit_price_original_currency": (
                        unit_price_original
                    ),
                    "created_at": created_at,
                    "updated_at": item_updated_at,
                }
            )

            purchase_order_item_id += 1

        purchase_order_rows.append(
            {
                "purchase_order_id": (
                    purchase_order_id
                ),
                "purchase_order_number": (
                    f"PO-{order_date.year}-"
                    f"{purchase_order_id:06d}"
                ),
                "supplier_id": supplier_id,
                "plant_id": 1,
                "order_date": order_date,
                "expected_delivery_date": (
                    expected_delivery_date
                ),
                "currency_code": currency_code,
                "order_status": order_status,
                "created_at": created_at,
                "updated_at": order_updated_at,
            }
        )

    return {
        "purchase_orders": pd.DataFrame(
            purchase_order_rows
        ),
        "purchase_order_items": pd.DataFrame(
            purchase_order_item_rows
        ),
        "component_receipts": pd.DataFrame(
            receipt_rows
        ),
    }


def generate_component_cost_history(
    procurement_tables: dict[str, pd.DataFrame],
    opening_cost_history: pd.DataFrame,
) -> pd.DataFrame:
    """Roll receipt landed costs into monthly moving-average history."""

    purchase_orders = procurement_tables[
        "purchase_orders"
    ]
    purchase_order_items = procurement_tables[
        "purchase_order_items"
    ]
    component_receipts = procurement_tables[
        "component_receipts"
    ]

    receipt_costs = (
        component_receipts.merge(
            purchase_order_items[
                [
                    "purchase_order_item_id",
                    "purchase_order_id",
                    "component_id",
                    "unit_price_original_currency",
                ]
            ],
            on="purchase_order_item_id",
            how="inner",
            validate="many_to_one",
        )
        .merge(
            purchase_orders[
                [
                    "purchase_order_id",
                    "currency_code",
                ]
            ],
            on="purchase_order_id",
            how="inner",
            validate="many_to_one",
        )
    )

    landed_cost_columns = [
        "international_freight_brl",
        "insurance_brl",
        "nonrecoverable_import_tax_brl",
        "domestic_freight_brl",
        "other_landed_cost_brl",
    ]

    receipt_costs["material_value_brl"] = (
        receipt_costs["received_quantity"].astype(float)
        * receipt_costs[
            "unit_price_original_currency"
        ].astype(float)
        * receipt_costs[
            "exchange_rate_to_brl"
        ].astype(float)
    )

    receipt_costs["landed_cost_value_brl"] = (
        receipt_costs[landed_cost_columns]
        .astype(float)
        .sum(axis=1)
    )

    receipt_costs["total_receipt_cost_brl"] = (
        receipt_costs["material_value_brl"]
        + receipt_costs["landed_cost_value_brl"]
    )

    receipt_costs["effective_date"] = (
        receipt_costs["receipt_date"].map(
            first_day_next_month
        )
    )

    receipt_costs = receipt_costs.loc[
        receipt_costs["effective_date"].le(
            GENERATION_CONFIG.end_date
        )
    ]

    monthly_receipts = (
        receipt_costs.groupby(
            [
                "component_id",
                "effective_date",
            ],
            as_index=False,
        )
        .agg(
            received_quantity=(
                "received_quantity",
                "sum",
            ),
            receipt_cost_brl=(
                "total_receipt_cost_brl",
                "sum",
            ),
        )
        .sort_values(
            [
                "component_id",
                "effective_date",
            ]
        )
    )

    history_rows = opening_cost_history.copy(
        deep=True
    ).to_dict(orient="records")

    current_row_by_component = {
        int(row["component_id"]): row
        for row in history_rows
    }

    next_cost_id = (
        int(
            opening_cost_history[
                "component_cost_id"
            ].max()
        )
        + 1
    )

    for monthly_receipt in monthly_receipts.itertuples(
        index=False
    ):
        component_id = int(
            monthly_receipt.component_id
        )
        effective_date = (
            monthly_receipt.effective_date
        )

        previous_row = current_row_by_component[
            component_id
        ]

        previous_row["valid_to"] = (
            effective_date
            - timedelta(days=1)
        )

        previous_average_cost = float(
            previous_row[
                "moving_average_unit_cost_brl"
            ]
        )

        received_quantity = float(
            monthly_receipt.received_quantity
        )
        receipt_cost_brl = float(
            monthly_receipt.receipt_cost_brl
        )

        # A notional opening balance keeps the moving average
        # stable while allowing receipts to update the cost.
        opening_balance_quantity = max(
            received_quantity * 0.50,
            1.0,
        )

        new_average_cost = (
            (
                previous_average_cost
                * opening_balance_quantity
            )
            + receipt_cost_brl
        ) / (
            opening_balance_quantity
            + received_quantity
        )

        record_timestamp = business_datetime(
            effective_date,
            8,
        )

        new_row = {
            "component_cost_id": next_cost_id,
            "component_id": component_id,
            "plant_id": 1,
            "valid_from": effective_date,
            "valid_to": None,
            "moving_average_unit_cost_brl": round(
                new_average_cost,
                6,
            ),
            "cost_source": "PURCHASE_RECEIPT",
            "source_reference": (
                f"RCPT-{effective_date:%Y-%m}"
            ),
            "created_at": record_timestamp,
            "updated_at": record_timestamp,
        }

        history_rows.append(new_row)
        current_row_by_component[
            component_id
        ] = new_row

        next_cost_id += 1

    return (
        pd.DataFrame(history_rows)
        .sort_values(
            [
                "component_id",
                "valid_from",
            ]
        )
        .reset_index(drop=True)
    )


def generate_procurement_transactions(
    context: RandomContext,
    industrial_tables: dict[str, pd.DataFrame],
    costing_tables: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """Generate procurement tables and receipt-driven cost history."""

    procurement_tables = (
        generate_procurement_base_tables(
            context,
            industrial_tables,
            costing_tables,
        )
    )

    component_cost_history = (
        generate_component_cost_history(
            procurement_tables,
            costing_tables[
                "component_cost_history"
            ],
        )
    )

    return {
        **procurement_tables,
        "component_cost_history": (
            component_cost_history
        ),
    }


def main() -> None:
    """Generate procurement data and print row counts."""

    context = RandomContext()

    industrial_tables = (
        generate_industrial_master_data(context)
    )

    costing_tables = generate_costing_and_bom(
        context,
        industrial_tables,
    )

    tables = generate_procurement_transactions(
        context,
        industrial_tables,
        costing_tables,
    )

    for table_name, dataframe in tables.items():
        print(f"{table_name}: {len(dataframe)} rows")


if __name__ == "__main__":
    main()