"""Polls every heater of the account in two requests."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import StarWifiApi, StarWifiError
from .const import CONF_USER_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


def to_float(value: Any) -> float | None:
    """The cloud sends numbers as strings, and "-" when a heater is offline."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_on(value: Any) -> bool:
    return value in (True, 1, "1", "ON", "on", "true", "True")


class StarWifiCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Data is {device id: {"device": ..., "label": ..., "last": last_reader}}."""

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

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            devices = await self.api.devices(self.user_id)
            by_id = {str(d["id"]): d for d in devices if isinstance(d, dict) and d.get("id")}
            readings = await self.api.last_readings(list(by_id)) if by_id else []
        except StarWifiError as err:
            raise UpdateFailed(str(err)) from err

        last = {str(r.get("id")): r for r in readings if isinstance(r, dict)}
        data: dict[str, dict[str, Any]] = {}
        for device_id, device in by_id.items():
            reading = last.get(device_id, {})
            data[device_id] = {
                "device": device,
                "label": reading.get("label") or device.get("label") or f"Heater {device_id}",
                "last": reading.get("last_reader") or {},
            }
        return data
