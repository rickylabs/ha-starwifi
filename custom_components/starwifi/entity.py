"""Base entity: one HA device per heater."""

from __future__ import annotations

from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ALLOW_CONTROL, DOMAIN
from .coordinator import StarWifiCoordinator, is_on
from .schedule import Week


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

    def _control_reference(self) -> str:
        """The heater's reference, once we know the user allowed control. Checked before anything is sent."""
        if not self.coordinator.config_entry.options.get(CONF_ALLOW_CONTROL, False):
            raise HomeAssistantError(
                "Star Wi-Fi control is off. Turn on 'Allow control' in the integration options."
            )
        reference = self._entry.get("device", {}).get("reference")
        if not reference:
            raise HomeAssistantError("This heater has no reference in the cloud data")
        return reference


class StarWifiPlanEntity(StarWifiEntity):
    """Shows the weekly plan saved in the cloud, so it stays available while the heater is offline."""

    @property
    def _week(self) -> Week | None:
        return self._entry.get("plan")

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self._week is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # The heater follows its plan only in mode AUTO.
        return {"followed": str(self._last.get("mode") or "").upper() == "AUTO"}
