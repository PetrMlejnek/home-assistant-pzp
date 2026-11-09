"""Credentials are entered in HA and stored only in its config entry."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from . import DOMAIN
from .client import AuthError, PzpClient, PzpError, UnsupportedFirmware, normalize_host


class PzpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                user_input = {**user_input, 'host': normalize_host(user_input['host'])}
                await self.async_set_unique_id(user_input['host'])
                self._abort_if_unique_id_configured()
                for entry in self._async_current_entries():
                    if normalize_host(entry.data['host']) == user_input['host']:
                        return self.async_abort(reason='already_configured')
                client = await self.hass.async_add_executor_job(
                    PzpClient, user_input["host"], user_input["username"], user_input["password"]
                )
                await self.hass.async_add_executor_job(client.read_state)
            except AuthError:
                errors["base"] = "invalid_auth"
            except UnsupportedFirmware:
                errors["base"] = "unsupported_firmware"
            except (PzpError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=f"PZP ({user_input['host']})", data=user_input)
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("host"): str,
            vol.Required("username"): str,
            vol.Required("password"): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
        }), errors=errors)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        entry = self._get_reauth_entry()
        errors = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            try:
                client = await self.hass.async_add_executor_job(
                    PzpClient, data["host"], data["username"], data["password"]
                )
                await self.hass.async_add_executor_job(client.read_state)
            except AuthError:
                errors["base"] = "invalid_auth"
            except UnsupportedFirmware:
                errors["base"] = "unsupported_firmware"
            except (PzpError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(step_id="reauth_confirm", data_schema=vol.Schema({
            vol.Required("username", default=entry.data["username"]): str,
            vol.Required("password"): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
        }), errors=errors)
