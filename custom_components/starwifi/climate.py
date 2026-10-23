"""One thermostat per heater. Changes are refused unless the "allow control" option is on."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import StarWifiConfigEntry
from .api import StarWifiError
from .const import MAX_TEMP, MIN_TEMP, TEMP_STEP
from .coordinator import is_on, to_float
from .entity import StarWifiEntity

# The app's two modes: MANUAL holds the setpoint, AUTO follows the app's schedule.
PRESETS = {"manual": "MANUAL", "auto": "AUTO"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StarWifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(StarWifiClimate(coordinator, device_id) for device_id in coordinator.data)


class StarWifiClimate(StarWifiEntity, ClimateEntity):
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = list(PRESETS)
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = TEMP_STEP
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_climate"

    @property
    def current_temperature(self) -> float | None:
        return to_float(self._last.get("temperature"))

    @property
    def target_temperature(self) -> float | None:
        return to_float(self._last.get("consigna"))

    @property
    def hvac_mode(self) -> HVACMode | None:
        if self._last.get("power") is None:
            return None
        return HVACMode.HEAT if is_on(self._last.get("power")) else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if self._last.get("heat") is None:
            return None
        return HVACAction.HEATING if is_on(self._last.get("heat")) else HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        mode = str(self._last.get("mode") or "").upper()
        return next((k for k, v in PRESETS.items() if v == mode), None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "window": self._last.get("window"),
            "away": self._last.get("ausente"),
            "reference": self._entry.get("device", {}).get("reference"),
        }

    async def _send(self, component: str, value: Any) -> None:
        reference = self._control_reference()
        try:
            await self.coordinator.api.control(reference, component, value)
        except StarWifiError as err:
            raise HomeAssistantError(f"Star Wi-Fi command failed: {err}") from err
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self._send("consigna", float(temperature))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self._send("power", "ON" if hvac_mode == HVACMode.HEAT else "OFF")

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self._send("mode", PRESETS[preset_mode])
