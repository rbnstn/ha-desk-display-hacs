"""Add a flashed display through HA's integration dialog."""

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from .client import DisplayClient
from .const import DOMAIN

SCHEMA = vol.Schema({
    vol.Required("host"): str,
    vol.Required("key"): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
})


class DeskDisplayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                info = await DisplayClient(async_get_clientsession(self.hass),
                                           user_input["host"], user_input["key"]).info()
            except aiohttp.ClientResponseError as err:
                errors["base"] = "invalid_auth" if err.status == 401 else "cannot_connect"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except ValueError:
                errors["base"] = "invalid_device"
            else:
                await self.async_set_unique_id(info["id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Desk Display", data=user_input)
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)

    async def async_step_reconfigure(self, user_input=None):
        errors = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            try:
                info = await DisplayClient(async_get_clientsession(self.hass),
                                           user_input["host"], user_input["key"]).info()
                if info["id"] != entry.unique_id:
                    raise ValueError("Anderes Display")
            except aiohttp.ClientResponseError as err:
                errors["base"] = "invalid_auth" if err.status == 401 else "cannot_connect"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except ValueError:
                errors["base"] = "invalid_device"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(step_id="reconfigure", data_schema=SCHEMA, errors=errors)
