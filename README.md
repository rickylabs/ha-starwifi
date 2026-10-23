# Star Wi-Fi (Climastar) for Home Assistant

Brings Climastar electric heaters that you run from the **Star Wi-Fi** app (by Perfect Numbers) into Home Assistant.

Your heaters are on the Helki cloud instead (app "Climastar Smartbox")? Use [hass-smartbox](https://github.com/ajtudela/hass-smartbox).

Unofficial. Not made or supported by Climastar or Perfect Numbers.

## What you get

For each heater in your account:

- A thermostat: room temperature, setpoint, on/off, heating or idle, and preset `manual` or `auto`.
- A room temperature sensor, for history and graphs.
- A **schedule** calendar: the weekly plan saved in the app, one event per comfort or eco period.
- A **planned mode** sensor: what the plan says right now (`comfort`, `eco` or `off`).
- Extra attributes: `window`, `away` and `reference`.

Values refresh every 60 seconds; plans every 15 minutes. A heater that the app shows as offline shows as unavailable.

A heater follows its plan only in `auto`. In `manual` it keeps its setpoint, and the plan sensor says `followed: false`.

## Weekly plan card

The integration ships a card to view and edit the weekly plan, like the app: 7 days, 24 hours, comfort / eco / off per hour.

Add it to a dashboard: Edit → Add card → Manual, then:

```yaml
type: custom:starwifi-schedule-card
# entity: calendar.living_room_schedule   # optional: one heater only
# title: Heating plan                     # optional
```

Without `entity`, the card shows a heater picker. Paint hours with the Comfort / Eco / Off brush, tap a day name to fill the whole day, or copy one day to the weekdays, the weekend or all days. **Save** stores the plan in the cloud and sends it to the heater, as the app does. It takes about 20 seconds.

Saving needs **Allow control** (see below). The same thing is available as the service `starwifi.set_schedule`, with `week` as 7 strings of 24 digits, Monday first: `0` off, `1` comfort, `2` eco.

After an update and restart, a page that was already open still has the old card. Reload it once (in the mobile app: close and reopen it).

## Install

**HACS:** HACS → three dots → Custom repositories → add `https://github.com/rickylabs/ha-starwifi`, type Integration. Download "Star Wi-Fi (Climastar)", then restart Home Assistant.

**Manual:** copy `custom_components/starwifi` into the `custom_components` folder of your Home Assistant config, then restart.

## Set up

Settings → Devices & services → Add integration → **Star Wi-Fi (Climastar)**. Sign in with the email and password of the Star Wi-Fi app.

The password is used once to find your account. It is not stored.

## Control is off by default

Out of the box, Home Assistant only reads your heaters. To change setpoint, preset, on/off and the weekly plan from Home Assistant, open the integration, press **Configure** and turn on **Allow control**.

With it off, any change from Home Assistant is refused and nothing is sent to the cloud.

## Limits

- Cloud only. Needs internet.
- Setpoint: 5 to 30 °C, in 0.5 °C steps.
- Plans are hourly, like the app. Groups and history from the app are not in Home Assistant yet.
- Control sends the same commands as the app. Setpoint changes and plan saving are tested on a real heater. On/off and preset are not tested on a real heater yet: please open an issue if one does not work.

## Tests

The tests run offline, with no account. Run them from the repo root, in a Python environment that has Home Assistant installed:

```bash
python3 tests/test_starwifi.py .
```

## License

MIT
