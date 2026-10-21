"""Generate deterministic exchange-rate, costing, and BOM data."""

from datetime import date, datetime, time
from math import sin, tau

import pandas as pd

from data_generator.config import GENERATION_CONFIG
from data_generator.generators.industrial_master_data import (
    generate_industrial_master_data,
)
from data_generator.random_context import BUSINESS_TIMEZONE, RandomContext

CATEGORY_BASE_COST_BRL = {
    "PCB": 110.00,
    "MCU": 78.00,
    "COMM": 96.00,
    "SENSOR": 42.00,
    "POWER": 58.00,
    "CONN": 5.50,
    "ENC": 31.00,
    "DISPLAY": 64.00,
}


BOM_CATEGORY_QUANTITIES = {
    "CTRL": {
        "PCB": 1,
        "MCU": 1,
        "COMM": 1,
        "SENSOR": 2,
        "POWER": 1,
        "CONN": 3,
        "ENC": 1,
        "DISPLAY": 1,
    },
    "IOT": {
        "PCB": 1,
        "MCU": 1,
        "COMM": 2,
        "SENSOR": 2,
        "POWER": 1,
        "CONN": 2,
        "ENC": 1,
    },
    "ENERGY": {
        "PCB": 1,
        "MCU": 1,
        "COMM": 1,
        "SENSOR": 3,
        "POWER": 2,
        "CONN": 3,
        "ENC": 1,
        "DISPLAY": 1,
    },
}


ITEM_QUANTITY_OPTIONS = {
    "PCB": [1.0],
    "MCU": [1.0],
    "COMM": [1.0],
    "SENSOR": [1.0, 2.0, 3.0],
    "POWER": [1.0, 2.0],
    "CONN": [2.0, 4.0, 6.0],
    "ENC": [1.0],
    "DISPLAY": [1.0],
}


STANDARD_SCRAP_RATE = {
    "PCB": 0.012,
    "MCU": 0.008,
    "COMM": 0.010,
    "SENSOR": 0.015,
    "POWER": 0.012,
    "CONN": 0.020,
    "ENC": 0.025,
    "DISPLAY": 0.010,
}


CONVERSION_BASE = {
    "CTRL": {
        "labor_hours": 0.45,
        "machine_hours": 0.30,
        "overhead": 38.00,
    },
    "IOT": {
        "labor_hours": 0.60,
        "machine_hours": 0.45,
        "overhead": 52.00,
    },
    "ENERGY": {
        "labor_hours": 0.75,
        "machine_hours": 0.55,
        "overhead": 65.00,
    },
}


def business_datetime(
    value: date,
    hour: int,
) -> datetime:
    """Convert a date to a timezone-aware business timestamp."""

    return datetime.combine(
        value,
        time(hour, 0),
        tzinfo=BUSINESS_TIMEZONE,
    )


def generate_exchange_rates(
    context: RandomContext,
) -> pd.DataFrame:
    """Generate daily BRL, USD, and EUR exchange rates."""

    calendar = pd.date_range(
        GENERATION_CONFIG.start_date,
        GENERATION_CONFIG.end_date,
        freq="D",
    )

    rows = []
    total_intervals = max(len(calendar) - 1, 1)

    for index, timestamp in enumerate(calendar):
        rate_date = timestamp.date()
        progress = index / total_intervals

        usd_trend = 4.85 + (6.15 - 4.85) * progress
        eur_trend = 5.35 + (6.60 - 5.35) * progress

        seasonal_wave = sin(tau * progress * 4)

        usd_rate = (
            usd_trend
            + 0.08 * seasonal_wave
            + float(context.rng.normal(0, 0.025))
        )
        eur_rate = (
            eur_trend
            + 0.10 * seasonal_wave
            + float(context.rng.normal(0, 0.030))
        )

        created_at = business_datetime(rate_date, 19)

        rows.extend(
            [
                {
                    "rate_date": rate_date,
                    "currency_code": "BRL",
                    "rate_to_brl": 1.000000,
                    "created_at": created_at,
                },
                {
                    "rate_date": rate_date,
                    "currency_code": "USD",
                    "rate_to_brl": round(usd_rate, 6),
                    "created_at": created_at,
                },
                {
                    "rate_date": rate_date,
                    "currency_code": "EUR",
                    "rate_to_brl": round(eur_rate, 6),
                    "created_at": created_at,
                },
            ]
        )

    return pd.DataFrame(rows)


