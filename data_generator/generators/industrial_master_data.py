"""Generate deterministic industrial master data."""

from datetime import date, datetime

import pandas as pd

from data_generator.config import GENERATION_CONFIG, GenerationConfig
from data_generator.random_context import BUSINESS_TIMEZONE, RandomContext

MASTER_CREATED_AT = datetime(
    2023,
    1,
    1,
    9,
    0,
    tzinfo=BUSINESS_TIMEZONE,
)

MASTER_UPDATED_AT = datetime(
    2023,
    12,
    15,
    9,
    0,
    tzinfo=BUSINESS_TIMEZONE,
)


def generate_plants() -> pd.DataFrame:
    """Generate the fictional manufacturing plant."""

    records = [
        {
            "plant_id": 1,
            "plant_code": "PLT-CPS",
            "plant_name": "MarginLens Electronics - Campinas",
            "city": "Campinas",
            "state_code": "SP",
            "country_code": "BR",
            "active_from": date(2017, 1, 1),
            "active_to": None,
            "created_at": MASTER_CREATED_AT,
            "updated_at": MASTER_UPDATED_AT,
        }
    ]

    return pd.DataFrame(records)


def generate_production_lines() -> pd.DataFrame:
    """Generate the three production lines."""

    line_specs = [
        (1, "LINE-CTRL", "Industrial Controllers Line"),
        (2, "LINE-IOT", "Industrial IoT Gateways Line"),
        (3, "LINE-ENE", "Energy Monitoring Modules Line"),
    ]

    records = [
        {
            "production_line_id": line_id,
            "plant_id": 1,
            "line_code": line_code,
            "line_name": line_name,
            "active_from": date(2018, 1, 1),
            "active_to": None,
            "created_at": MASTER_CREATED_AT,
            "updated_at": MASTER_UPDATED_AT,
        }
        for line_id, line_code, line_name in line_specs
    ]

    return pd.DataFrame(records)


def generate_product_families() -> pd.DataFrame:
    """Generate the three product families."""

    family_specs = [
        (1, "CTRL", "Industrial Controllers"),
        (2, "IOT", "Industrial IoT Gateways"),
        (3, "ENERGY", "Energy Monitoring Modules"),
    ]

    records = [
        {
            "product_family_id": family_id,
            "family_code": family_code,
            "family_name": family_name,
            "created_at": MASTER_CREATED_AT,
            "updated_at": MASTER_UPDATED_AT,
        }
        for family_id, family_code, family_name in family_specs
    ]

    return pd.DataFrame(records)


def generate_products(
    context: RandomContext,
    config: GenerationConfig,
) -> pd.DataFrame:
    """Generate five products for each family."""

    product_specs = {
        1: [
            "Compact Controller C100",
            "Modular Controller C200",
            "Advanced Controller C300",
            "Motion Controller M100",
            "Safety Controller S200",
        ],
        2: [
            "Industrial Gateway G100",
            "Industrial Gateway G200",
            "Edge Gateway G300",
            "Cellular Gateway G400",
            "Secure Gateway G500",
        ],
        3: [
            "Energy Monitor E100",
            "Energy Monitor E200",
            "Power Quality Monitor E300",
            "Three-Phase Meter E400",
            "Smart Meter E500",
        ],
    }

    family_codes = {
        1: "CTRL",
        2: "IOT",
        3: "ENE",
    }

    physical_ranges = {
        1: {
            "net_weight": (0.60, 1.60),
            "volume": (0.0020, 0.0080),
        },
        2: {
            "net_weight": (0.35, 1.00),
            "volume": (0.0015, 0.0060),
        },
        3: {
            "net_weight": (0.25, 0.80),
            "volume": (0.0010, 0.0045),
        },
    }

    expected_count = sum(len(names) for names in product_specs.values())

    if config.product_count != expected_count:
        raise ValueError(
            f"Configured product_count must be {expected_count}.",
        )

    records = []
    product_id = 1

    for family_id, product_names in product_specs.items():
        family_code = family_codes[family_id]
        ranges = physical_ranges[family_id]

        for family_sequence, product_name in enumerate(
            product_names,
            start=1,
        ):
            net_weight = round(
                float(
                    context.rng.uniform(
                        *ranges["net_weight"],
                    )
                ),
                4,
            )

            gross_weight = round(
                net_weight
                * float(context.rng.uniform(1.08, 1.22)),
                4,
            )

            package_volume = round(
                float(
                    context.rng.uniform(
                        *ranges["volume"],
                    )
                ),
                6,
            )

            records.append(
                {
                    "product_id": product_id,
                    "product_family_id": family_id,
                    "product_code": (
                        f"PRD-{family_code}-{family_sequence:03d}"
                    ),
                    "product_name": product_name,
                    "unit_of_measure": "EA",
                    "net_weight_kg": net_weight,
                    "gross_weight_kg": gross_weight,
                    "package_volume_m3": package_volume,
                    "launch_date": context.random_date(
                        date(2020, 1, 1),
                        date(2023, 6, 30),
                    ),
                    "discontinue_date": None,
                    "product_status": "ACTIVE",
                    "created_at": MASTER_CREATED_AT,
                    "updated_at": MASTER_UPDATED_AT,
                }
            )

            product_id += 1

    return pd.DataFrame(records)


