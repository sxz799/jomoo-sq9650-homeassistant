"""协调器：把实体操作翻译成 BLE 指令并刷新状态."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .client import JomooBleClient
from .const import DOMAIN, LOGGER
from .protocol import COMMANDS, ToiletState


class JomooCoordinator(DataUpdateCoordinator[ToiletState]):
    """无轮询：仅在命令下发/手动刷新时连接并更新状态."""

    def __init__(self, hass: HomeAssistant, client: JomooBleClient, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}-{client.address}",
            update_interval=None,
        )
        self.client = client
        self.entry = entry
        # 乐观状态：马桶不上报的字段（预润湿/久坐提醒）或上报超时时使用
        self.optimistic: dict[str, Any] = {}
        self.connected = False
        client.on_state = self._handle_state
        client.on_connectivity = self._handle_connectivity

    @callback
    def _handle_connectivity(self, connected: bool) -> None:
        """连接状态变化时刷新实体（不改变马桶状态数据）."""
        self.connected = connected
        self.async_update_listeners()

    @callback
    def _handle_state(self, state: ToiletState) -> None:
        # 上报里存在的字段，以真实状态为准，清掉对应的乐观值
        self.optimistic = {
            key: value
            for key, value in self.optimistic.items()
            if not hasattr(state, key)
        }
        self.async_set_updated_data(state)

    async def async_send(
        self,
        command: str,
        optimistic_key: str | None = None,
        optimistic_value: Any = None,
    ) -> None:
        """下发语义命令，并尽量刷新一次真实状态."""
        if optimistic_key is not None:
            self.optimistic[optimistic_key] = optimistic_value
            self.async_update_listeners()

        await self.client.async_send(COMMANDS[command])
        await self.async_refresh_state()

    async def async_refresh_state(self) -> None:
        state = await self.client.async_query_state()
        if state is not None:
            self._handle_state(state)
