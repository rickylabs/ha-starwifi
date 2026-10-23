"""Star Wi-Fi (Climastar) heaters, through the ccdatos cloud."""

from __future__ import annotations

import hashlib
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .api import StarWifiApi
from .const import DOMAIN
from .coordinator import StarWifiCoordinator
from .energy import ENERGY_INTERVAL, EnergyImporter

PLATFORMS = [Platform.CALENDAR, Platform.CLIMATE, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CARD_URL = f"/{DOMAIN}_frontend"
CARD_FILE = "starwifi-schedule-card.js"

type StarWifiConfigEntry = ConfigEntry[StarWifiCoordinator]


def card_hash(path: Path) -> str:
    """First 8 hex digits of the card file's SHA-256."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the schedule card and load it on every dashboard."""
    frontend = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(frontend), True)])
    # Browsers keep this file for a month, so the URL carries the file's own
    # hash: any change to the card, even within one version, is fetched anew.
    version = await hass.async_add_executor_job(card_hash, frontend / CARD_FILE)
    add_extra_js_url(hass, f"{CARD_URL}/{CARD_FILE}?v={version}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: StarWifiConfigEntry) -> bool:
    coordinator = StarWifiCoordinator(hass, entry, StarWifiApi(async_get_clientsession(hass)))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    energy = EnergyImporter(hass, coordinator)
    entry.async_on_unload(async_track_time_interval(hass, energy.start, ENERGY_INTERVAL))
    energy.start()
    return True


async def _async_reload(hass: HomeAssistant, entry: StarWifiConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: StarWifiConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
