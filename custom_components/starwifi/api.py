"""Small client for the Star Wi-Fi cloud (ccdatos), as the Android app 1.6.2 uses it.

Login returns the account; every later call needs only the account id or a
device reference, with no token.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
import json
from typing import Any

import aiohttp

from .const import API_BASE, CONTROL_URL
from .schedule import DAYS, OFF, Week

TIMEOUT = aiohttp.ClientTimeout(total=15)
# The app waits 3 seconds between the days it sends to a heater.
PUSH_PAUSE = 3


def _compact(value: Any) -> str:
    """JSON text as the app's JSON.stringify writes it, with no spaces."""
    return json.dumps(value, separators=(",", ":"))


class StarWifiError(Exception):
    """The cloud could not be reached or answered with an error."""


class StarWifiAuthError(StarWifiError):
    """Wrong email or password."""


class StarWifiApi:
    """Calls used by the app's login, device list, readings and control screens."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def _request(self, method: str, url: str, body: dict | None = None) -> Any:
        headers = {"Content-Type": "application/json", "lang": "fr"} if body is not None else None
        try:
            async with self._session.request(
                method, url, json=body, headers=headers, timeout=TIMEOUT
            ) as resp:
                if resp.status == 401:
                    raise StarWifiAuthError
                if resp.status >= 400:
                    raise StarWifiError(f"{method} {url} answered HTTP {resp.status}")
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise StarWifiError(f"{method} {url} failed: {err}") from err

    async def login(self, email: str, password: str) -> dict[str, Any]:
        user = await self._request(
            "POST", f"{API_BASE}/api/user/login", {"email": email, "password": password}
        )
        if not isinstance(user, dict) or not user.get("id"):
            raise StarWifiAuthError
        return user

    async def devices(self, user_id: str) -> list[dict[str, Any]]:
        return await self._request("GET", f"{API_BASE}/api/user/{user_id}/devices") or []

    async def last_readings(self, device_ids: list[str]) -> list[dict[str, Any]]:
        ids = "-".join(device_ids)
        return await self._request("GET", f"{API_BASE}/api/deviceLastMulti/{ids}") or []

    async def calendar(self, reference: str) -> dict[str, str] | None:
        """Weekly plan as {"L-08:00": "1", ...}, or None when the app never saved one."""
        rows = await self._request("GET", f"{API_BASE}/api/device/{reference}/calendar")
        row = rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else {}
        value = row.get("dev_option_value")
        if not value:
            return None
        try:
            slots = json.loads(value)["heat"]
            return {str(s["id"]): str(s["state"]) for s in slots}
        except (ValueError, KeyError, TypeError) as err:
            raise StarWifiError(f"unreadable plan for {reference}: {err}") from err

    async def save_calendar(self, reference: str, week: Week) -> None:
        """Store the plan in the cloud, as the app does: only the slots that are not off."""
        heat = [
            {"id": f"{day}-{hour:02d}:00", "state": state}
            for day, states in zip(DAYS, week)
            for hour, state in enumerate(states)
            if state != OFF
        ]
        await self._request(
            "POST",
            f"{API_BASE}/api/device/calendar/save",
            {"_method": "PATCH", "device": reference, "calendar": _compact({"heat": heat})},
        )

    async def push_calendar(self, reference: str, week: Week, now: datetime) -> None:
        """Send the plan to the heater as the app does: its clock first, then one day every 3 seconds."""
        # The app sends JavaScript's getDay(): 0 is Sunday.
        await self.control(reference, "datetime", f"{(now.weekday() + 1) % 7},{now:%Y-%m-%dT%H:%M:%S}")
        for day, states in zip(DAYS, week):
            await asyncio.sleep(PUSH_PAUSE)
            await self.control(reference, "calendar", _compact({day: states, "action": 1}))

    async def day_consumption(self, reference: str, day: date) -> dict[int, float]:
        """Energy of one local day from the app's history, as {hour: kWh}.

        One row per hour, stamped with the hour's local start. An hour with no use
        has no row, and an hour shows up only once it is over.
        """
        body = await self._request(
            "POST",
            f"{API_BASE}/api/device/history/temperatura",
            {"reference": reference, "year": f"{day:%Y}", "month": f"{day:%m}", "day": f"{day:%d}"},
        )
        rows = body.get("consumptions") if isinstance(body, dict) else None
        hours: dict[int, float] = {}
        for row in rows or []:
            try:
                stamp = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
                kwh = float(row["power_consumption"])
            except (KeyError, TypeError, ValueError):
                continue
            if stamp.date() == day:
                hours[stamp.hour] = hours.get(stamp.hour, 0.0) + kwh
        return hours

    async def control(self, reference: str, component: str, value: Any) -> None:
        await self._request(
            "POST",
            CONTROL_URL,
            {"device": reference, "component": component, "value": value},
        )
