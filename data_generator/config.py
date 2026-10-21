"""Central configuration for deterministic synthetic data generation."""

import os
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    """Business period, volumes, and deterministic generation rules."""

    random_seed: int = 20261015
    faker_locale: str = "pt_BR"

    start_date: date = date(2024, 1, 1)
    end_date: date = date(2025, 12, 31)

    customer_count: int = 120
    salesperson_count: int = 12
    product_count: int = 15
    component_count: int = 60
    supplier_count: int = 18

    purchase_order_count: int = 1_200
    production_order_count: int = 720
    sales_order_count: int = 6_000

    traceability_target_rate: float = 0.78
    return_target_rate: float = 0.04
    cancellation_target_rate: float = 0.02

    imported_component_scenario_code: str = "CMP-COM-001"
    discount_customer_scenario_code: str = "CUS-0007"
    low_yield_product_scenario_code: str = "PRD-IOT-003"

    def __post_init__(self) -> None:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date.")

        count_fields = (
            self.customer_count,
            self.salesperson_count,
            self.product_count,
            self.component_count,
            self.supplier_count,
            self.purchase_order_count,
            self.production_order_count,
            self.sales_order_count,
        )

        if any(value <= 0 for value in count_fields):
            raise ValueError("All configured record counts must be positive.")

        rate_fields = (
            self.traceability_target_rate,
            self.return_target_rate,
            self.cancellation_target_rate,
        )

        if any(value < 0 or value > 1 for value in rate_fields):
            raise ValueError("Configured rates must be between 0 and 1.")


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    """PostgreSQL connection settings loaded from the local .env file."""

    dbname: str
    user: str
    password: str = field(repr=False)
    host: str = "localhost"
    port: int = 5433

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        load_dotenv()

        required_variables = (
            "POSTGRES_DB",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_HOST",
            "POSTGRES_PORT",
        )

        missing_variables = [
            variable
            for variable in required_variables
            if not os.getenv(variable)
        ]

        if missing_variables:
            missing = ", ".join(missing_variables)
            raise RuntimeError(f"Missing environment variables: {missing}")

        return cls(
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            host=os.environ["POSTGRES_HOST"],
            port=int(os.environ["POSTGRES_PORT"]),
        )

    def connection_kwargs(self) -> dict[str, Any]:
        return {
            "dbname": self.dbname,
            "user": self.user,
            "password": self.password,
            "host": self.host,
            "port": self.port,
        }


GENERATION_CONFIG = GenerationConfig()