"""Room temperature per heater, kept as a sensor for long-term statistics, and the plan's mode now."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import StarWifiConfigEntry
from .coordinator import to_float
from .entity import StarWifiEntity, StarWifiPlanEntity
from .schedule import MODES, mode_at


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StarWifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(StarWifiTemperature(coordinator, device_id) for device_id in coordinator.data)
    async_add_entities(StarWifiPlannedMode(coordinator, device_id) for device_id in coordinator.data)


class StarWifiTemperature(StarWifiEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_temperature"
        self._attr_translation_key = "room_temperature"

    @property
    def native_value(self) -> float | None:
        return to_float(self._last.get("temperature"))


class StarWifiPlannedMode(StarWifiPlanEntity, SensorEntity):
    """What the weekly plan asks for right now: comfort, eco or off."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(MODES.values())

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_planned_mode"
        self._attr_translation_key = "planned_mode"

    @property
    def native_value(self) -> str | None:
        return mode_at(self._week, dt_util.now()) if self._week else None
