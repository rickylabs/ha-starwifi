# Star Wi-Fi (Climastar) for Home Assistant

Brings Climastar electric heaters that you run from the **Star Wi-Fi** app (by Perfect Numbers) into Home Assistant.

Your heaters are on the Helki cloud instead (app "Climastar Smartbox")? Use [hass-smartbox](https://github.com/ajtudela/hass-smartbox).

Unofficial. Not made or supported by Climastar or Perfect Numbers.

## What you get

For each heater in your account:

- A thermostat: room temperature, setpoint, on/off, heating or idle, and preset `manual` or `auto`.
- A room temperature sensor, for history and graphs.
- Extra attributes: `window`, `away` and `reference`.

Values refresh every 60 seconds. A heater that the app shows as offline shows as unavailable.

## Install

**HACS:** HACS → three dots → Custom repositories → add `https://github.com/rickylabs/ha-starwifi`, type Integration. Download "Star Wi-Fi (Climastar)", then restart Home Assistant.

**Manual:** copy `custom_components/starwifi` into the `custom_components` folder of your Home Assistant config, then restart.

## Set up

Settings → Devices & services → Add integration → **Star Wi-Fi (Climastar)**. Sign in with the email and password of the Star Wi-Fi app.

The password is used once to find your account. It is not stored.

## Control is off by default

Out of the box, Home Assistant only reads your heaters. To change setpoint, preset and on/off from Home Assistant, open the integration, press **Configure** and turn on **Allow control**.

With it off, any change from Home Assistant is refused and nothing is sent to the cloud.

## Limits

- Cloud only. Needs internet.
- Setpoint: 5 to 30 °C, in 0.5 °C steps.
- Weekly schedules, groups and history from the app are not in Home Assistant yet.
- Control sends the same commands as the app. Setpoint changes are tested on a real heater. On/off and preset are not tested on a real heater yet: please open an issue if one does not work.

## Tests

The tests run offline, with no account. Run them from the repo root, in a Python environment that has Home Assistant installed:

```bash
python3 tests/test_starwifi.py .
```

## License

MIT
