"""Generate deterministic fulfillment, returns, and lot traceability."""

from datetime import timedelta

import pandas as pd

from data_generator.config import GENERATION_CONFIG
from data_generator.generators.commercial_master_data import (
    generate_commercial_master_data,
)
from data_generator.generators.costing_and_bom import (
    business_datetime,
    generate_costing_and_bom,
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

CARRIERS = [
    "RotaSul Transportes",
    "TransVale Logística",
    "Expresso Campinas",
    "Norte Cargo",
    "Via Brasil Transportes",
]


REGION_TRANSIT_DAYS = {
    "SOUTHEAST": (1, 4),
    "SOUTH": (3, 7),
    "CENTRAL_WEST": (4, 8),
    "NORTHEAST": (6, 11),
    "NORTH": (8, 15),
}


REGION_FREIGHT_FACTOR = {
    "SOUTHEAST": 1.00,
    "SOUTH": 1.15,
    "CENTRAL_WEST": 1.25,
    "NORTHEAST": 1.40,
    "NORTH": 1.60,
}


COMMISSION_RATE_BY_CHANNEL = {
    "DIRECT": 0.025,
    "PARTNER": 0.018,
    "DIGITAL_B2B": 0.012,
}


WARRANTY_RATE_BY_FAMILY = {
    "CTRL": 0.012,
    "IOT": 0.015,
    "ENERGY": 0.010,
}


RETURN_REASON_CODES = [
    "CUSTOMER_DISSATISFACTION",
    "TRANSPORT_DAMAGE",
    "INSTALLATION_FAILURE",
    "COMMERCIAL_AGREEMENT",
    "PRODUCT_DEFECT",
]


def build_invoiced_item_catalog(
    industrial_tables: dict[str, pd.DataFrame],
    commercial_tables: dict[str, pd.DataFrame],
    sales_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Enrich invoiced sales items with order and master data."""

    sales_order_items = sales_tables[
        "sales_order_items"
    ]
    sales_orders = sales_tables["sales_orders"]
    customers = commercial_tables["customers"]
    channels = commercial_tables["sales_channels"]
    products = industrial_tables["products"]
    families = industrial_tables["product_families"]

    product_catalog = products.merge(
        families[
            [
                "product_family_id",
                "family_code",
            ]
        ],
        on="product_family_id",
        how="left",
        validate="many_to_one",
    )

    return (
        sales_order_items.loc[
            sales_order_items[
                "invoiced_quantity"
            ].gt(0)
        ][
            [
                "sales_order_item_id",
                "sales_order_id",
                "product_id",
                "invoiced_quantity",
                "realized_unit_price_brl",
                "managerial_sales_tax_rate",
                "invoice_date",
            ]
        ]
        .merge(
            sales_orders[
                [
                    "sales_order_id",
                    "customer_id",
                    "salesperson_id",
                    "sales_channel_id",
                ]
            ],
            on="sales_order_id",
            how="inner",
            validate="many_to_one",
        )
        .merge(
            customers[
                [
                    "customer_id",
                    "sales_region",
                ]
            ],
            on="customer_id",
            how="inner",
            validate="many_to_one",
        )
        .merge(
            channels[
                [
                    "sales_channel_id",
                    "channel_code",
                ]
            ],
            on="sales_channel_id",
            how="inner",
            validate="many_to_one",
        )
        .merge(
            product_catalog[
                [
                    "product_id",
                    "family_code",
                    "gross_weight_kg",
                    "package_volume_m3",
                ]
            ],
            on="product_id",
            how="inner",
            validate="many_to_one",
        )
    )


def generate_shipments(
    context: RandomContext,
    invoiced_items: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[int, dict[str, object]],
]:
    """Generate shipments, shipment items, and freight costs."""

    shipment_rows = []
    shipment_item_rows = []
    freight_rows = []
    shipment_lookup = {}

    shipment_id = 1
    shipment_item_id = 1
    freight_cost_id = 1

    grouped_orders = invoiced_items.groupby(
        "sales_order_id",
        sort=True,
    )

    for sales_order_id, order_items in grouped_orders:
        sales_region = str(
            order_items.iloc[0][
                "sales_region"
            ]
        )

        shipment_date = max(
            order_items["invoice_date"]
        )

        minimum_days, maximum_days = (
            REGION_TRANSIT_DAYS[sales_region]
        )

        transit_days = int(
            context.rng.integers(
                minimum_days,
                maximum_days + 1,
            )
        )

        planned_delivery_date = (
            shipment_date
            + timedelta(days=transit_days)
        )

        if (
            planned_delivery_date
            <= GENERATION_CONFIG.end_date
        ):
            delivery_date = (
                planned_delivery_date
            )
            shipment_status = "DELIVERED"
        else:
            delivery_date = None
            shipment_status = "SHIPPED"

        carrier_name = str(
            context.rng.choice(CARRIERS)
        )

        created_at = business_datetime(
            shipment_date,
            10,
        )
        updated_at = (
            business_datetime(
                delivery_date,
                17,
            )
            if delivery_date is not None
            else created_at
        )

        shipment_rows.append(
            {
                "shipment_id": shipment_id,
                "shipment_number": (
                    f"SHP-{shipment_id:07d}"
                ),
                "sales_order_id": int(
                    sales_order_id
                ),
                "plant_id": 1,
                "carrier_name": carrier_name,
                "shipment_date": shipment_date,
                "delivery_date": delivery_date,
                "shipment_status": (
                    shipment_status
                ),
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )

        total_weight = 0.0
        total_volume = 0.0

        for item in order_items.itertuples(
            index=False
        ):
            shipped_quantity = float(
                item.invoiced_quantity
            )

            gross_weight = round(
                shipped_quantity
                * float(item.gross_weight_kg),
                6,
            )
            volume = round(
                shipped_quantity
                * float(item.package_volume_m3),
                8,
            )

            total_weight += gross_weight
            total_volume += volume

            shipment_item_rows.append(
                {
                    "shipment_item_id": (
                        shipment_item_id
                    ),
                    "shipment_id": shipment_id,
                    "sales_order_item_id": int(
                        item.sales_order_item_id
                    ),
                    "shipped_quantity": (
                        shipped_quantity
                    ),
                    "gross_weight_kg": (
                        gross_weight
                    ),
                    "volume_m3": volume,
                    "created_at": created_at,
                    "updated_at": created_at,
                }
            )

            shipment_item_id += 1

        freight_factor = (
            REGION_FREIGHT_FACTOR[
                sales_region
            ]
        )

        base_freight = max(
            120.0,
            (
                total_weight * 0.85
                + total_volume * 250.0
            )
            * freight_factor,
        )

        fuel_surcharge = (
            base_freight
            * float(
                context.rng.uniform(
                    0.06,
                    0.12,
                )
            )
        )
        insurance = (
            base_freight
            * float(
                context.rng.uniform(
                    0.01,
                    0.03,
                )
            )
        )
        other_charge = (
            base_freight
            * float(
                context.rng.uniform(
                    0.00,
                    0.025,
                )
            )
        )

        responsibility = (
            context.weighted_choice(
                ["COMPANY", "CUSTOMER"],
                [0.72, 0.28],
            )
        )

        freight_rows.append(
            {
                "freight_cost_id": (
                    freight_cost_id
                ),
                "shipment_id": shipment_id,
                "freight_date": shipment_date,
                "freight_responsibility": (
                    responsibility
                ),
                "base_freight_brl": round(
                    base_freight,
                    4,
                ),
                "fuel_surcharge_brl": round(
                    fuel_surcharge,
                    4,
                ),
                "insurance_brl": round(
                    insurance,
                    4,
                ),
                "other_charge_brl": round(
                    other_charge,
                    4,
                ),
                "created_at": created_at,
                "updated_at": created_at,
            }
        )

        shipment_lookup[
            int(sales_order_id)
        ] = {
            "shipment_id": shipment_id,
            "shipment_date": shipment_date,
        }

        shipment_id += 1
        freight_cost_id += 1

    return (
        pd.DataFrame(shipment_rows),
        pd.DataFrame(shipment_item_rows),
        pd.DataFrame(freight_rows),
        shipment_lookup,
    )


def generate_sales_expenses(
    invoiced_items: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate item commissions and variable expenses."""

    commission_rows = []
    expense_rows = []

    commission_id = 1
    expense_id = 1

    for item in invoiced_items.itertuples(
        index=False
    ):
        gross_revenue = (
            float(item.invoiced_quantity)
            * float(
                item.realized_unit_price_brl
            )
        )

        revenue_after_tax = (
            gross_revenue
            * (
                1
                - float(
                    item.managerial_sales_tax_rate
                )
            )
        )

        commission_rate = (
            COMMISSION_RATE_BY_CHANNEL[
                item.channel_code
            ]
        )

        commission_amount = round(
            revenue_after_tax
            * commission_rate,
            4,
        )

        record_timestamp = business_datetime(
            item.invoice_date,
            18,
        )

        commission_rows.append(
            {
                "commission_id": commission_id,
                "sales_order_id": int(
                    item.sales_order_id
                ),
                "sales_order_item_id": int(
                    item.sales_order_item_id
                ),
                "salesperson_id": int(
                    item.salesperson_id
                ),
                "commission_date": (
                    item.invoice_date
                ),
                "commission_scope": "ITEM",
                "commission_rate": (
                    commission_rate
                ),
                "commission_amount_brl": (
                    commission_amount
                ),
                "created_at": record_timestamp,
                "updated_at": record_timestamp,
            }
        )

        commission_id += 1

        expenses = [
            (
                "PACKAGING",
                gross_revenue * 0.005,
            ),
            (
                "WARRANTY_PROVISION",
                gross_revenue
                * WARRANTY_RATE_BY_FAMILY[
                    item.family_code
                ],
            ),
        ]

        if item.channel_code == "DIGITAL_B2B":
            expenses.append(
                (
                    "PAYMENT_FEE",
                    gross_revenue * 0.008,
                )
            )

        for expense_type, expense_amount in expenses:
            expense_rows.append(
                {
                    "variable_expense_id": (
                        expense_id
                    ),
                    "sales_order_item_id": int(
                        item.sales_order_item_id
                    ),
                    "expense_date": (
                        item.invoice_date
                    ),
                    "expense_type": (
                        expense_type
                    ),
                    "expense_amount_brl": round(
                        expense_amount,
                        4,
                    ),
                    "created_at": (
                        record_timestamp
                    ),
                    "updated_at": (
                        record_timestamp
                    ),
                }
            )

            expense_id += 1

    return (
        pd.DataFrame(commission_rows),
        pd.DataFrame(expense_rows),
    )


def generate_sales_returns(
    context: RandomContext,
    invoiced_items: pd.DataFrame,
) -> pd.DataFrame:
    """Generate returns with explicit product disposition."""

    target_return_count = round(
        len(invoiced_items)
        * GENERATION_CONFIG.return_target_rate
    )

    latest_eligible_invoice_date = (
        GENERATION_CONFIG.end_date
        - timedelta(days=15)
    )

    eligible_items = invoiced_items.loc[
        invoiced_items[
            "invoice_date"
        ].le(latest_eligible_invoice_date)
    ]

    if target_return_count > len(eligible_items):
        raise ValueError(
            "There are not enough eligible items "
            "to generate the target return rate."
        )

    selected_positions = context.rng.choice(
        len(eligible_items),
        size=target_return_count,
        replace=False,
    )

    selected_items = (
        eligible_items.iloc[selected_positions]
        .sort_values("invoice_date")
    )

    rows = []

    for return_item_id, item in enumerate(
        selected_items.itertuples(
            index=False
        ),
        start=1,
    ):
        return_date = min(
            item.invoice_date
            + timedelta(
                days=int(
                    context.rng.integers(
                        7,
                        46,
                    )
                )
            ),
            GENERATION_CONFIG.end_date,
        )

        initial_returned_quantity = round(
            float(item.invoiced_quantity)
            * float(
                context.rng.uniform(
                    0.10,
                    0.40,
                )
            ),
            6,
        )

        return_status = (
            context.weighted_choice(
                [
                    "APPROVED",
                    "RECEIVED",
                    "REJECTED",
                ],
                [0.80, 0.15, 0.05],
            )
        )

        if return_status == "REJECTED":
            restocked_quantity = 0.0
            rework_quantity = 0.0
            scrapped_quantity = 0.0
            unknown_quantity = (
                initial_returned_quantity
            )
            refund_unit_amount = 0.0
        else:
            restocked_quantity = round(
                initial_returned_quantity
                * float(
                    context.rng.uniform(
                        0.45,
                        0.75,
                    )
                ),
                6,
            )

            remaining_quantity = round(
                initial_returned_quantity
                - restocked_quantity,
                6,
            )

            rework_quantity = round(
                remaining_quantity
                * float(
                    context.rng.uniform(
                        0.15,
                        0.45,
                    )
                ),
                6,
            )

            remaining_quantity = round(
                remaining_quantity
                - rework_quantity,
                6,
            )

            scrapped_quantity = round(
                remaining_quantity
                * float(
                    context.rng.uniform(
                        0.65,
                        0.95,
                    )
                ),
                6,
            )

            unknown_quantity = round(
                initial_returned_quantity
                - restocked_quantity
                - rework_quantity
                - scrapped_quantity,
                6,
            )

            refund_unit_amount = float(
                item.realized_unit_price_brl
            )

        returned_quantity = round(
            restocked_quantity
            + rework_quantity
            + scrapped_quantity
            + unknown_quantity,
            6,
        )

        return_freight = (
            0.0
            if return_status == "REJECTED"
            else float(
                context.rng.uniform(
                    40.0,
                    180.0,
                )
            )
        )
        processing_cost = float(
            context.rng.uniform(
                15.0,
                60.0,
            )
        )

        record_timestamp = business_datetime(
            return_date,
            15,
        )

        rows.append(
            {
                "return_item_id": (
                    return_item_id
                ),
                "return_number": (
                    f"RET-{return_item_id:07d}"
                ),
                "return_line_number": 1,
                "original_sales_order_item_id": int(
                    item.sales_order_item_id
                ),
                "return_date": return_date,
                "returned_quantity": (
                    returned_quantity
                ),
                "restocked_quantity": (
                    restocked_quantity
                ),
                "rework_quantity": (
                    rework_quantity
                ),
                "scrapped_quantity": (
                    scrapped_quantity
                ),
                "unknown_disposition_quantity": (
                    unknown_quantity
                ),
                "refund_unit_amount_brl": round(
                    refund_unit_amount,
                    4,
                ),
                "return_freight_cost_brl": round(
                    return_freight,
                    4,
                ),
                "return_processing_cost_brl": round(
                    processing_cost,
                    4,
                ),
                "return_reason_code": str(
                    context.rng.choice(
                        RETURN_REASON_CODES
                    )
                ),
                "return_status": (
                    return_status
                ),
                "created_at": record_timestamp,
                "updated_at": record_timestamp,
            }
        )

    return pd.DataFrame(rows)


def generate_lot_allocations(
    context: RandomContext,
    invoiced_items: pd.DataFrame,
    manufacturing_tables: dict[str, pd.DataFrame],
    shipment_lookup: dict[int, dict[str, object]],
) -> pd.DataFrame:
    """Allocate the configured share of invoiced items to production lots."""

    production_lots = manufacturing_tables[
        "production_lots"
    ]
    production_orders = manufacturing_tables[
        "production_orders"
    ]

    lot_catalog = (
        production_lots.merge(
            production_orders[
                [
                    "production_order_id",
                    "product_id",
                ]
            ],
            on="production_order_id",
            how="inner",
            validate="one_to_one",
        )
        .loc[
            production_lots[
                "released_date"
            ].notna()
            & production_lots[
                "good_quantity"
            ].gt(0)
        ]
        .sort_values(
            [
                "product_id",
                "released_date",
                "production_lot_id",
            ]
        )
    )

    lots_by_product: dict[
        int,
        list[dict[str, object]],
    ] = {}

    for product_id, product_lots in (
        lot_catalog.groupby("product_id")
    ):
        lots_by_product[
            int(product_id)
        ] = [
            {
                "production_lot_id": int(
                    lot.production_lot_id
                ),
                "released_date": (
                    lot.released_date
                ),
                "remaining_quantity": float(
                    lot.good_quantity
                ),
            }
            for lot in product_lots.itertuples(
                index=False
            )
        ]

    allocation_dates = {
        sales_order_id: shipment[
            "shipment_date"
        ]
        for sales_order_id, shipment in (
            shipment_lookup.items()
        )
    }

    candidates = invoiced_items.copy()
    candidates["allocation_date"] = (
        candidates["sales_order_id"].map(
            allocation_dates
        )
    )

    first_release_by_product = (
        lot_catalog.groupby("product_id")[
            "released_date"
        ].min()
    )

    candidates["first_release_date"] = (
        candidates["product_id"].map(
            first_release_by_product
        )
    )

    candidates = candidates.loc[
        candidates[
            "first_release_date"
        ].notna()
        & candidates[
            "allocation_date"
        ].ge(
            candidates[
                "first_release_date"
            ]
        )
    ]

    target_item_count = round(
        len(invoiced_items)
        * GENERATION_CONFIG.traceability_target_rate
    )

    if target_item_count > len(candidates):
        raise ValueError(
            "There are not enough eligible sales items "
            "to reach the traceability target."
        )

    selected_positions = context.rng.choice(
        len(candidates),
        size=target_item_count,
        replace=False,
    )

    selected_items = (
        candidates.iloc[selected_positions]
        .sort_values(
            [
                "allocation_date",
                "sales_order_item_id",
            ]
        )
    )

    rows = []
    allocation_id = 1

    for item in selected_items.itertuples(
        index=False
    ):
        product_id = int(item.product_id)
        required_quantity = float(
            item.invoiced_quantity
        )
        allocation_date = (
            item.allocation_date
        )

        eligible_lots = [
            lot
            for lot in lots_by_product.get(
                product_id,
                [],
            )
            if (
                lot["released_date"]
                <= allocation_date
                and lot[
                    "remaining_quantity"
                ]
                > 0
            )
        ]

        available_quantity = sum(
            float(
                lot["remaining_quantity"]
            )
            for lot in eligible_lots
        )

        if available_quantity < required_quantity:
            continue

        quantity_to_allocate = (
            required_quantity
        )

        for lot in eligible_lots:
            if quantity_to_allocate <= 0:
                break

            allocated_quantity = min(
                quantity_to_allocate,
                float(
                    lot[
                        "remaining_quantity"
                    ]
                ),
            )

            allocated_at = business_datetime(
                allocation_date,
                13,
            )

            allocation_method = (
                context.weighted_choice(
                    [
                        "DIRECT_TRACE",
                        "WAREHOUSE_ALLOCATION",
                        "MANUAL_ADJUSTMENT",
                    ],
                    [0.75, 0.22, 0.03],
                )
            )

            rows.append(
                {
                    "sales_lot_allocation_id": (
                        allocation_id
                    ),
                    "sales_order_item_id": int(
                        item.sales_order_item_id
                    ),
                    "production_lot_id": int(
                        lot[
                            "production_lot_id"
                        ]
                    ),
                    "allocated_quantity": round(
                        allocated_quantity,
                        6,
                    ),
                    "allocation_method": (
                        allocation_method
                    ),
                    "allocated_at": (
                        allocated_at
                    ),
                    "created_at": (
                        allocated_at
                    ),
                    "updated_at": (
                        allocated_at
                    ),
                }
            )

            lot["remaining_quantity"] = (
                float(
                    lot[
                        "remaining_quantity"
                    ]
                )
                - allocated_quantity
            )
            quantity_to_allocate -= (
                allocated_quantity
            )
            allocation_id += 1

    return pd.DataFrame(rows)


def generate_fulfillment_and_traceability(
    context: RandomContext,
    industrial_tables: dict[str, pd.DataFrame],
    commercial_tables: dict[str, pd.DataFrame],
    manufacturing_tables: dict[str, pd.DataFrame],
    sales_tables: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """Generate all post-sale fulfillment tables."""

    invoiced_items = (
        build_invoiced_item_catalog(
            industrial_tables,
            commercial_tables,
            sales_tables,
        )
    )

    (
        shipments,
        shipment_items,
        shipment_freight_costs,
        shipment_lookup,
    ) = generate_shipments(
        context,
        invoiced_items,
    )

    (
        sales_commissions,
        sales_variable_expenses,
    ) = generate_sales_expenses(
        invoiced_items
    )

    sales_returns = generate_sales_returns(
        context,
        invoiced_items,
    )

    sales_lot_allocations = (
        generate_lot_allocations(
            context,
            invoiced_items,
            manufacturing_tables,
            shipment_lookup,
        )
    )

    return {
        "shipments": shipments,
        "shipment_items": shipment_items,
        "shipment_freight_costs": (
            shipment_freight_costs
        ),
        "sales_commissions": (
            sales_commissions
        ),
        "sales_variable_expenses": (
            sales_variable_expenses
        ),
        "sales_returns": sales_returns,
        "sales_lot_allocations": (
            sales_lot_allocations
        ),
    }


def main() -> None:
    """Generate fulfillment data and print row counts."""

    context = RandomContext()

    industrial_tables = (
        generate_industrial_master_data(context)
    )
    commercial_tables = (
        generate_commercial_master_data(context)
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
    sales_tables = generate_pricing_and_sales(
        context,
        industrial_tables,
        commercial_tables,
        costing_tables,
    )

    tables = (
        generate_fulfillment_and_traceability(
            context,
            industrial_tables,
            commercial_tables,
            manufacturing_tables,
            sales_tables,
        )
    )

    for table_name, dataframe in tables.items():
        print(f"{table_name}: {len(dataframe)} rows")


if __name__ == "__main__":
    main()