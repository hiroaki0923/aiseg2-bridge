from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from . import AiSeg2Client, AiSeg2Config
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DEFAULT_USER, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Optional("username", default=DEFAULT_USER): str,
        vol.Optional("password", default=""): str,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(int, vol.Range(min=30, max=3600))}
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            # 接続テスト
            cfg = AiSeg2Config(
                host=user_input["host"],
                user=user_input.get("username", DEFAULT_USER),
                password=user_input.get("password", ""),
                timeout=10.0,
            )
            client = AiSeg2Client(cfg)
            try:
                # 軽いリクエストで疎通確認
                await client.fetch_circuit_catalog()
                await client.close()
                return self.async_create_entry(
                    title=f"AiSEG2 ({cfg.host})",
                    data={
                        "host": cfg.host,
                        "username": cfg.user,
                        "password": cfg.password,
                    },
                )
            except Exception:
                await client.close()
                errors["base"] = "cannot_connect"

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        return await self.async_step_user(user_input)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return await self.async_step_user(user_input)

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="options", data_schema=OPTIONS_SCHEMA)

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry):
        self._entry = entry

    async def async_step_init(self, user_input=None):
        return await self.async_step_options(user_input)

    async def async_step_options(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="options", data_schema=OPTIONS_SCHEMA)
