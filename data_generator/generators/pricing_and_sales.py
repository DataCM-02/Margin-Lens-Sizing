"""Generate deterministic pricing policies and sales transactions."""

from datetime import date, timedelta

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
from data_generator.random_context import RandomContext

FAMILY_MARKUP = {
    "CTRL": 1.75,
    "IOT": 1.85,
    "ENERGY": 1.70,
}


SALES_QUANTITY_RANGES = {
    "CTRL": (1, 12),
    "IOT": (1, 15),
    "ENERGY": (1, 8),
}


SEGMENT_DISCOUNT_BASE = {
    "STRATEGIC": 0.08,
    "DISTRIBUTOR": 0.10,
    "SYSTEM_INTEGRATOR": 0.07,
    "INDUSTRIAL_END_USER": 0.05,
}


def generate_price_lists() -> pd.DataFrame:
    """Generate the active BRL price list."""

    created_at = business_datetime(
        date(2023, 12, 1),
        9,
    )

    return pd.DataFrame(
        [
            {
                "price_list_id": 1,
                "price_list_code": "BRL_STANDARD",
                "price_list_name": "Tabela padrão B2B em BRL",
                "currency_code": "BRL",
                "is_active": True,
                "created_at": created_at,
                "updated_at": created_at,
            }
        ]
    )


def calculate_product_standard_cost(
    product_id: int,
    year: int,
    costing_tables: dict[str, pd.DataFrame],
) -> float:
    """Calculate standard product cost from BOM and conversion."""

    bill_of_materials = costing_tables[
        "bill_of_materials"
    ]
    bom_items = costing_tables[
        "bill_of_material_items"
    ]
    component_costs = costing_tables[
        "component_standard_cost_history"
    ]
    conversion_costs = costing_tables[
        "standard_conversion_costs"
    ]

    bom_id = int(
        bill_of_materials.loc[
            bill_of_materials["product_id"].eq(
                product_id
            )
            & bill_of_materials["bom_status"].eq(
                "ACTIVE"
            ),
            "bom_id",
        ].iloc[0]
    )

    product_bom_items = bom_items.loc[
        bom_items["bom_id"].eq(bom_id)
    ]

    material_cost = 0.0

    for bom_item in product_bom_items.itertuples(
        index=False
    ):
        component_cost = float(
            component_costs.loc[
                component_costs["component_id"].eq(
                    int(bom_item.component_id)
                )
                & component_costs["valid_from"].eq(
                    date(year, 1, 1)
                ),
                "standard_unit_cost_brl",
            ].iloc[0]
        )

        material_cost += (
            float(
                bom_item.base_quantity_per_unit
            )
            * (
                1
                + float(
                    bom_item.standard_scrap_rate
                )
            )
            * component_cost
        )

    conversion = conversion_costs.loc[
        conversion_costs["product_id"].eq(
            product_id
        )
        & conversion_costs["valid_from"].eq(
            date(year, 1, 1)
        )
    ].iloc[0]

    conversion_cost = (
        float(
            conversion[
                "standard_labor_hours_per_unit"
            ]
        )
        * float(
            conversion[
                "labor_rate_per_hour_brl"
            ]
        )
        + float(
            conversion[
                "standard_machine_hours_per_unit"
            ]
        )
        * float(
            conversion[
                "machine_rate_per_hour_brl"
            ]
        )
        + float(
            conversion[
                "overhead_cost_per_unit_brl"
            ]
        )
    )

    return material_cost + conversion_cost


