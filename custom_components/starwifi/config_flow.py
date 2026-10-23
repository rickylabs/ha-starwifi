"""Sign in once with the Star Wi-Fi app's email and password."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import StarWifiApi, StarWifiAuthError, StarWifiError
from .const import CONF_ALLOW_CONTROL, CONF_USER_ID, DOMAIN

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL)),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class StarWifiConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            api = StarWifiApi(async_get_clientsession(self.hass))
            try:
                user = await api.login(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            except StarWifiAuthError:
                errors["base"] = "invalid_auth"
            except StarWifiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(str(user["id"]))
                self._abort_if_unique_id_configured()
                # The cloud needs only the account id after login, so the password is not stored.
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data={CONF_USER_ID: str(user["id"])}
                )
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return StarWifiOptionsFlow()


class StarWifiOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_ALLOW_CONTROL, False)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required(CONF_ALLOW_CONTROL, default=current): bool}),
        )