def generate_component_categories() -> pd.DataFrame:
    """Generate electronic component categories."""

    category_specs = [
        (1, "PCB", "Printed Circuit Boards"),
        (2, "MCU", "Microcontrollers"),
        (3, "COMM", "Communication Modules"),
        (4, "SENSOR", "Sensors"),
        (5, "POWER", "Power Supplies"),
        (6, "CONN", "Connectors"),
        (7, "ENC", "Enclosures"),
        (8, "DISPLAY", "Electronic Displays"),
    ]

    records = [
        {
            "component_category_id": category_id,
            "category_code": category_code,
            "category_name": category_name,
            "created_at": MASTER_CREATED_AT,
            "updated_at": MASTER_UPDATED_AT,
        }
        for category_id, category_code, category_name in category_specs
    ]

    return pd.DataFrame(records)


def generate_components(
    context: RandomContext,
    config: GenerationConfig,
) -> pd.DataFrame:
    """Generate local and imported electronic components."""

    category_specs = [
        {
            "category_id": 1,
            "code_prefix": "PCB",
            "name": "Printed Circuit Board",
            "count": 9,
            "import_rate": 0.55,
        },
        {
            "category_id": 2,
            "code_prefix": "MCU",
            "name": "Microcontroller",
            "count": 6,
            "import_rate": 0.90,
        },
        {
            "category_id": 3,
            "code_prefix": "COM",
            "name": "Communication Module",
            "count": 6,
            "import_rate": 0.90,
        },
        {
            "category_id": 4,
            "code_prefix": "SNS",
            "name": "Electronic Sensor",
            "count": 8,
            "import_rate": 0.60,
        },
        {
            "category_id": 5,
            "code_prefix": "PWR",
            "name": "Power Supply",
            "count": 8,
            "import_rate": 0.50,
        },
        {
            "category_id": 6,
            "code_prefix": "CON",
            "name": "Industrial Connector",
            "count": 10,
            "import_rate": 0.30,
        },
        {
            "category_id": 7,
            "code_prefix": "ENC",
            "name": "Product Enclosure",
            "count": 8,
            "import_rate": 0.20,
        },
        {
            "category_id": 8,
            "code_prefix": "DSP",
            "name": "Electronic Display",
            "count": 5,
            "import_rate": 0.80,
        },
    ]

    expected_count = sum(
        category["count"]
        for category in category_specs
    )

    if config.component_count != expected_count:
        raise ValueError(
            f"Configured component_count must be {expected_count}.",
        )

    records = []
    component_id = 1

    for category in category_specs:
        for category_sequence in range(1, category["count"] + 1):
            component_code = (
                f"CMP-{category['code_prefix']}-{category_sequence:03d}"
            )

            is_scenario_component = (
                component_code
                == config.imported_component_scenario_code
            )

            is_imported = (
                is_scenario_component
                or context.rng.random() < category["import_rate"]
            )

            sourcing_type = (
                "IMPORTED"
                if is_imported
                else "DOMESTIC"
            )

            if is_scenario_component:
                preferred_currency = "USD"
            elif is_imported:
                preferred_currency = str(
                    context.rng.choice(
                        ["USD", "EUR"],
                        p=[0.80, 0.20],
                    )
                )
            else:
                preferred_currency = "BRL"

            if is_imported:
                lead_time_days = int(
                    context.rng.integers(45, 121),
                )
            else:
                lead_time_days = int(
                    context.rng.integers(7, 31),
                )

            records.append(
                {
                    "component_id": component_id,
                    "component_category_id": category["category_id"],
                    "component_code": component_code,
                    "component_name": (
                        f"{category['name']} {category_sequence:03d}"
                    ),
                    "unit_of_measure": "EA",
                    "sourcing_type": sourcing_type,
                    "preferred_currency": preferred_currency,
                    "standard_lead_time_days": lead_time_days,
                    "is_active": True,
                    "created_at": MASTER_CREATED_AT,
                    "updated_at": MASTER_UPDATED_AT,
                }
            )

            component_id += 1

    return pd.DataFrame(records)


