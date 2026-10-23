"""Small client for the Star Wi-Fi cloud (ccdatos), as the Android app 1.6.2 uses it.

Login returns the account; every later call needs only the account id or a
device reference, with no token.
"""

from __future__ import annotations

from typing import Any

import aiohttp

from .const import API_BASE, CONTROL_URL

TIMEOUT = aiohttp.ClientTimeout(total=15)


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

    async def control(self, reference: str, component: str, value: Any) -> None:
        await self._request(
            "POST",
            CONTROL_URL,
            {"device": reference, "component": component, "value": value},
        )
