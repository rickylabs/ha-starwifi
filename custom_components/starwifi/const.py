"""Constants for the Star Wi-Fi (Climastar) integration."""

DOMAIN = "starwifi"

# Taken from the Star Wi-Fi Android app 1.6.2 (src/providers/ccdatos/ccdatos.ts).
API_BASE = "https://starwifi.ccdatos.com"
CONTROL_URL = "https://starwifi.ccdatos.com:1880/control"

CONF_USER_ID = "user_id"
CONF_ALLOW_CONTROL = "allow_control"

MIN_TEMP = 5.0
MAX_TEMP = 30.0
TEMP_STEP = 0.5