def generate_suppliers(
    context: RandomContext,
    config: GenerationConfig,
) -> pd.DataFrame:
    """Generate domestic and international suppliers."""

    domestic_count = 10
    international_specs = [
        ("US", "USD"),
        ("US", "USD"),
        ("CN", "USD"),
        ("CN", "USD"),
        ("DE", "EUR"),
        ("DE", "EUR"),
        ("TW", "USD"),
        ("MX", "USD"),
    ]

    expected_count = domestic_count + len(international_specs)

    if config.supplier_count != expected_count:
        raise ValueError(
            f"Configured supplier_count must be {expected_count}.",
        )

    brazilian_states = [
        "SP",
        "MG",
        "RJ",
        "PR",
        "SC",
        "RS",
    ]

    records = []

    for supplier_id in range(1, domestic_count + 1):
        records.append(
            {
                "supplier_id": supplier_id,
                "supplier_code": f"SUP-BR-{supplier_id:03d}",
                "supplier_name": (
                    f"{context.faker.unique.company()} BR"
                ),
                "country_code": "BR",
                "state_code": str(
                    context.rng.choice(brazilian_states)
                ),
                "default_currency": "BRL",
                "is_active": True,
                "created_at": MASTER_CREATED_AT,
                "updated_at": MASTER_UPDATED_AT,
            }
        )

    for sequence, (country_code, currency_code) in enumerate(
        international_specs,
        start=1,
    ):
        supplier_id = domestic_count + sequence

        records.append(
            {
                "supplier_id": supplier_id,
                "supplier_code": f"SUP-INT-{sequence:03d}",
                "supplier_name": (
                    f"{context.faker.unique.company()} Global"
                ),
                "country_code": country_code,
                "state_code": None,
                "default_currency": currency_code,
                "is_active": True,
                "created_at": MASTER_CREATED_AT,
                "updated_at": MASTER_UPDATED_AT,
            }
        )

    return pd.DataFrame(records)


def generate_industrial_master_data(
    context: RandomContext | None = None,
    config: GenerationConfig = GENERATION_CONFIG,
) -> dict[str, pd.DataFrame]:
    """Generate all industrial master tables in dependency order."""

    random_context = context or RandomContext()

    return {
        "plants": generate_plants(),
        "production_lines": generate_production_lines(),
        "product_families": generate_product_families(),
        "products": generate_products(
            random_context,
            config,
        ),
        "component_categories": generate_component_categories(),
        "components": generate_components(
            random_context,
            config,
        ),
        "suppliers": generate_suppliers(
            random_context,
            config,
        ),
    }


def main() -> None:
    """Generate the tables and print their row counts."""

    tables = generate_industrial_master_data()

    for table_name, dataframe in tables.items():
        print(f"{table_name}: {len(dataframe)} rows")


if __name__ == "__main__":
    main()