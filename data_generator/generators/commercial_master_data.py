"""Generate deterministic commercial master data."""

from datetime import date, datetime, time

import pandas as pd

from data_generator.config import GENERATION_CONFIG
from data_generator.random_context import BUSINESS_TIMEZONE, RandomContext

MASTER_UPDATED_AT = datetime(
    2025,
    12,
    31,
    23,
    59,
    59,
    tzinfo=BUSINESS_TIMEZONE,
)


CUSTOMER_LOCATIONS = {
    "NORTH": [
        ("Manaus", "AM"),
        ("Belém", "PA"),
        ("Porto Velho", "RO"),
    ],
    "NORTHEAST": [
        ("Salvador", "BA"),
        ("Recife", "PE"),
        ("Fortaleza", "CE"),
        ("São Luís", "MA"),
    ],
    "CENTRAL_WEST": [
        ("Goiânia", "GO"),
        ("Brasília", "DF"),
        ("Cuiabá", "MT"),
        ("Campo Grande", "MS"),
    ],
    "SOUTHEAST": [
        ("Campinas", "SP"),
        ("São Paulo", "SP"),
        ("Sorocaba", "SP"),
        ("São José dos Campos", "SP"),
        ("Belo Horizonte", "MG"),
        ("Rio de Janeiro", "RJ"),
        ("Vitória", "ES"),
    ],
    "SOUTH": [
        ("Curitiba", "PR"),
        ("Joinville", "SC"),
        ("Florianópolis", "SC"),
        ("Porto Alegre", "RS"),
        ("Caxias do Sul", "RS"),
    ],
}


def generate_customer_segments() -> pd.DataFrame:
    """Generate the four B2B customer segments."""

    created_at = datetime(
        2023,
        1,
        1,
        9,
        0,
        tzinfo=BUSINESS_TIMEZONE,
    )

    rows = [
        {
            "customer_segment_id": 1,
            "segment_code": "STRATEGIC",
            "segment_name": "Contas estratégicas",
            "segment_description": (
                "Grandes contas industriais com negociação direta "
                "e contratos comerciais recorrentes."
            ),
            "created_at": created_at,
            "updated_at": MASTER_UPDATED_AT,
        },
        {
            "customer_segment_id": 2,
            "segment_code": "DISTRIBUTOR",
            "segment_name": "Distribuidores",
            "segment_description": (
                "Empresas que revendem os produtos eletrônicos "
                "fabricados pela MarginLens."
            ),
            "created_at": created_at,
            "updated_at": MASTER_UPDATED_AT,
        },
        {
            "customer_segment_id": 3,
            "segment_code": "SYSTEM_INTEGRATOR",
            "segment_name": "Integradores de sistemas",
            "segment_description": (
                "Integradores que incorporam os produtos em projetos "
                "de automação e IoT industrial."
            ),
            "created_at": created_at,
            "updated_at": MASTER_UPDATED_AT,
        },
        {
            "customer_segment_id": 4,
            "segment_code": "INDUSTRIAL_END_USER",
            "segment_name": "Indústrias consumidoras",
            "segment_description": (
                "Indústrias que utilizam diretamente os equipamentos "
                "em suas operações."
            ),
            "created_at": created_at,
            "updated_at": MASTER_UPDATED_AT,
        },
    ]

    return pd.DataFrame(rows)


def generate_customers(
    context: RandomContext,
) -> pd.DataFrame:
    """Generate B2B customers across the five Brazilian regions."""

    segment_ids = {
        "STRATEGIC": 1,
        "DISTRIBUTOR": 2,
        "SYSTEM_INTEGRATOR": 3,
        "INDUSTRIAL_END_USER": 4,
    }

    segment_codes = list(segment_ids)
    segment_probabilities = [0.15, 0.30, 0.30, 0.25]

    region_codes = [
        "NORTH",
        "NORTHEAST",
        "CENTRAL_WEST",
        "SOUTHEAST",
        "SOUTH",
    ]
    region_probabilities = [0.05, 0.15, 0.10, 0.50, 0.20]

    rows = []

    for customer_id in range(
        1,
        GENERATION_CONFIG.customer_count + 1,
    ):
        customer_code = f"CUS-{customer_id:04d}"

        segment_code = context.weighted_choice(
            segment_codes,
            segment_probabilities,
        )
        sales_region = context.weighted_choice(
            region_codes,
            region_probabilities,
        )

        location_options = CUSTOMER_LOCATIONS[sales_region]
        location_index = int(
            context.rng.integers(0, len(location_options))
        )
        city, state_code = location_options[location_index]

        customer_name = context.faker.company()[:150]

        # This customer will receive the escalating-discount scenario
        # when sales transactions are generated.
        if (
            customer_code
            == GENERATION_CONFIG.discount_customer_scenario_code
        ):
            segment_code = "STRATEGIC"
            customer_name = "Aureon Sistemas Industriais S.A."
            city = "Campinas"
            state_code = "SP"
            sales_region = "SOUTHEAST"

        customer_since = context.random_date(
            date(2018, 1, 1),
            date(2023, 12, 31),
        )

        # Six customers become inactive during 2025.
        is_active = customer_id % 20 != 0

        inactive_date = None
        if not is_active:
            inactive_date = context.random_date(
                date(2025, 1, 1),
                date(2025, 12, 15),
            )

        created_at = datetime.combine(
            customer_since,
            time(9, 0),
            tzinfo=BUSINESS_TIMEZONE,
        )

        rows.append(
            {
                "customer_id": customer_id,
                "customer_segment_id": segment_ids[segment_code],
                "customer_code": customer_code,
                "customer_name": customer_name,
                "city": city,
                "state_code": state_code,
                "sales_region": sales_region,
                "country_code": "BR",
                "customer_since": customer_since,
                "inactive_date": inactive_date,
                "is_active": is_active,
                "created_at": created_at,
                "updated_at": MASTER_UPDATED_AT,
            }
        )

    return pd.DataFrame(rows)


