"""Generate deterministic manufacturing transactions."""

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
from data_generator.generators.procurement_transactions import (
    generate_procurement_transactions,
)
from data_generator.random_context import RandomContext

FAMILY_LINE_CODE = {
    "CTRL": "LINE-CTRL",
    "IOT": "LINE-IOT",
    "ENERGY": "LINE-ENE",
}


PLANNED_QUANTITY_RANGES = {
    "CTRL": (80, 220),
    "IOT": (100, 300),
    "ENERGY": (60, 180),
}


def normalize_date(value: object) -> date | None:
    """Convert pandas date-like values to Python dates."""

    if value is None or pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        return value.date()

    if isinstance(value, date):
        return value

    raise TypeError(f"Unsupported date value: {value!r}")


def build_component_cost_lookup(
    component_cost_history: pd.DataFrame,
) -> dict[int, list[dict[str, object]]]:
    """Index component costs by component and validity period."""

    lookup: dict[int, list[dict[str, object]]] = {}

    for component_id, group in (
        component_cost_history.groupby("component_id")
    ):
        entries = []

        for row in group.sort_values(
            "valid_from"
        ).itertuples(index=False):
            entries.append(
                {
                    "component_cost_id": int(
                        row.component_cost_id
                    ),
                    "valid_from": normalize_date(
                        row.valid_from
                    ),
                    "valid_to": normalize_date(
                        row.valid_to
                    ),
                    "unit_cost": float(
                        row.moving_average_unit_cost_brl
                    ),
                }
            )

        lookup[int(component_id)] = entries

    return lookup


def find_component_cost(
    cost_lookup: dict[int, list[dict[str, object]]],
    component_id: int,
    movement_date: date,
) -> tuple[int, float]:
    """Find the component cost valid on a movement date."""

    for entry in reversed(cost_lookup[component_id]):
        valid_from = entry["valid_from"]
        valid_to = entry["valid_to"]

        if (
            isinstance(valid_from, date)
            and valid_from <= movement_date
            and (
                valid_to is None
                or (
                    isinstance(valid_to, date)
                    and movement_date <= valid_to
                )
            )
        ):
            return (
                int(entry["component_cost_id"]),
                float(entry["unit_cost"]),
            )

    raise ValueError(
        "No valid component cost was found for "
        f"component {component_id} on {movement_date}."
    )


def generate_production_schedule(
    context: RandomContext,
    product_catalog: pd.DataFrame,
) -> list[dict[str, object]]:
    """Create two production orders per product and month."""

    months = pd.period_range(
        GENERATION_CONFIG.start_date,
        GENERATION_CONFIG.end_date,
        freq="M",
    )

    schedule = []

    for month in months:
        for product in product_catalog.itertuples(
            index=False
        ):
            for cycle_number, base_day in (
                (1, 5),
                (2, 18),
            ):
                day_adjustment = int(
                    context.rng.integers(-2, 3)
                )

                planned_day = max(
                    1,
                    min(
                        month.days_in_month,
                        base_day + day_adjustment,
                    ),
                )

                schedule.append(
                    {
                        "product_id": int(
                            product.product_id
                        ),
                        "product_code": str(
                            product.product_code
                        ),
                        "family_code": str(
                            product.family_code
                        ),
                        "cycle_number": cycle_number,
                        "planned_start_date": date(
                            month.year,
                            month.month,
                            planned_day,
                        ),
                    }
                )

    schedule.sort(
        key=lambda row: (
            row["planned_start_date"],
            row["product_id"],
            row["cycle_number"],
        )
    )

    if (
        len(schedule)
        != GENERATION_CONFIG.production_order_count
    ):
        raise ValueError(
            "Generated production schedule does not match "
            "the configured production-order count."
        )

    return schedule