def generate_price_list_items(
    industrial_tables: dict[str, pd.DataFrame],
    costing_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Generate annual product list prices."""

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

    rows = []
    price_list_item_id = 1
    price_2024_by_product = {}

    for product in product_catalog.itertuples(
        index=False
    ):
        standard_cost_2024 = (
            calculate_product_standard_cost(
                int(product.product_id),
                2024,
                costing_tables,
            )
        )

        list_price_2024 = round(
            standard_cost_2024
            * FAMILY_MARKUP[
                product.family_code
            ],
            4,
        )

        price_2024_by_product[
            int(product.product_id)
        ] = list_price_2024

        periods = [
            {
                "year": 2024,
                "valid_to": date(2024, 12, 31),
                "price": list_price_2024,
            },
            {
                "year": 2025,
                "valid_to": None,
                # Price increases only 7%, allowing
                # imported-cost pressure to reduce margin.
                "price": round(
                    list_price_2024 * 1.07,
                    4,
                ),
            },
        ]

        for period in periods:
            valid_from = date(
                period["year"],
                1,
                1,
            )
            record_timestamp = (
                business_datetime(
                    date(
                        period["year"] - 1,
                        12,
                        15,
                    ),
                    9,
                )
            )

            rows.append(
                {
                    "price_list_item_id": (
                        price_list_item_id
                    ),
                    "price_list_id": 1,
                    "product_id": int(
                        product.product_id
                    ),
                    "valid_from": valid_from,
                    "valid_to": period["valid_to"],
                    "list_unit_price_brl": (
                        period["price"]
                    ),
                    "created_at": (
                        record_timestamp
                    ),
                    "updated_at": (
                        record_timestamp
                    ),
                }
            )

            price_list_item_id += 1

    return pd.DataFrame(rows)


def generate_discount_policies(
    industrial_tables: dict[str, pd.DataFrame],
    commercial_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Generate annual discount limits by commercial context."""

    segments = commercial_tables[
        "customer_segments"
    ]
    families = industrial_tables[
        "product_families"
    ]
    channels = commercial_tables[
        "sales_channels"
    ]

    rows = []
    policy_id = 1

    for segment in segments.itertuples(
        index=False
    ):
        for family in families.itertuples(
            index=False
        ):
            for channel in channels.itertuples(
                index=False
            ):
                for year in (2024, 2025):
                    automatic_limit = (
                        SEGMENT_DISCOUNT_BASE[
                            segment.segment_code
                        ]
                    )

                    if channel.channel_code == "PARTNER":
                        automatic_limit += 0.02
                    elif (
                        channel.channel_code
                        == "DIGITAL_B2B"
                    ):
                        automatic_limit -= 0.01

                    if family.family_code == "IOT":
                        automatic_limit += 0.01

                    if year == 2025:
                        automatic_limit += 0.01

                    automatic_limit = round(
                        max(
                            0.02,
                            automatic_limit,
                        ),
                        6,
                    )
                    manager_limit = round(
                        automatic_limit + 0.08,
                        6,
                    )

                    valid_from = date(
                        year,
                        1,
                        1,
                    )
                    record_timestamp = (
                        business_datetime(
                            date(
                                year - 1,
                                12,
                                15,
                            ),
                            10,
                        )
                    )

                    rows.append(
                        {
                            "discount_policy_id": (
                                policy_id
                            ),
                            "customer_segment_id": (
                                int(
                                    segment.customer_segment_id
                                )
                            ),
                            "product_family_id": (
                                int(
                                    family.product_family_id
                                )
                            ),
                            "sales_channel_id": (
                                int(
                                    channel.sales_channel_id
                                )
                            ),
                            "valid_from": valid_from,
                            "valid_to": (
                                date(2024, 12, 31)
                                if year == 2024
                                else None
                            ),
                            "automatic_discount_limit_rate": (
                                automatic_limit
                            ),
                            "manager_approval_limit_rate": (
                                manager_limit
                            ),
                            "created_at": (
                                record_timestamp
                            ),
                            "updated_at": (
                                record_timestamp
                            ),
                        }
                    )

                    policy_id += 1

    return pd.DataFrame(rows)


def generate_discount_exceptions(
    industrial_tables: dict[str, pd.DataFrame],
    commercial_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Generate escalating exceptions for the scenario customer."""

    customers = commercial_tables["customers"]
    families = industrial_tables[
        "product_families"
    ]

    scenario_customer_id = int(
        customers.loc[
            customers["customer_code"].eq(
                GENERATION_CONFIG.discount_customer_scenario_code
            ),
            "customer_id",
        ].iloc[0]
    )

    periods = [
        {
            "code": "2024H1",
            "valid_from": date(2024, 1, 1),
            "valid_to": date(2024, 6, 30),
            "rate": 0.12,
            "role": "SALES_MANAGER",
        },
        {
            "code": "2024H2",
            "valid_from": date(2024, 7, 1),
            "valid_to": date(2024, 12, 31),
            "rate": 0.15,
            "role": "SALES_MANAGER",
        },
        {
            "code": "2025H1",
            "valid_from": date(2025, 1, 1),
            "valid_to": date(2025, 6, 30),
            "rate": 0.19,
            "role": "COMMERCIAL_DIRECTOR",
        },
        {
            "code": "2025H2",
            "valid_from": date(2025, 7, 1),
            "valid_to": date(2025, 12, 31),
            "rate": 0.24,
            "role": "COMMERCIAL_DIRECTOR",
        },
    ]

    rows = []
    exception_id = 1

    for family in families.itertuples(
        index=False
    ):
        for period in periods:
            created_at = business_datetime(
                period["valid_from"]
                - timedelta(days=10),
                10,
            )

            rows.append(
                {
                    "discount_exception_id": (
                        exception_id
                    ),
                    "approval_code": (
                        f"EXC-CUS0007-"
                        f"{family.family_code}-"
                        f"{period['code']}"
                    ),
                    "customer_id": (
                        scenario_customer_id
                    ),
                    "product_family_id": (
                        int(
                            family.product_family_id
                        )
                    ),
                    "valid_from": (
                        period["valid_from"]
                    ),
                    "valid_to": (
                        period["valid_to"]
                    ),
                    "approved_discount_rate": (
                        period["rate"]
                    ),
                    "approved_by_role": (
                        period["role"]
                    ),
                    "approval_reason": (
                        "Condição comercial excepcional "
                        "para retenção de conta estratégica."
                    ),
                    "created_at": created_at,
                    "updated_at": created_at,
                }
            )

            exception_id += 1

    return pd.DataFrame(rows)


def select_sales_channel_id(
    context: RandomContext,
    segment_code: str,
    channel_id_by_code: dict[str, int],
) -> int:
    """Select a channel according to customer segment."""

    if segment_code == "STRATEGIC":
        codes = [
            "DIRECT",
            "DIGITAL_B2B",
            "PARTNER",
        ]
        probabilities = [0.70, 0.20, 0.10]
    elif segment_code == "DISTRIBUTOR":
        codes = [
            "PARTNER",
            "DIRECT",
            "DIGITAL_B2B",
        ]
        probabilities = [0.75, 0.15, 0.10]
    elif segment_code == "SYSTEM_INTEGRATOR":
        codes = [
            "DIRECT",
            "PARTNER",
            "DIGITAL_B2B",
        ]
        probabilities = [0.55, 0.35, 0.10]
    else:
        codes = [
            "DIRECT",
            "DIGITAL_B2B",
            "PARTNER",
        ]
        probabilities = [0.60, 0.25, 0.15]

    channel_code = context.weighted_choice(
        codes,
        probabilities,
    )

    return channel_id_by_code[channel_code]


def managerial_tax_rate(
    state_code: str,
    sales_region: str,
) -> float:
    """Return a simplified managerial sales-tax rate."""

    if state_code == "SP":
        return 0.18

    if sales_region in {
        "SOUTHEAST",
        "SOUTH",
    }:
        return 0.12

    return 0.07


def generate_sales_transactions(
    context: RandomContext,
    industrial_tables: dict[str, pd.DataFrame],
    commercial_tables: dict[str, pd.DataFrame],
    pricing_tables: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate sales orders and their items."""

    products = industrial_tables["products"]
    families = industrial_tables[
        "product_families"
    ]
    customers = commercial_tables["customers"]
    segments = commercial_tables[
        "customer_segments"
    ]
    salespeople = commercial_tables["salespeople"]
    channels = commercial_tables[
        "sales_channels"
    ]

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

    customer_catalog = customers.merge(
        segments[
            [
                "customer_segment_id",
                "segment_code",
            ]
        ],
        on="customer_segment_id",
        how="left",
        validate="many_to_one",
    )

    channel_id_by_code = dict(
        zip(
            channels["channel_code"],
            channels[
                "sales_channel_id"
            ].astype(int),
            strict=True,
        )
    )

    price_lookup = {
        (
            int(row.product_id),
            row.valid_from.year,
        ): float(row.list_unit_price_brl)
        for row in pricing_tables[
            "price_list_items"
        ].itertuples(index=False)
    }

    policy_lookup = {
        (
            int(row["customer_segment_id"]),
            int(row["product_family_id"]),
            int(row["sales_channel_id"]),
            row["valid_from"].year,
        ): row
        for row in pricing_tables[
            "discount_policies"
        ].to_dict(orient="records")
    }

    exceptions = pricing_tables[
        "approved_discount_exceptions"
    ]

    scenario_customer = customer_catalog.loc[
        customer_catalog["customer_code"].eq(
            GENERATION_CONFIG.discount_customer_scenario_code
        )
    ].iloc[0]
    scenario_customer_id = int(
        scenario_customer["customer_id"]
    )

    order_dates = sorted(
        context.random_date(
            GENERATION_CONFIG.start_date,
            GENERATION_CONFIG.end_date,
        )
        for _ in range(
            GENERATION_CONFIG.sales_order_count
        )
    )

    order_count = len(order_dates)

    open_ids = set(
        range(
            order_count - 59,
            order_count + 1,
        )
    )
    partial_ids = set(
        range(
            order_count - 119,
            order_count - 59,
        )
    )

    cancellation_count = round(
        order_count
        * GENERATION_CONFIG.cancellation_target_rate
    )

    cancellation_candidates = list(
        range(
            1,
            order_count - 119,
        )
    )

    cancelled_ids = {
        int(order_id)
        for order_id in context.rng.choice(
            cancellation_candidates,
            size=cancellation_count,
            replace=False,
        )
    }

    order_rows = []
    item_rows = []
    sales_order_item_id = 1

    for sales_order_id, order_date in enumerate(
        order_dates,
        start=1,
    ):
        eligible_customers = (
            customer_catalog.loc[
                customer_catalog[
                    "customer_since"
                ].le(order_date)
                & (
                    customer_catalog[
                        "inactive_date"
                    ].isna()
                    | customer_catalog[
                        "inactive_date"
                    ].ge(order_date)
                )
            ]
        )

        if sales_order_id % 33 == 0:
            customer = scenario_customer
        else:
            customer_position = int(
                context.rng.integers(
                    0,
                    len(eligible_customers),
                )
            )
            customer = (
                eligible_customers.iloc[
                    customer_position
                ]
            )

        customer_id = int(
            customer["customer_id"]
        )
        customer_segment_id = int(
            customer["customer_segment_id"]
        )
        segment_code = str(
            customer["segment_code"]
        )
        sales_region = str(
            customer["sales_region"]
        )

        eligible_salespeople = (
            salespeople.loc[
                salespeople[
                    "sales_region"
                ].eq(sales_region)
                & salespeople[
                    "hire_date"
                ].le(order_date)
                & (
                    salespeople[
                        "termination_date"
                    ].isna()
                    | salespeople[
                        "termination_date"
                    ].ge(order_date)
                )
            ]
        )

        if eligible_salespeople.empty:
            eligible_salespeople = (
                salespeople.loc[
                    salespeople[
                        "hire_date"
                    ].le(order_date)
                    & (
                        salespeople[
                            "termination_date"
                        ].isna()
                        | salespeople[
                            "termination_date"
                        ].ge(order_date)
                    )
                ]
            )

        salesperson_position = int(
            context.rng.integers(
                0,
                len(eligible_salespeople),
            )
        )
        salesperson_id = int(
            eligible_salespeople.iloc[
                salesperson_position
            ]["salesperson_id"]
        )

        sales_channel_id = (
            select_sales_channel_id(
                context,
                segment_code,
                channel_id_by_code,
            )
        )

        requested_delivery_date = (
            order_date
            + timedelta(
                days=int(
                    context.rng.integers(
                        5,
                        31,
                    )
                )
            )
        )

        if sales_order_id in cancelled_ids:
            order_status = "CANCELLED"
        elif sales_order_id in open_ids:
            order_status = "OPEN"
        elif sales_order_id in partial_ids:
            order_status = (
                "PARTIALLY_INVOICED"
            )
        else:
            order_status = "INVOICED"

        created_at = business_datetime(
            order_date,
            10,
        )
        order_updated_at = created_at

        item_count = int(
            context.rng.choice(
                [1, 2, 3],
                p=[0.45, 0.40, 0.15],
            )
        )

        product_positions = (
            context.rng.choice(
                len(product_catalog),
                size=item_count,
                replace=False,
            )
        )

        selected_products = (
            product_catalog.iloc[
                product_positions
            ]
        )

        for line_number, product in enumerate(
            selected_products.itertuples(
                index=False
            ),
            start=1,
        ):
            product_id = int(
                product.product_id
            )
            product_family_id = int(
                product.product_family_id
            )
            family_code = str(
                product.family_code
            )

            minimum_quantity, maximum_quantity = (
                SALES_QUANTITY_RANGES[
                    family_code
                ]
            )

            ordered_quantity = float(
                context.rng.integers(
                    minimum_quantity,
                    maximum_quantity + 1,
                )
            )

            list_unit_price = round(
                price_lookup[
                    (
                        product_id,
                        order_date.year,
                    )
                ],
                4,
            )

            policy = policy_lookup[
                (
                    customer_segment_id,
                    product_family_id,
                    sales_channel_id,
                    order_date.year,
                )
            ]

            discount_exception_id = None

            if (
                customer_id
                == scenario_customer_id
            ):
                exception = exceptions.loc[
                    exceptions[
                        "customer_id"
                    ].eq(customer_id)
                    & exceptions[
                        "product_family_id"
                    ].eq(product_family_id)
                    & exceptions[
                        "valid_from"
                    ].le(order_date)
                    & exceptions[
                        "valid_to"
                    ].ge(order_date)
                ].iloc[0]

                discount_exception_id = int(
                    exception[
                        "discount_exception_id"
                    ]
                )
                discount_rate = round(
                    float(
                        exception[
                            "approved_discount_rate"
                        ]
                    )
                    - float(
                        context.rng.uniform(
                            0.000,
                            0.006,
                        )
                    ),
                    6,
                )
            else:
                automatic_limit = float(
                    policy[
                        "automatic_discount_limit_rate"
                    ]
                )
                manager_limit = float(
                    policy[
                        "manager_approval_limit_rate"
                    ]
                )

                if (
                    float(context.rng.random())
                    < 0.15
                ):
                    discount_rate = float(
                        context.rng.uniform(
                            automatic_limit,
                            manager_limit,
                        )
                    )
                else:
                    discount_rate = float(
                        context.rng.uniform(
                            0.01,
                            automatic_limit * 0.90,
                        )
                    )

                discount_rate = round(
                    discount_rate,
                    6,
                )

            realized_unit_price = round(
                list_unit_price
                * (1 - discount_rate),
                4,
            )

            if order_status == "INVOICED":
                invoiced_quantity = (
                    ordered_quantity
                )
                item_status = "INVOICED"
            elif (
                order_status
                == "PARTIALLY_INVOICED"
            ):
                invoiced_quantity = round(
                    ordered_quantity
                    * float(
                        context.rng.uniform(
                            0.40,
                            0.80,
                        )
                    ),
                    6,
                )
                item_status = (
                    "PARTIALLY_INVOICED"
                )
            elif order_status == "CANCELLED":
                invoiced_quantity = 0.0
                item_status = "CANCELLED"
            else:
                invoiced_quantity = 0.0
                item_status = "OPEN"

            if invoiced_quantity > 0:
                invoice_date = max(
                    order_date,
                    min(
                        requested_delivery_date
                        + timedelta(
                            days=int(
                                context.rng.integers(
                                    -2,
                                    6,
                                )
                            )
                        ),
                        GENERATION_CONFIG.end_date,
                    ),
                )
                invoice_number = (
                    f"NF-{order_date.year}-"
                    f"{sales_order_id:06d}"
                )
                item_updated_at = (
                    business_datetime(
                        invoice_date,
                        16,
                    )
                )
                order_updated_at = max(
                    order_updated_at,
                    item_updated_at,
                )
            else:
                invoice_date = None
                invoice_number = None
                item_updated_at = created_at

            item_rows.append(
                {
                    "sales_order_item_id": (
                        sales_order_item_id
                    ),
                    "sales_order_id": (
                        sales_order_id
                    ),
                    "line_number": line_number,
                    "product_id": product_id,
                    "discount_exception_id": (
                        discount_exception_id
                    ),
                    "ordered_quantity": (
                        ordered_quantity
                    ),
                    "invoiced_quantity": (
                        invoiced_quantity
                    ),
                    "list_unit_price_brl": (
                        list_unit_price
                    ),
                    "discount_rate": (
                        discount_rate
                    ),
                    "realized_unit_price_brl": (
                        realized_unit_price
                    ),
                    "managerial_sales_tax_rate": (
                        managerial_tax_rate(
                            str(
                                customer[
                                    "state_code"
                                ]
                            ),
                            sales_region,
                        )
                    ),
                    "invoice_number": (
                        invoice_number
                    ),
                    "invoice_date": invoice_date,
                    "item_status": item_status,
                    "created_at": created_at,
                    "updated_at": (
                        item_updated_at
                    ),
                }
            )

            sales_order_item_id += 1

        order_rows.append(
            {
                "sales_order_id": (
                    sales_order_id
                ),
                "sales_order_number": (
                    f"SO-{order_date.year}-"
                    f"{sales_order_id:06d}"
                ),
                "customer_id": customer_id,
                "salesperson_id": (
                    salesperson_id
                ),
                "sales_channel_id": (
                    sales_channel_id
                ),
                "price_list_id": 1,
                "order_date": order_date,
                "requested_delivery_date": (
                    requested_delivery_date
                ),
                "order_status": (
                    order_status
                ),
                "created_at": created_at,
                "updated_at": (
                    order_updated_at
                ),
            }
        )

    return (
        pd.DataFrame(order_rows),
        pd.DataFrame(item_rows),
    )


def generate_pricing_and_sales(
    context: RandomContext,
    industrial_tables: dict[str, pd.DataFrame],
    commercial_tables: dict[str, pd.DataFrame],
    costing_tables: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """Generate pricing masters and sales transactions."""

    price_lists = generate_price_lists()

    price_list_items = (
        generate_price_list_items(
            industrial_tables,
            costing_tables,
        )
    )

    discount_policies = (
        generate_discount_policies(
            industrial_tables,
            commercial_tables,
        )
    )

    approved_discount_exceptions = (
        generate_discount_exceptions(
            industrial_tables,
            commercial_tables,
        )
    )

    pricing_tables = {
        "price_lists": price_lists,
        "price_list_items": (
            price_list_items
        ),
        "discount_policies": (
            discount_policies
        ),
        "approved_discount_exceptions": (
            approved_discount_exceptions
        ),
    }

    (
        sales_orders,
        sales_order_items,
    ) = generate_sales_transactions(
        context,
        industrial_tables,
        commercial_tables,
        pricing_tables,
    )

    return {
        **pricing_tables,
        "sales_orders": sales_orders,
        "sales_order_items": (
            sales_order_items
        ),
    }


def main() -> None:
    """Generate pricing and sales data and print row counts."""

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

    tables = generate_pricing_and_sales(
        context,
        industrial_tables,
        commercial_tables,
        costing_tables,
    )

    for table_name, dataframe in tables.items():
        print(f"{table_name}: {len(dataframe)} rows")


if __name__ == "__main__":
    main()