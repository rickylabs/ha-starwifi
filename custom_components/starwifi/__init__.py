"""Star Wi-Fi (Climastar) heaters, through the ccdatos cloud."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import StarWifiApi
from .const import DOMAIN
from .coordinator import StarWifiCoordinator

PLATFORMS = [Platform.CALENDAR, Platform.CLIMATE, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CARD_URL = f"/{DOMAIN}_frontend"
CARD_FILE = "starwifi-schedule-card.js"

type StarWifiConfigEntry = ConfigEntry[StarWifiCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the schedule card and load it on every dashboard."""
    integration = await async_get_integration(hass, DOMAIN)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(Path(__file__).parent / "frontend"), True)]
    )
    # The version in the URL makes browsers fetch the new card after an update.
    add_extra_js_url(hass, f"{CARD_URL}/{CARD_FILE}?v={integration.version}")
    return True


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