def generate_manufacturing_transactions(
    context: RandomContext,
    industrial_tables: dict[str, pd.DataFrame],
    costing_tables: dict[str, pd.DataFrame],
    procurement_tables: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """Generate production orders, lots, consumption, and quality."""

    products = industrial_tables["products"]
    product_families = industrial_tables[
        "product_families"
    ]
    production_lines = industrial_tables[
        "production_lines"
    ]

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

    line_id_by_code = dict(
        zip(
            production_lines["line_code"],
            production_lines[
                "production_line_id"
            ].astype(int),
            strict=True,
        )
    )

    bom_by_product = (
        costing_tables["bill_of_materials"]
        .loc[
            costing_tables[
                "bill_of_materials"
            ]["bom_status"].eq("ACTIVE")
        ]
        .set_index("product_id")["bom_id"]
        .astype(int)
        .to_dict()
    )

    bom_items_by_bom = {
        int(bom_id): group.sort_values(
            "item_sequence"
        ).copy()
        for bom_id, group in (
            costing_tables[
                "bill_of_material_items"
            ].groupby("bom_id")
        )
    }

    conversion_costs = costing_tables[
        "standard_conversion_costs"
    ]

    conversion_lookup = {
        (
            int(row["product_id"]),
            normalize_date(row["valid_from"]).year,
        ): row
        for row in conversion_costs.to_dict(
            orient="records"
        )
    }

    component_cost_lookup = (
        build_component_cost_lookup(
            procurement_tables[
                "component_cost_history"
            ]
        )
    )

    schedule = generate_production_schedule(
        context,
        product_catalog,
    )

    scenario_order_id = next(
        order_id
        for order_id, order in enumerate(
            schedule,
            start=1,
        )
        if (
            order["product_code"]
            == GENERATION_CONFIG.low_yield_product_scenario_code
            and order["planned_start_date"].year == 2025
            and order["planned_start_date"].month == 9
            and order["cycle_number"] == 1
        )
    )

    order_count = len(schedule)

    planned_ids = set(
        range(
            order_count - 7,
            order_count + 1,
        )
    )
    released_ids = set(
        range(
            order_count - 15,
            order_count - 7,
        )
    )
    in_progress_ids = set(
        range(
            order_count - 25,
            order_count - 15,
        )
    )

    unavailable_for_cancellation = (
        planned_ids
        | released_ids
        | in_progress_ids
        | {scenario_order_id}
    )

    cancellation_candidates = [
        order_id
        for order_id in range(
            1,
            order_count + 1,
        )
        if order_id not in unavailable_for_cancellation
    ]

    cancellation_count = round(
        order_count
        * GENERATION_CONFIG.cancellation_target_rate
    )

    cancelled_ids = {
        int(order_id)
        for order_id in context.rng.choice(
            cancellation_candidates,
            size=cancellation_count,
            replace=False,
        )
    }

    production_order_rows = []
    production_lot_rows = []
    material_consumption_rows = []
    conversion_cost_rows = []
    quality_event_rows = []

    production_lot_id = 1
    material_consumption_id = 1
    conversion_cost_id = 1
    quality_event_id = 1

    for production_order_id, order in enumerate(
        schedule,
        start=1,
    ):
        product_id = int(order["product_id"])
        family_code = str(order["family_code"])
        planned_start_date = order[
            "planned_start_date"
        ]

        minimum_quantity, maximum_quantity = (
            PLANNED_QUANTITY_RANGES[family_code]
        )

        planned_quantity = float(
            context.rng.integers(
                minimum_quantity,
                maximum_quantity + 1,
            )
        )

        planned_duration = int(
            context.rng.integers(2, 7)
        )

        planned_end_date = (
            planned_start_date
            + timedelta(days=planned_duration)
        )

        created_date = (
            planned_start_date
            - timedelta(
                days=int(
                    context.rng.integers(7, 15)
                )
            )
        )
        created_at = business_datetime(
            created_date,
            9,
        )

        if production_order_id in cancelled_ids:
            order_status = "CANCELLED"
        elif production_order_id in planned_ids:
            order_status = "PLANNED"
        elif production_order_id in released_ids:
            order_status = "RELEASED"
        elif production_order_id in in_progress_ids:
            order_status = "IN_PROGRESS"
        else:
            order_status = "COMPLETED"

        actual_start_at = None
        actual_end_at = None
        updated_at = created_at

        if order_status in {
            "COMPLETED",
            "IN_PROGRESS",
        }:
            actual_start_date = (
                planned_start_date
                + timedelta(
                    days=int(
                        context.rng.integers(-1, 2)
                    )
                )
            )
            actual_start_date = max(
                actual_start_date,
                GENERATION_CONFIG.start_date,
            )

            actual_start_at = business_datetime(
                actual_start_date,
                8,
            )
            updated_at = actual_start_at

            if order_status == "COMPLETED":
                actual_end_date = (
                    planned_end_date
                    + timedelta(
                        days=int(
                            context.rng.integers(-1, 3)
                        )
                    )
                )
                actual_end_date = max(
                    actual_start_date,
                    actual_end_date,
                )
                actual_end_date = min(
                    actual_end_date,
                    GENERATION_CONFIG.end_date,
                )

                actual_end_at = business_datetime(
                    actual_end_date,
                    18,
                )
                updated_at = actual_end_at
        elif order_status in {
            "RELEASED",
            "CANCELLED",
        }:
            updated_at = business_datetime(
                planned_start_date,
                10,
            )

        bom_id = int(
            bom_by_product[product_id]
        )

        production_order_rows.append(
            {
                "production_order_id": (
                    production_order_id
                ),
                "production_order_number": (
                    f"MO-{planned_start_date.year}-"
                    f"{production_order_id:06d}"
                ),
                "product_id": product_id,
                "plant_id": 1,
                "production_line_id": (
                    line_id_by_code[
                        FAMILY_LINE_CODE[
                            family_code
                        ]
                    ]
                ),
                "bom_id": bom_id,
                "planned_quantity": (
                    planned_quantity
                ),
                "planned_start_date": (
                    planned_start_date
                ),
                "planned_end_date": (
                    planned_end_date
                ),
                "actual_start_at": actual_start_at,
                "actual_end_at": actual_end_at,
                "order_status": order_status,
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )

        if order_status not in {
            "COMPLETED",
            "IN_PROGRESS",
        }:
            continue

        is_low_yield_scenario = (
            production_order_id
            == scenario_order_id
        )

        if order_status == "COMPLETED":
            initial_produced_quantity = round(
                planned_quantity
                * float(
                    context.rng.uniform(
                        0.97,
                        1.03,
                    )
                ),
                6,
            )
            manufactured_date = (
                actual_end_at.date()
            )
        else:
            initial_produced_quantity = round(
                planned_quantity
                * float(
                    context.rng.uniform(
                        0.35,
                        0.70,
                    )
                ),
                6,
            )
            manufactured_date = min(
                actual_start_at.date()
                + timedelta(days=1),
                GENERATION_CONFIG.end_date,
            )

        if is_low_yield_scenario:
            scrap_rate = 0.18
            rework_rate = 0.24
        else:
            scrap_rate = float(
                context.rng.uniform(
                    0.006,
                    0.025,
                )
            )
            has_rework = (
                float(context.rng.random())
                < 0.25
            )
            rework_rate = (
                float(
                    context.rng.uniform(
                        0.010,
                        0.040,
                    )
                )
                if has_rework
                else 0.0
            )

        scrap_quantity = round(
            initial_produced_quantity
            * scrap_rate,
            6,
        )
        good_quantity = round(
            initial_produced_quantity
            - scrap_quantity,
            6,
        )
        produced_quantity = round(
            good_quantity
            + scrap_quantity,
            6,
        )
        reworked_quantity = round(
            produced_quantity
            * rework_rate,
            6,
        )

        if order_status == "COMPLETED":
            release_delay = (
                7
                if is_low_yield_scenario
                else int(
                    context.rng.integers(1, 4)
                )
            )

            released_date = min(
                manufactured_date
                + timedelta(
                    days=release_delay
                ),
                GENERATION_CONFIG.end_date,
            )
            lot_status = "CLOSED"
        else:
            released_date = None
            lot_status = "IN_PROCESS"

        lot_created_at = business_datetime(
            manufactured_date,
            14,
        )
        lot_updated_at = (
            business_datetime(
                released_date,
                16,
            )
            if released_date is not None
            else lot_created_at
        )

        production_lot_rows.append(
            {
                "production_lot_id": (
                    production_lot_id
                ),
                "production_order_id": (
                    production_order_id
                ),
                "lot_code": (
                    f"LOT-{manufactured_date:%Y%m}-"
                    f"{production_order_id:06d}"
                ),
                "manufactured_date": (
                    manufactured_date
                ),
                "released_date": released_date,
                "produced_quantity": (
                    produced_quantity
                ),
                "good_quantity": (
                    good_quantity
                ),
                "scrap_quantity": (
                    scrap_quantity
                ),
                "reworked_quantity": (
                    reworked_quantity
                ),
                "lot_status": lot_status,
                "created_at": lot_created_at,
                "updated_at": lot_updated_at,
            }
        )

        production_lot_id += 1

        bom_items = bom_items_by_bom[
            bom_id
        ]

        material_movement_date = (
            actual_start_at.date()
        )
        material_movement_at = (
            business_datetime(
                material_movement_date,
                10,
            )
        )

        issue_component_ids = []

        for bom_item in bom_items.itertuples(
            index=False
        ):
            component_id = int(
                bom_item.component_id
            )
            issue_component_ids.append(
                component_id
            )

            standard_requirement = (
                produced_quantity
                * float(
                    bom_item.base_quantity_per_unit
                )
                * (
                    1
                    + float(
                        bom_item.standard_scrap_rate
                    )
                )
            )

            if is_low_yield_scenario:
                consumption_factor = float(
                    context.rng.uniform(
                        1.18,
                        1.28,
                    )
                )
            else:
                consumption_factor = float(
                    context.rng.uniform(
                        0.98,
                        1.05,
                    )
                )

            issue_quantity = round(
                standard_requirement
                * consumption_factor,
                6,
            )

            (
                component_cost_id,
                actual_unit_cost_brl,
            ) = find_component_cost(
                component_cost_lookup,
                component_id,
                material_movement_date,
            )

            material_consumption_rows.append(
                {
                    "material_consumption_id": (
                        material_consumption_id
                    ),
                    "production_order_id": (
                        production_order_id
                    ),
                    "component_id": component_id,
                    "component_cost_id": (
                        component_cost_id
                    ),
                    "movement_timestamp": (
                        material_movement_at
                    ),
                    "movement_type": "ISSUE",
                    "quantity": issue_quantity,
                    "actual_unit_cost_brl": round(
                        actual_unit_cost_brl,
                        6,
                    ),
                    "created_at": (
                        material_movement_at
                    ),
                    "updated_at": (
                        material_movement_at
                    ),
                }
            )

            material_consumption_id += 1

            should_return_material = (
                not is_low_yield_scenario
                and float(context.rng.random())
                < 0.10
            )

            if should_return_material:
                return_quantity = round(
                    issue_quantity
                    * float(
                        context.rng.uniform(
                            0.005,
                            0.020,
                        )
                    ),
                    6,
                )

                return_timestamp = (
                    business_datetime(
                        material_movement_date,
                        16,
                    )
                )

                material_consumption_rows.append(
                    {
                        "material_consumption_id": (
                            material_consumption_id
                        ),
                        "production_order_id": (
                            production_order_id
                        ),
                        "component_id": (
                            component_id
                        ),
                        "component_cost_id": (
                            component_cost_id
                        ),
                        "movement_timestamp": (
                            return_timestamp
                        ),
                        "movement_type": (
                            "RETURN_TO_STOCK"
                        ),
                        "quantity": return_quantity,
                        "actual_unit_cost_brl": round(
                            actual_unit_cost_brl,
                            6,
                        ),
                        "created_at": (
                            return_timestamp
                        ),
                        "updated_at": (
                            return_timestamp
                        ),
                    }
                )

                material_consumption_id += 1

        standard_conversion = (
            conversion_lookup[
                (
                    product_id,
                    manufactured_date.year,
                )
            ]
        )

        if is_low_yield_scenario:
            labor_efficiency = 1.45
            machine_efficiency = 1.35
            overhead_efficiency = 1.20
        else:
            labor_efficiency = float(
                context.rng.uniform(
                    0.95,
                    1.10,
                )
            )
            machine_efficiency = float(
                context.rng.uniform(
                    0.95,
                    1.10,
                )
            )
            overhead_efficiency = float(
                context.rng.uniform(
                    0.97,
                    1.08,
                )
            )

        actual_labor_hours = round(
            float(
                standard_conversion[
                    "standard_labor_hours_per_unit"
                ]
            )
            * produced_quantity
            * labor_efficiency,
            6,
        )
        labor_rate = round(
            float(
                standard_conversion[
                    "labor_rate_per_hour_brl"
                ]
            )
            * float(
                context.rng.uniform(
                    0.98,
                    1.08,
                )
            ),
            4,
        )

        actual_machine_hours = round(
            float(
                standard_conversion[
                    "standard_machine_hours_per_unit"
                ]
            )
            * produced_quantity
            * machine_efficiency,
            6,
        )
        machine_rate = round(
            float(
                standard_conversion[
                    "machine_rate_per_hour_brl"
                ]
            )
            * float(
                context.rng.uniform(
                    0.98,
                    1.08,
                )
            ),
            4,
        )

        overhead_cost = round(
            float(
                standard_conversion[
                    "overhead_cost_per_unit_brl"
                ]
            )
            * produced_quantity
            * overhead_efficiency,
            4,
        )

        conversion_timestamp = (
            business_datetime(
                manufactured_date,
                18,
            )
        )

        base_conversion_rows = [
            {
                "cost_type": "DIRECT_LABOR",
                "actual_hours": actual_labor_hours,
                "hourly_rate_brl": labor_rate,
                "actual_cost_brl": round(
                    actual_labor_hours
                    * labor_rate,
                    4,
                ),
            },
            {
                "cost_type": "MACHINE",
                "actual_hours": actual_machine_hours,
                "hourly_rate_brl": machine_rate,
                "actual_cost_brl": round(
                    actual_machine_hours
                    * machine_rate,
                    4,
                ),
            },
            {
                "cost_type": "OVERHEAD",
                "actual_hours": None,
                "hourly_rate_brl": None,
                "actual_cost_brl": (
                    overhead_cost
                ),
            },
        ]

        for conversion_row in (
            base_conversion_rows
        ):
            conversion_cost_rows.append(
                {
                    "conversion_cost_id": (
                        conversion_cost_id
                    ),
                    "production_order_id": (
                        production_order_id
                    ),
                    "cost_date": manufactured_date,
                    **conversion_row,
                    "created_at": (
                        conversion_timestamp
                    ),
                    "updated_at": (
                        conversion_timestamp
                    ),
                }
            )

            conversion_cost_id += 1

        if reworked_quantity > 0:
            rework_labor_hours = round(
                reworked_quantity
                * float(
                    standard_conversion[
                        "standard_labor_hours_per_unit"
                    ]
                )
                * float(
                    context.rng.uniform(
                        0.50,
                        0.90,
                    )
                ),
                6,
            )

            rework_machine_hours = round(
                reworked_quantity
                * float(
                    standard_conversion[
                        "standard_machine_hours_per_unit"
                    ]
                )
                * float(
                    context.rng.uniform(
                        0.40,
                        0.80,
                    )
                ),
                6,
            )

            rework_rows = [
                {
                    "cost_type": "REWORK_LABOR",
                    "actual_hours": (
                        rework_labor_hours
                    ),
                    "hourly_rate_brl": labor_rate,
                    "actual_cost_brl": round(
                        rework_labor_hours
                        * labor_rate,
                        4,
                    ),
                },
                {
                    "cost_type": "REWORK_MACHINE",
                    "actual_hours": (
                        rework_machine_hours
                    ),
                    "hourly_rate_brl": (
                        machine_rate
                    ),
                    "actual_cost_brl": round(
                        rework_machine_hours
                        * machine_rate,
                        4,
                    ),
                },
            ]

            for rework_row in rework_rows:
                conversion_cost_rows.append(
                    {
                        "conversion_cost_id": (
                            conversion_cost_id
                        ),
                        "production_order_id": (
                            production_order_id
                        ),
                        "cost_date": (
                            manufactured_date
                        ),
                        **rework_row,
                        "created_at": (
                            conversion_timestamp
                        ),
                        "updated_at": (
                            conversion_timestamp
                        ),
                    }
                )

                conversion_cost_id += 1

        event_timestamp = business_datetime(
            manufactured_date,
            16,
        )

        if (
            scrap_rate >= 0.018
            or is_low_yield_scenario
        ):
            affected_component_id = (
                None
                if is_low_yield_scenario
                else int(
                    context.rng.choice(
                        issue_component_ids
                    )
                )
            )

            quality_event_rows.append(
                {
                    "quality_event_id": (
                        quality_event_id
                    ),
                    "production_order_id": (
                        production_order_id
                    ),
                    "component_id": (
                        affected_component_id
                    ),
                    "event_timestamp": (
                        event_timestamp
                    ),
                    "event_type": "SCRAP",
                    "quantity_affected": (
                        scrap_quantity
                    ),
                    "reason_code": (
                        "CALIBRATION_FAILURE"
                        if is_low_yield_scenario
                        else "PROCESS_VARIATION"
                    ),
                    "event_description": (
                        "Refugo elevado provocado por falha "
                        "de calibração na linha IoT."
                        if is_low_yield_scenario
                        else "Refugo acima do limite operacional."
                    ),
                    "created_at": event_timestamp,
                    "updated_at": event_timestamp,
                }
            )

            quality_event_id += 1

        if reworked_quantity > 0:
            quality_event_rows.append(
                {
                    "quality_event_id": (
                        quality_event_id
                    ),
                    "production_order_id": (
                        production_order_id
                    ),
                    "component_id": None,
                    "event_timestamp": (
                        event_timestamp
                    ),
                    "event_type": "REWORK",
                    "quantity_affected": (
                        reworked_quantity
                    ),
                    "reason_code": (
                        "CALIBRATION_FAILURE"
                        if is_low_yield_scenario
                        else "ASSEMBLY_ADJUSTMENT"
                    ),
                    "event_description": (
                        "Retrabalho necessário após falha "
                        "de calibração do processo."
                        if is_low_yield_scenario
                        else "Retrabalho por ajuste de montagem."
                    ),
                    "created_at": event_timestamp,
                    "updated_at": event_timestamp,
                }
            )

            quality_event_id += 1

        if is_low_yield_scenario:
            quality_event_rows.append(
                {
                    "quality_event_id": (
                        quality_event_id
                    ),
                    "production_order_id": (
                        production_order_id
                    ),
                    "component_id": None,
                    "event_timestamp": (
                        event_timestamp
                    ),
                    "event_type": "QUALITY_HOLD",
                    "quantity_affected": (
                        produced_quantity
                    ),
                    "reason_code": (
                        "LOW_YIELD_REVIEW"
                    ),
                    "event_description": (
                        "Lote retido para revisão devido "
                        "a rendimento abaixo do padrão."
                    ),
                    "created_at": event_timestamp,
                    "updated_at": event_timestamp,
                }
            )

            quality_event_id += 1

    return {
        "production_orders": pd.DataFrame(
            production_order_rows
        ),
        "production_lots": pd.DataFrame(
            production_lot_rows
        ),
        "production_material_consumption": (
            pd.DataFrame(
                material_consumption_rows
            )
        ),
        "production_conversion_costs": (
            pd.DataFrame(
                conversion_cost_rows
            )
        ),
        "production_quality_events": (
            pd.DataFrame(
                quality_event_rows
            )
        ),
    }


def main() -> None:
    """Generate manufacturing data and print row counts."""

    context = RandomContext()

    industrial_tables = (
        generate_industrial_master_data(context)
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

    tables = generate_manufacturing_transactions(
        context,
        industrial_tables,
        costing_tables,
        procurement_tables,
    )

    for table_name, dataframe in tables.items():
        print(f"{table_name}: {len(dataframe)} rows")


if __name__ == "__main__":
    main()