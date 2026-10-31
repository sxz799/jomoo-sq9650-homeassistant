"""按钮实体（一次性动作）."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import JomooCoordinator
from .entity import JomooEntity


@dataclass(frozen=True, kw_only=True)
class ButtonDesc:
    key: str
    name: str
    icon: str
    command: str | None = None  # None = 仅刷新状态
    action: str | None = None  # "connect" / "disconnect"


BUTTONS: tuple[ButtonDesc, ...] = (
    ButtonDesc(key="connect", name="bt01-连接", icon="mdi:bluetooth-connect", action="connect"),
    ButtonDesc(key="disconnect", name="bt02-断开连接", icon="mdi:bluetooth-off", action="disconnect"),
    ButtonDesc(key="flush_small", name="bt03-小冲", icon="mdi:water-outline", command="flush_small"),
    ButtonDesc(key="flush_large", name="bt04-大冲", icon="mdi:water", command="flush_large"),
    ButtonDesc(key="cover_open", name="bt05-翻盖开", icon="mdi:arrow-up-bold-box", command="cover_open"),
    ButtonDesc(key="cover_close", name="bt06-翻盖关", icon="mdi:arrow-down-bold-box", command="cover_close"),
    ButtonDesc(key="ring_open", name="bt07-翻圈开", icon="mdi:arrow-up-bold", command="ring_open"),
    ButtonDesc(key="ring_close", name="bt08-翻圈关", icon="mdi:arrow-down-bold", command="ring_close"),
    ButtonDesc(key="magic_bubble", name="bt09-魔力泡", icon="mdi:chart-bubble", command="magic_bubble"),
    ButtonDesc(key="hibernate", name="bt10-待机", icon="mdi:power-sleep", command="hibernate"),
    ButtonDesc(key="refresh", name="bt11-刷新状态", icon="mdi:refresh", command=None),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: JomooCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(JomooButton(coordinator, desc) for desc in BUTTONS)


class JomooButton(JomooEntity, ButtonEntity):
    def __init__(self, coordinator: JomooCoordinator, desc: ButtonDesc) -> None:
        super().__init__(coordinator, desc.key, desc.name, desc.icon)
        self.desc = desc

    async def async_press(self) -> None:
        if self.desc.action == "connect":
            await self.coordinator.client.async_connect_now()
        elif self.desc.action == "disconnect":
            await self.coordinator.client.async_disconnect()
        elif self.desc.command is None:
            await self.coordinator.async_refresh_state()
        else:
            await self.coordinator.async_send(self.desc.command)
