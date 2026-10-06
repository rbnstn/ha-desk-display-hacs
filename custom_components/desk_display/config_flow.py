"""Add a flashed display through HA's integration dialog."""

import aiohttp
import re
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
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

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo):
        device_id=discovery_info.properties.get('id','')
        if not isinstance(device_id,str) or not re.fullmatch(r'[0-9a-f]{12}',device_id) or discovery_info.properties.get('model')!='E32R35T':
            return self.async_abort(reason='invalid_device')
        host=discovery_info.host
        for entry in self._async_current_entries():
            if entry.unique_id==device_id:
                # Discovery packets alone must never redirect an existing device key.
                if entry.data['host']!=host:
                    try:
                        info=await DisplayClient(async_get_clientsession(self.hass),host,entry.data['key']).info()
                        if info['id']==device_id:
                            self.hass.config_entries.async_update_entry(entry,data={**entry.data,'host':host})
                            await self.hass.config_entries.async_reload(entry.entry_id)
                    except (aiohttp.ClientError,TimeoutError,ValueError):pass
                return self.async_abort(reason='already_configured')
        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured()
        self.discovered_host=host
        self.context['title_placeholders']={'name':f'Desk Display ({host})'}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self,user_input=None):
        errors={}
        if user_input is not None:
            try:
                info=await DisplayClient(async_get_clientsession(self.hass),self.discovered_host,user_input['key']).info()
                if info['id']!=self.unique_id:raise ValueError('Anderes Display')
            except aiohttp.ClientResponseError as error:errors['base']='invalid_auth' if error.status==401 else 'cannot_connect'
            except (aiohttp.ClientError,TimeoutError):errors['base']='cannot_connect'
            except ValueError:errors['base']='invalid_device'
            else:
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title='Desk Display',data={'host':self.discovered_host,'key':user_input['key']})
        return self.async_show_form(step_id='discovery_confirm',data_schema=vol.Schema({vol.Required('key'):selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))}),errors=errors,description_placeholders={'host':self.discovered_host})

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