def generate_component_cost_tables(
    context: RandomContext,
    industrial_tables: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate component standard costs and opening moving-average costs."""

    components = industrial_tables["components"]
    categories = industrial_tables["component_categories"]

    component_catalog = components.merge(
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

    standard_rows = []
    opening_rows = []

    standard_cost_id = 1
    opening_cost_id = 1

    for component in component_catalog.itertuples(index=False):
        category_base_cost = CATEGORY_BASE_COST_BRL[
            component.category_code
        ]

        variation_factor = float(
            context.rng.uniform(0.82, 1.18)
        )
        sourcing_factor = (
            1.10
            if component.sourcing_type == "IMPORTED"
            else 1.00
        )

        standard_cost_2024 = round(
            category_base_cost
            * variation_factor
            * sourcing_factor,
            6,
        )

        if (
            component.component_code
            == GENERATION_CONFIG.imported_component_scenario_code
        ):
            standard_cost_2024 = 128.000000
            adjustment_2025 = 1.18
        elif component.sourcing_type == "IMPORTED":
            adjustment_2025 = float(
                context.rng.uniform(1.08, 1.14)
            )
        else:
            adjustment_2025 = float(
                context.rng.uniform(1.04, 1.09)
            )

        standard_cost_2025 = round(
            standard_cost_2024 * adjustment_2025,
            6,
        )

        periods = [
            {
                "valid_from": date(2024, 1, 1),
                "valid_to": date(2024, 12, 31),
                "unit_cost": standard_cost_2024,
                "revision_reason": "INITIAL_2024_STANDARD",
                "record_date": date(2023, 12, 15),
            },
            {
                "valid_from": date(2025, 1, 1),
                "valid_to": None,
                "unit_cost": standard_cost_2025,
                "revision_reason": (
                    "FX_AND_SUPPLIER_INCREASE"
                    if (
                        component.component_code
                        == GENERATION_CONFIG.imported_component_scenario_code
                    )
                    else "ANNUAL_2025_REVISION"
                ),
                "record_date": date(2024, 12, 15),
            },
        ]

        for period in periods:
            record_timestamp = business_datetime(
                period["record_date"],
                9,
            )

            standard_rows.append(
                {
                    "standard_cost_id": standard_cost_id,
                    "component_id": int(component.component_id),
                    "plant_id": 1,
                    "valid_from": period["valid_from"],
                    "valid_to": period["valid_to"],
                    "standard_unit_cost_brl": period["unit_cost"],
                    "revision_reason": period["revision_reason"],
                    "created_at": record_timestamp,
                    "updated_at": record_timestamp,
                }
            )

            standard_cost_id += 1

        opening_average_cost = round(
            standard_cost_2024
            * float(context.rng.uniform(0.97, 1.03)),
            6,
        )

        opening_timestamp = business_datetime(
            date(2024, 1, 1),
            7,
        )

        opening_rows.append(
            {
                "component_cost_id": opening_cost_id,
                "component_id": int(component.component_id),
                "plant_id": 1,
                "valid_from": date(2024, 1, 1),
                "valid_to": None,
                "moving_average_unit_cost_brl": opening_average_cost,
                "cost_source": "OPENING_BALANCE",
                "source_reference": "OPENING-2024",
                "created_at": opening_timestamp,
                "updated_at": opening_timestamp,
            }
        )

        opening_cost_id += 1

    return (
        pd.DataFrame(standard_rows),
        pd.DataFrame(opening_rows),
    )


def select_components_for_bom(
    context: RandomContext,
    family_code: str,
    component_catalog: pd.DataFrame,
) -> list[int]:
    """Select a valid component combination for one product BOM."""

    category_requirements = BOM_CATEGORY_QUANTITIES[
        family_code
    ]

    selected_component_ids = []

    scenario_matches = component_catalog.loc[
        component_catalog["component_code"].eq(
            GENERATION_CONFIG.imported_component_scenario_code
        )
    ]

    if scenario_matches.empty:
        raise ValueError(
            "The imported-component scenario was not found."
        )

    scenario_component_id = int(
        scenario_matches.iloc[0]["component_id"]
    )

    for category_code, required_count in (
        category_requirements.items()
    ):
        candidates = (
            component_catalog.loc[
                component_catalog["category_code"].eq(
                    category_code
                ),
                "component_id",
            ]
            .astype(int)
            .tolist()
        )

        mandatory_ids = []

        if family_code == "IOT" and category_code == "COMM":
            mandatory_ids = [scenario_component_id]

        available_candidates = [
            component_id
            for component_id in candidates
            if component_id not in mandatory_ids
        ]

        random_count = required_count - len(mandatory_ids)

        random_selection = context.rng.choice(
            available_candidates,
            size=random_count,
            replace=False,
        )

        selected_component_ids.extend(mandatory_ids)
        selected_component_ids.extend(
            int(component_id)
            for component_id in random_selection
        )

    return selected_component_ids


def generate_bom_tables(
    context: RandomContext,
    industrial_tables: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate one active engineering BOM for each product."""

    products = industrial_tables["products"]
    product_families = industrial_tables["product_families"]
    components = industrial_tables["components"]
    categories = industrial_tables["component_categories"]

    product_catalog = products.merge(
        product_families[
            [
                "product_family_id",
                "family_code",
            ]
        ],
        on="product_family_id",
        how="left",
        validate="many_to_one",
    )

    component_catalog = components.merge(
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

    component_category_lookup = dict(
        zip(
            component_catalog["component_id"].astype(int),
            component_catalog["category_code"],
            strict=True,
        )
    )

    bom_rows = []
    item_rows = []

    bom_item_id = 1
    record_timestamp = business_datetime(
        date(2023, 12, 15),
        10,
    )

    for bom_id, product in enumerate(
        product_catalog.itertuples(index=False),
        start=1,
    ):
        bom_rows.append(
            {
                "bom_id": bom_id,
                "product_id": int(product.product_id),
                "bom_version": "V1.0",
                "valid_from": date(2024, 1, 1),
                "valid_to": None,
                "bom_status": "ACTIVE",
                "created_at": record_timestamp,
                "updated_at": record_timestamp,
            }
        )

        selected_components = select_components_for_bom(
            context,
            product.family_code,
            component_catalog,
        )

        for position, component_id in enumerate(
            selected_components,
            start=1,
        ):
            category_code = component_category_lookup[
                component_id
            ]

            quantity = float(
                context.rng.choice(
                    ITEM_QUANTITY_OPTIONS[category_code]
                )
            )

            scrap_rate = round(
                STANDARD_SCRAP_RATE[category_code]
                + float(context.rng.uniform(0, 0.004)),
                6,
            )

            item_rows.append(
                {
                    "bom_item_id": bom_item_id,
                    "bom_id": bom_id,
                    "component_id": component_id,
                    "item_sequence": position * 10,
                    "base_quantity_per_unit": round(
                        quantity,
                        6,
                    ),
                    "standard_scrap_rate": scrap_rate,
                    "created_at": record_timestamp,
                    "updated_at": record_timestamp,
                }
            )

            bom_item_id += 1

    return (
        pd.DataFrame(bom_rows),
        pd.DataFrame(item_rows),
    )


def generate_standard_conversion_costs(
    context: RandomContext,
    industrial_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Generate annual standard conversion costs per product."""

    products = industrial_tables["products"]
    product_families = industrial_tables["product_families"]

    product_catalog = products.merge(
        product_families[
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
    conversion_cost_id = 1

    for product in product_catalog.itertuples(index=False):
        base = CONVERSION_BASE[product.family_code]

        product_factor = float(
            context.rng.uniform(0.92, 1.08)
        )

        for year in (2024, 2025):
            annual_factor = 1.00 if year == 2024 else 1.08

            valid_from = date(year, 1, 1)
            valid_to = (
                date(2024, 12, 31)
                if year == 2024
                else None
            )

            record_date = date(year - 1, 12, 15)
            record_timestamp = business_datetime(
                record_date,
                10,
            )

            rows.append(
                {
                    "standard_conversion_cost_id": (
                        conversion_cost_id
                    ),
                    "product_id": int(product.product_id),
                    "plant_id": 1,
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                    "standard_labor_hours_per_unit": round(
                        base["labor_hours"] * product_factor,
                        6,
                    ),
                    "standard_machine_hours_per_unit": round(
                        base["machine_hours"] * product_factor,
                        6,
                    ),
                    "labor_rate_per_hour_brl": round(
                        72.00 * annual_factor,
                        4,
                    ),
                    "machine_rate_per_hour_brl": round(
                        110.00 * annual_factor,
                        4,
                    ),
                    "overhead_cost_per_unit_brl": round(
                        base["overhead"]
                        * product_factor
                        * annual_factor,
                        4,
                    ),
                    "created_at": record_timestamp,
                    "updated_at": record_timestamp,
                }
            )

            conversion_cost_id += 1

    return pd.DataFrame(rows)


def generate_costing_and_bom(
    context: RandomContext,
    industrial_tables: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """Generate costing, currency, and BOM source tables."""

    exchange_rates = generate_exchange_rates(context)

    (
        component_standard_cost_history,
        component_cost_history,
    ) = generate_component_cost_tables(
        context,
        industrial_tables,
    )

    (
        bill_of_materials,
        bill_of_material_items,
    ) = generate_bom_tables(
        context,
        industrial_tables,
    )

    standard_conversion_costs = (
        generate_standard_conversion_costs(
            context,
            industrial_tables,
        )
    )

    return {
        "exchange_rates": exchange_rates,
        "component_standard_cost_history": (
            component_standard_cost_history
        ),
        "component_cost_history": component_cost_history,
        "bill_of_materials": bill_of_materials,
        "bill_of_material_items": bill_of_material_items,
        "standard_conversion_costs": standard_conversion_costs,
    }


def main() -> None:
    """Generate the tables in memory and print their row counts."""

    context = RandomContext()

    industrial_tables = generate_industrial_master_data(
        context
    )

    tables = generate_costing_and_bom(
        context,
        industrial_tables,
    )

    for table_name, dataframe in tables.items():
        print(f"{table_name}: {len(dataframe)} rows")


if __name__ == "__main__":
    main()