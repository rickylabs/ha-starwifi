"""Star Wi-Fi (Climastar) heaters, through the ccdatos cloud."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import StarWifiApi
from .coordinator import StarWifiCoordinator

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]

type StarWifiConfigEntry = ConfigEntry[StarWifiCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: StarWifiConfigEntry) -> bool:
    coordinator = StarWifiCoordinator(hass, entry, StarWifiApi(async_get_clientsession(hass)))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: StarWifiConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: StarWifiConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
