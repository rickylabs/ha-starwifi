"""Polls every heater of the account in two requests, and their weekly plans less often."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import StarWifiApi, StarWifiError
from .const import CONF_USER_ID, DOMAIN
from .schedule import Week, week_from_slots

_LOGGER = logging.getLogger(__name__)

PLAN_INTERVAL = timedelta(minutes=15)


def to_float(value: Any) -> float | None:
    """The cloud sends numbers as strings, and "-" when a heater is offline."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_on(value: Any) -> bool:
    return value in (True, 1, "1", "ON", "on", "true", "True")


class StarWifiCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Data is {device id: {"device": ..., "label": ..., "last": last_reader, "plan": week or None}}."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: StarWifiApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self.api = api
        self.user_id: str = entry.data[CONF_USER_ID]
        self.plans: dict[str, Week | None] = {}
        self.plans_at: datetime | None = None

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            devices = await self.api.devices(self.user_id)
            by_id = {str(d["id"]): d for d in devices if isinstance(d, dict) and d.get("id")}
            readings = await self.api.last_readings(list(by_id)) if by_id else []
        except StarWifiError as err:
            raise UpdateFailed(str(err)) from err
        await self._refresh_plans(by_id)

        last = {str(r.get("id")): r for r in readings if isinstance(r, dict)}
        data: dict[str, dict[str, Any]] = {}
        for device_id, device in by_id.items():
            reading = last.get(device_id, {})
            data[device_id] = {
                "device": device,
                "label": reading.get("label") or device.get("label") or f"Heater {device_id}",
                "last": reading.get("last_reader") or {},
                "plan": self.plans.get(device_id),
            }
        return data

    async def _refresh_plans(self, by_id: dict[str, dict[str, Any]]) -> None:
        """Plans change rarely: read them every 15 minutes, one request per heater."""
        now = dt_util.utcnow()
        if self.plans_at and now - self.plans_at < PLAN_INTERVAL and set(by_id) <= set(self.plans):
            return
        results = await asyncio.gather(
            *(self.api.calendar(d.get("reference")) for d in by_id.values()),
            return_exceptions=True,
        )
        for device_id, result in zip(by_id, results):
            if isinstance(result, StarWifiError):
                # Keep the last plan we read; the readings above are still good.
                _LOGGER.debug("Plan of heater %s not read: %s", device_id, result)
                # Known but unread: try again in 15 minutes, not at every poll.
                self.plans.setdefault(device_id, None)
                continue
            if isinstance(result, BaseException):
                raise result
            self.plans[device_id] = week_from_slots(result)
        self.plans_at = now
