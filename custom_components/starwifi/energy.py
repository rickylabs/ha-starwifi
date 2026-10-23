"""Hourly energy per heater, from the app's history, as statistics for the Energy dashboard."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, tzinfo
import logging

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from .api import StarWifiError
from .const import DOMAIN
from .coordinator import StarWifiCoordinator

_LOGGER = logging.getLogger(__name__)

ENERGY_INTERVAL = timedelta(minutes=30)
# The first import reads this many days of history.
BACKFILL_DAYS = 31
# An hour's row shows up some time after the hour ends: read the last hours again.
REREAD = timedelta(hours=3)

Row = tuple[datetime, float, float]


def statistic_id(device_id: str) -> str:
    return f"{DOMAIN}:energy_{device_id}"


def hourly_rows(
    start: datetime, end: datetime, tz: tzinfo, days: dict[date, dict[int, float]], base: float
) -> list[Row]:
    """(hour start, kWh in that hour, running total) for every hour from start to end.

    The history is in local hours. When the clocks go back, the repeated hour
    takes the app's value once, at its first occurrence.
    """
    rows: list[Row] = []
    seen: set[tuple[date, int]] = set()
    total = base
    hour = start
    while hour < end:
        local = hour.astimezone(tz)
        key = (local.date(), local.hour)
        kwh = 0.0 if key in seen else days.get(key[0], {}).get(key[1], 0.0)
        seen.add(key)
        total += kwh
        rows.append((hour, kwh, round(total, 4)))
        hour += timedelta(hours=1)
    return rows


class EnergyImporter:
    """Every 30 minutes, brings each heater's hourly energy up to date, one heater at a time."""

    def __init__(self, hass: HomeAssistant, coordinator: StarWifiCoordinator) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self._task: asyncio.Task | None = None

    @callback
    def start(self, _now: datetime | None = None) -> None:
        if self._task and not self._task.done():
            return
        self._task = self.coordinator.config_entry.async_create_background_task(
            self.hass, self.run(), f"{DOMAIN} energy import"
        )

    async def run(self) -> None:
        for device_id, heater in (self.coordinator.data or {}).items():
            reference = heater["device"].get("reference")
            if not reference:
                continue
            try:
                await self.import_heater(device_id, reference, heater["label"])
            except StarWifiError as err:
                # Nothing written for this heater; the next run starts from the same place.
                _LOGGER.debug("Energy of heater %s not read: %s", device_id, err)

    async def import_heater(self, device_id: str, reference: str, label: str) -> None:
        stat = statistic_id(device_id)
        tz = dt_util.get_default_time_zone()
        now = dt_util.utcnow()
        end = now.replace(minute=0, second=0, microsecond=0)
        recorder = get_instance(self.hass)

        last = await recorder.async_add_executor_job(
            get_last_statistics, self.hass, 1, stat, True, {"sum"}
        )
        if last.get(stat):
            since = dt_util.utc_from_timestamp(last[stat][0]["start"]) - REREAD
        else:
            since = now - timedelta(days=BACKFILL_DAYS)
        first_day = since.astimezone(tz).date()
        start = dt_util.as_utc(dt_util.start_of_local_day(first_day))

        # Whole days are written again from midnight, on top of the total before it.
        before = await recorder.async_add_executor_job(
            statistics_during_period, self.hass, start - timedelta(hours=1), start, {stat}, "hour", None, {"sum"}
        )
        base = (before.get(stat) or [{}])[-1].get("sum") or 0.0

        days: dict[date, dict[int, float]] = {}
        day, today = first_day, now.astimezone(tz).date()
        while day <= today:
            days[day] = await self.coordinator.api.day_consumption(reference, day)
            day += timedelta(days=1)

        rows = hourly_rows(start, end, tz, days, base)
        if not rows:
            return
        metadata = StatisticMetaData(
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=f"{label} energy",
            source=DOMAIN,
            statistic_id=stat,
            unit_class=EnergyConverter.UNIT_CLASS,
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        )
        async_add_external_statistics(
            self.hass, metadata, [StatisticData(start=t, state=kwh, sum=total) for t, kwh, total in rows]
        )
