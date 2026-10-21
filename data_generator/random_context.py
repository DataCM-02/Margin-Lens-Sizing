"""Deterministic random and Faker helpers."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
from faker import Faker
from numpy.random import Generator

from data_generator.config import GENERATION_CONFIG

BUSINESS_TIMEZONE = ZoneInfo("America/Sao_Paulo")


class RandomContext:
    """Shared deterministic random context for all data generators."""

    def __init__(
        self,
        seed: int = GENERATION_CONFIG.random_seed,
        locale: str = GENERATION_CONFIG.faker_locale,
    ) -> None:
        self.seed = seed
        self.rng: Generator = np.random.default_rng(seed)
        self.faker = Faker(locale)
        self.faker.seed_instance(seed)

    def random_date(self, start_date: date, end_date: date) -> date:
        """Return a deterministic random date inside an inclusive interval."""

        if end_date < start_date:
            raise ValueError("end_date must not be earlier than start_date.")

        interval_days = (end_date - start_date).days
        offset_days = int(self.rng.integers(0, interval_days + 1))

        return date.fromordinal(start_date.toordinal() + offset_days)

    def random_datetime(
        self,
        start_date: date,
        end_date: date,
        start_hour: int = 8,
        end_hour: int = 18,
    ) -> datetime:
        """Return a timezone-aware deterministic business timestamp."""

        if not 0 <= start_hour <= end_hour <= 23:
            raise ValueError("Hours must satisfy 0 <= start_hour <= end_hour <= 23.")

        selected_date = self.random_date(start_date, end_date)
        selected_hour = int(
            self.rng.integers(start_hour, end_hour + 1),
        )
        selected_minute = int(self.rng.integers(0, 60))
        selected_second = int(self.rng.integers(0, 60))

        return datetime(
            year=selected_date.year,
            month=selected_date.month,
            day=selected_date.day,
            hour=selected_hour,
            minute=selected_minute,
            second=selected_second,
            tzinfo=BUSINESS_TIMEZONE,
        )

    def weighted_choice(
        self,
        values: list[str],
        probabilities: list[float],
    ) -> str:
        """Select one value using explicit probabilities."""

        if len(values) != len(probabilities):
            raise ValueError("Values and probabilities must have equal lengths.")

        if not np.isclose(sum(probabilities), 1.0):
            raise ValueError("Probabilities must sum to 1.")

        selected_index = int(
            self.rng.choice(
                len(values),
                p=probabilities,
            )
        )

        return values[selected_index]