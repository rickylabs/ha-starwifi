"""Base entity: one HA device per heater."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StarWifiCoordinator, is_on


class StarWifiEntity(CoordinatorEntity[StarWifiCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: StarWifiCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=coordinator.data[device_id]["label"],
            manufacturer="Climastar",
            model="Star Wi-Fi heater",
        )

    @property
    def _entry(self) -> dict[str, Any]:
        return self.coordinator.data.get(self._device_id, {})

    @property
    def _last(self) -> dict[str, Any]:
        return self._entry.get("last", {})

    @property
    def available(self) -> bool:
        return super().available and is_on(self._last.get("connect"))
