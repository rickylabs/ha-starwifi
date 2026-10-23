"""Offline checks for custom_components/starwifi. Run from the repo root inside a Home Assistant environment: python3 tests/test_starwifi.py ."""

import asyncio
import sys
from types import SimpleNamespace

sys.path.insert(0, sys.argv[1])

from homeassistant.components.climate import HVACAction, HVACMode  # noqa: E402
from homeassistant.exceptions import HomeAssistantError  # noqa: E402

from custom_components.starwifi import api as A  # noqa: E402
from custom_components.starwifi import climate as CL  # noqa: E402
from custom_components.starwifi import config_flow  # noqa: E402,F401
from custom_components.starwifi import coordinator as C  # noqa: E402
from custom_components.starwifi import sensor as S  # noqa: E402

failures = 0


def check(name, cond):
    global failures
    print(("PASS " if cond else "FAIL ") + name)
    failures += 0 if cond else 1


class FakeResp:
    def __init__(self, status, body):
        self.status, self._body = status, body

    async def json(self, content_type=None):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def request(self, method, url, json=None, headers=None, timeout=None):
        self.calls.append((method, url, json))
        status, body = self.routes.get((method, url), (404, None))
        return FakeResp(status, body)


B = A.API_BASE
ROUTES = {
    ("POST", f"{B}/api/user/login"): (200, {"id": 77, "app_id": 3}),
    ("GET", f"{B}/api/user/77/devices"): (200, [{"id": 11, "reference": "R11"}, {"id": 12, "reference": "R12"}]),
    ("GET", f"{B}/api/deviceLastMulti/11-12"): (
        200,
        [{"id": 11, "label": "Living room", "last_reader": {
            "temperature": "20.5", "consigna": "21", "power": "ON", "heat": "1",
            "mode": "AUTO", "connect": True, "window": "OFF", "ausente": 0}}],
    ),
    ("POST", A.CONTROL_URL): (200, {"ok": 1}),
}


async def main():
    session = FakeSession(ROUTES)
    api = A.StarWifiApi(session)

    bad = A.StarWifiApi(FakeSession({("POST", f"{B}/api/user/login"): (401, "Usuario o contraseña incorrectos.")}))
    try:
        await bad.login("a@b.c", "x")
        check("login 401 raises auth error", False)
    except A.StarWifiAuthError:
        check("login 401 raises auth error", True)
    check("login returns the account id", (await api.login("a@b.c", "pw"))["id"] == 77)

    co = object.__new__(C.StarWifiCoordinator)
    co.api, co.user_id = api, "77"
    data = await co._async_update_data()
    check("both heaters listed", set(data) == {"11", "12"})
    check("label from readings", data["11"]["label"] == "Living room")
    check("heater with no reading gets a fallback name", data["12"]["label"] == "Heater 12")

    refreshed = []

    async def refresh():
        refreshed.append(1)

    fake = SimpleNamespace(
        data=data, api=api, last_update_success=True, user_id="77",
        config_entry=SimpleNamespace(options={}), async_request_refresh=refresh,
    )
    living = CL.StarWifiClimate(fake, "11")
    other = CL.StarWifiClimate(fake, "12")
    check("room temperature", living.current_temperature == 20.5)
    check("setpoint", living.target_temperature == 21.0)
    check("power ON -> heat", living.hvac_mode == HVACMode.HEAT)
    check("heat 1 -> heating", living.hvac_action == HVACAction.HEATING)
    check("mode AUTO -> preset auto", living.preset_mode == "auto")
    check("connected heater available", living.available is True)
    check("heater with no reading unavailable", other.available is False)
    check("temperature sensor", S.StarWifiTemperature(fake, "11").native_value == 20.5)

    # Negative control: with the option off, nothing reaches the cloud.
    before = len(session.calls)
    try:
        await living.async_set_temperature(temperature=19.5)
        check("control refused when option off", False)
    except HomeAssistantError:
        check("control refused when option off", True)
    check("no request sent when option off", len(session.calls) == before)

    # Positive control: with the option on, the app's exact command goes out.
    fake.config_entry.options = {"allow_control": True}
    await living.async_set_temperature(temperature=19.5)
    check("setpoint command sent", session.calls[-1] == (
        "POST", A.CONTROL_URL, {"device": "R11", "component": "consigna", "value": 19.5}))
    await living.async_turn_off()
    check("off command sent", session.calls[-1][2] == {"device": "R11", "component": "power", "value": "OFF"})
    check("refresh after command", len(refreshed) == 2)


asyncio.run(main())
print("FAILURES", failures)
sys.exit(1 if failures else 0)
