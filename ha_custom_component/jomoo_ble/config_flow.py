"""配置流程：蓝牙自动发现 + 手动填 MAC."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
)
from homeassistant.config_entries import ConfigFlow

try:  # HA >= 2024.4
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:  # 旧版 HA
    from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult

from homeassistant.helpers.device_registry import format_mac

from .const import CONF_ADDRESS, DEFAULT_ADDRESS, DOMAIN


class JomooBleConfigFlow(ConfigFlow, domain=DOMAIN):
    """添加九牧马桶."""

    VERSION = 1

    def __init__(self) -> None:
        self._address: str | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """蓝牙广播自动发现（Service UUID FFE0）."""
        address = discovery_info.address
        await self.async_set_unique_id(format_mac(address))
        self._abort_if_unique_id_configured()
        self._address = address
        self.context["title_placeholders"] = {
            "name": discovery_info.name or address
        }
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """确认添加发现的设备."""
        assert self._address is not None
        name = self.context.get("title_placeholders", {}).get(
            "name", self._address
        )
        if user_input is not None:
            return self.async_create_entry(
                title=f"九牧马桶 {name}", data={CONF_ADDRESS: self._address}
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"name": name, "address": self._address},
        )

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """手动输入 MAC."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            if async_ble_device_from_address(self.hass, address, connectable=True) is None:
                errors["base"] = "not_found"
            else:
                await self.async_set_unique_id(format_mac(address), raise_on_progress=False)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"九牧马桶 {address[-5:]}", data={CONF_ADDRESS: address}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS, default=DEFAULT_ADDRESS): str,
                }
            ),
            errors=errors,
        )
