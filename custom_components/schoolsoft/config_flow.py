"""Configuration flow for SchoolSoft."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import SchoolSoftClient, SchoolSoftAuthenticationError
from .const import CONF_ICAL_URL, CONF_SCHOOL_URL, CONF_STUDENT_NAME, DEFAULT_SCHOOL_URL, DEFAULT_STUDENT_NAME, DOMAIN


class SchoolSoftConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle SchoolSoft configuration."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**user_input, CONF_SCHOOL_URL: user_input[CONF_SCHOOL_URL].rstrip("/")}
            try:
                client = SchoolSoftClient(async_get_clientsession(self.hass), data)
                await client.async_login()
                await self.async_set_unique_id(f"{data[CONF_SCHOOL_URL]}:{data[CONF_USERNAME]}")
                self._abort_if_unique_id_configured()
            except SchoolSoftAuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=f"{data[CONF_STUDENT_NAME]} School", data=data)

        schema = vol.Schema({
            vol.Required(CONF_STUDENT_NAME, default=DEFAULT_STUDENT_NAME): str,
            vol.Required(CONF_SCHOOL_URL, default=DEFAULT_SCHOOL_URL): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SchoolSoftOptionsFlow(config_entry)


class SchoolSoftOptionsFlow(OptionsFlow):
    """Configure optional SchoolSoft sources."""

    def __init__(self, config_entry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data={CONF_ICAL_URL: user_input[CONF_ICAL_URL].strip()})
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_ICAL_URL, default=self.config_entry.options.get(CONF_ICAL_URL, "")): str,
            }),
        )
