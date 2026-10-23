"""Offline checks for custom_components/starwifi. Run from the repo root inside a Home Assistant environment: python3 tests/test_starwifi.py ."""

import asyncio
from datetime import datetime, timedelta
import json
import sys
from types import SimpleNamespace
from zoneinfo import ZoneInfo

sys.path.insert(0, sys.argv[1])

from homeassistant.components.climate import HVACAction, HVACMode  # noqa: E402
from homeassistant.exceptions import HomeAssistantError  # noqa: E402
from homeassistant.util import dt as dt_util  # noqa: E402
import voluptuous as vol  # noqa: E402  (after homeassistant, which may replace it)

from custom_components.starwifi import api as A  # noqa: E402
from custom_components.starwifi import calendar as CA  # noqa: E402
from custom_components.starwifi import climate as CL  # noqa: E402
from custom_components.starwifi import config_flow  # noqa: E402,F401
from custom_components.starwifi import coordinator as C  # noqa: E402
from custom_components.starwifi import schedule as P  # noqa: E402
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
    # Monday: eco 00-01, comfort 08-09, eco 09-11. Sunday: eco 23-24. Heater 12's plan fails.
    ("GET", f"{B}/api/device/R11/calendar"): (200, [{"dev_option_value": json.dumps({"heat": [
        {"id": "L-00:00", "state": "2"}, {"id": "L-08:00", "state": "1"}, {"id": "L-09:00", "state": "2"},
        {"id": "L-10:00", "state": "2"}, {"id": "D-23:00", "state": "2"}]})}]),
    ("GET", f"{B}/api/device/R12/calendar"): (500, None),
}
ZURICH = ZoneInfo("Europe/Zurich")
MONDAY = datetime(2026, 10, 19, tzinfo=ZURICH)


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
    co.plans, co.plans_at = {}, None
    data = await co._async_update_data()
    check("both heaters listed", set(data) == {"11", "12"})
    check("label from readings", data["11"]["label"] == "Living room")
    check("heater with no reading gets a fallback name", data["12"]["label"] == "Heater 12")
    week = data["11"]["plan"]
    check("plan read as 7 days of 24 hours", len(week) == 7 and all(len(d) == 24 for d in week))
    check("monday plan", week[0] == "2" + "0" * 7 + "122" + "0" * 13)
    check("sunday 23:00 eco", week[6][23] == "2" and week[6][:23] == "0" * 23)
    check("plan that fails to load is None", data["12"]["plan"] is None)

    calls = lambda: sum(1 for c in session.calls if c[1].endswith("/calendar"))  # noqa: E731
    before = calls()
    await co._async_update_data()
    check("plans not re-read within 15 minutes", calls() == before)
    co.plans_at -= timedelta(minutes=16)
    await co._async_update_data()
    check("plans re-read after 15 minutes", calls() == before + 2)

    check("mode at monday 08:30", P.mode_at(week, MONDAY.replace(hour=8, minute=30)) == "comfort")
    check("mode at monday 12:00", P.mode_at(week, MONDAY.replace(hour=12)) == "off")
    check("blocks merge across midnight", P.blocks(week, MONDAY, MONDAY + timedelta(days=1), ZURICH) == [
        (MONDAY - timedelta(hours=1), MONDAY.replace(hour=1), "eco"),
        (MONDAY.replace(hour=8), MONDAY.replace(hour=9), "comfort"),
        (MONDAY.replace(hour=9), MONDAY.replace(hour=11), "eco"),
    ])
    check("no plan stays None", P.week_from_slots(None) is None)

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

    dt_util.set_default_time_zone(ZURICH)
    events = await CA.StarWifiSchedule(fake, "11").async_get_events(None, MONDAY, MONDAY + timedelta(days=1))
    check("calendar events", [(e.summary, e.start.hour, e.end.hour) for e in events] == [
        ("Eco", 23, 1), ("Comfort", 8, 9), ("Eco", 9, 11)])
    check("calendar without a plan unavailable", CA.StarWifiSchedule(fake, "12").available is False)
    planned = S.StarWifiPlannedMode(fake, "11")
    real_now = dt_util.now
    dt_util.now = lambda time_zone=None: MONDAY.replace(hour=9, minute=15)
    try:
        check("planned mode sensor", planned.native_value == "eco")
    finally:
        dt_util.now = real_now
    check("plan followed in AUTO", planned.extra_state_attributes == {"followed": True})
    schedule = CA.StarWifiSchedule(fake, "11")
    check("card gets the week", schedule.extra_state_attributes["week"] == week)

    # The service only takes 7 days of 24 slots, each 0, 1 or 2.
    new_week = ["0" * 7 + "1" * 2 + "2" * 13 + "0" * 2] * 5 + ["1" * 24, "0" * 24]
    check("good week accepted", CA.WEEK_SCHEMA(new_week) == new_week)
    for name, bad_week in [
        ("6 days", new_week[:6]),
        ("23 hours", ["0" * 23] + new_week[1:]),
        ("state 3", ["3" * 24] + new_week[1:]),
    ]:
        try:
            CA.WEEK_SCHEMA(bad_week)
            check(f"week with {name} rejected", False)
        except vol.Invalid:
            check(f"week with {name} rejected", True)

    # Negative control: with the option off, a plan reaches neither the cloud nor the heater.
    before = len(session.calls)
    try:
        await schedule.async_set_schedule(new_week)
        check("plan refused when option off", False)
    except HomeAssistantError:
        check("plan refused when option off", True)
    check("no plan request sent when option off", len(session.calls) == before)

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

    # Positive control: the app's save, then the heater's clock, then one day at a time.
    ROUTES[("POST", f"{B}/api/device/calendar/save")] = (200, {"ok": 1})
    A.PUSH_PAUSE = 0
    updated = []
    fake.plans = {"11": week}
    fake.async_update_listeners = lambda: updated.append(1)
    before = len(session.calls)
    real_now = dt_util.now
    dt_util.now = lambda time_zone=None: MONDAY.replace(hour=9, minute=15, second=7)
    try:
        await schedule.async_set_schedule(new_week)
    finally:
        dt_util.now = real_now
    sent = session.calls[before:]
    heat = [{"id": f"{d}-{h:02d}:00", "state": s} for d, day in zip("LMXJVSD", new_week) for h, s in enumerate(day) if s != "0"]
    check("plan saved like the app", sent[0] == ("POST", f"{B}/api/device/calendar/save", {
        "_method": "PATCH", "device": "R11", "calendar": json.dumps({"heat": heat}, separators=(",", ":"))}))
    check("heater clock sent first", sent[1][2] == {"device": "R11", "component": "datetime", "value": "1,2026-10-19T09:15:07"})
    check("then the 7 days", [c[2]["value"] for c in sent[2:]] == [
        json.dumps({d: s, "action": 1}, separators=(",", ":")) for d, s in zip("LMXJVSD", new_week)])
    check("nothing else sent", len(sent) == 9)
    check("new plan shown at once", schedule.extra_state_attributes["week"] == new_week and fake.plans["11"] == new_week)
    check("entities told", updated == [1])

    # A cloud error becomes a Home Assistant error, and the shown plan does not change.
    ROUTES[("POST", f"{B}/api/device/calendar/save")] = (500, None)
    try:
        await schedule.async_set_schedule(week)
        check("save error reported", False)
    except HomeAssistantError:
        check("save error reported", True)
    check("plan unchanged after error", schedule.extra_state_attributes["week"] == new_week)


asyncio.run(main())
print("FAILURES", failures)
sys.exit(1 if failures else 0)
