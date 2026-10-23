"""Room temperature per heater, kept as a sensor for long-term statistics."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import StarWifiConfigEntry
from .coordinator import to_float
from .entity import StarWifiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StarWifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(StarWifiTemperature(coordinator, device_id) for device_id in coordinator.data)


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
