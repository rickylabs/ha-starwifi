"""Each heater's weekly plan as a calendar: one event per comfort or eco period.

The service set_schedule writes a new plan to the cloud and the heater, like the app's Save.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import StarWifiConfigEntry
from .api import StarWifiError
from .entity import StarWifiPlanEntity
from .schedule import Week, blocks

SUMMARIES = {"comfort": "Comfort", "eco": "Eco"}

# Monday first; per day 24 hourly slots, "0" off, "1" comfort, "2" eco.
WEEK_SCHEMA = vol.All([vol.Match(r"^[012]{24}$")], vol.Length(min=7, max=7))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StarWifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(StarWifiSchedule(coordinator, device_id) for device_id in coordinator.data)
    entity_platform.async_get_current_platform().async_register_entity_service(
        "set_schedule", {vol.Required("week"): WEEK_SCHEMA}, "async_set_schedule"
    )


class StarWifiSchedule(StarWifiPlanEntity, CalendarEntity):
    _attr_translation_key = "schedule"

    def __init__(self, coordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_schedule"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # "week" feeds the schedule card.
        return {**super().extra_state_attributes, "week": self._week}

    def _events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        if self._week is None:
            return []
        return [
            CalendarEvent(start=s, end=e, summary=SUMMARIES[mode])
            for s, e, mode in blocks(self._week, start, end, dt_util.get_default_time_zone())
        ]

    @property
    def event(self) -> CalendarEvent | None:
        """The period running now, or the next one."""
        now = dt_util.now()
        events = self._events(now, now + timedelta(days=8))
        return events[0] if events else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return self._events(start_date, end_date)

    async def async_set_schedule(self, week: Week) -> None:
        reference = self._control_reference()
        api = self.coordinator.api
        try:
            await api.save_calendar(reference, week)
            await api.push_calendar(reference, week, dt_util.now())
        except StarWifiError as err:
            raise HomeAssistantError(f"Star Wi-Fi plan not saved: {err}") from err
        self.coordinator.plans[self._device_id] = list(week)
        self._entry["plan"] = list(week)
        self.coordinator.async_update_listeners()