def generate_sales_channels() -> pd.DataFrame:
    """Generate the available B2B sales channels."""

    created_at = datetime(
        2023,
        1,
        1,
        9,
        0,
        tzinfo=BUSINESS_TIMEZONE,
    )

    rows = [
        {
            "sales_channel_id": 1,
            "channel_code": "DIRECT",
            "channel_name": "Venda direta",
            "channel_description": (
                "Negociação conduzida diretamente pela equipe comercial."
            ),
            "created_at": created_at,
            "updated_at": MASTER_UPDATED_AT,
        },
        {
            "sales_channel_id": 2,
            "channel_code": "PARTNER",
            "channel_name": "Parceiros e distribuidores",
            "channel_description": (
                "Vendas realizadas por distribuidores e parceiros autorizados."
            ),
            "created_at": created_at,
            "updated_at": MASTER_UPDATED_AT,
        },
        {
            "sales_channel_id": 3,
            "channel_code": "DIGITAL_B2B",
            "channel_name": "Portal digital B2B",
            "channel_description": (
                "Pedidos recorrentes efetuados pelo portal corporativo."
            ),
            "created_at": created_at,
            "updated_at": MASTER_UPDATED_AT,
        },
    ]

    return pd.DataFrame(rows)


def generate_salespeople(
    context: RandomContext,
) -> pd.DataFrame:
    """Generate salespeople distributed across Brazilian regions."""

    region_distribution = [
        "SOUTHEAST",
        "SOUTHEAST",
        "SOUTHEAST",
        "SOUTHEAST",
        "SOUTHEAST",
        "SOUTH",
        "SOUTH",
        "NORTHEAST",
        "NORTHEAST",
        "CENTRAL_WEST",
        "CENTRAL_WEST",
        "NORTH",
    ]

    rows = []

    for salesperson_id in range(
        1,
        GENERATION_CONFIG.salesperson_count + 1,
    ):
        sales_region = region_distribution[
            (salesperson_id - 1) % len(region_distribution)
        ]

        hire_date = context.random_date(
            date(2017, 1, 1),
            date(2023, 12, 31),
        )

        # One historical termination makes the status fields realistic.
        is_active = salesperson_id != 5
        termination_date = (
            date(2025, 6, 30)
            if not is_active
            else None
        )

        created_at = datetime.combine(
            hire_date,
            time(9, 0),
            tzinfo=BUSINESS_TIMEZONE,
        )

        rows.append(
            {
                "salesperson_id": salesperson_id,
                "salesperson_code": f"SAL-{salesperson_id:03d}",
                "salesperson_name": context.faker.name()[:150],
                "sales_region": sales_region,
                "hire_date": hire_date,
                "termination_date": termination_date,
                "is_active": is_active,
                "created_at": created_at,
                "updated_at": MASTER_UPDATED_AT,
            }
        )

    return pd.DataFrame(rows)


def generate_commercial_master_data(
    context: RandomContext,
) -> dict[str, pd.DataFrame]:
    """Generate all commercial master-data tables."""

    return {
        "customer_segments": generate_customer_segments(),
        "customers": generate_customers(context),
        "sales_channels": generate_sales_channels(),
        "salespeople": generate_salespeople(context),
    }


def main() -> None:
    """Generate the tables in memory and print their row counts."""

    context = RandomContext()
    tables = generate_commercial_master_data(context)

    for table_name, dataframe in tables.items():
        print(f"{table_name}: {len(dataframe)} rows")


if __name__ == "__main__":
    main()