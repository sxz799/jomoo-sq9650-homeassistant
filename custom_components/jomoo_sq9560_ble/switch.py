"""开关实体（0x40H / 0x41H 双值指令）."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import JomooCoordinator
from .entity import JomooEntity


@dataclass(frozen=True, kw_only=True)
class SwitchDesc:
    key: str
    name: str
    on: str
    off: str
    icon: str
    attr: str | None  # ToiletState 字段名；None 表示该功能不上报状态


SWITCHES: tuple[SwitchDesc, ...] = (
    SwitchDesc(key="auto_flush", name="sw01-自动冲刷", on="auto_flush_on", off="auto_flush_off",
               icon="mdi:water-sync", attr="auto_flush"),
    SwitchDesc(key="close_cover_flush", name="sw02-关盖冲厕", on="close_cover_flush_on", off="close_cover_flush_off",
               icon="mdi:toilet", attr="close_cover_flush"),
    SwitchDesc(key="foot", name="sw03-脚感控制", on="foot_on", off="foot_off",
               icon="mdi:shoe-print", attr="foot_sensor"),
    SwitchDesc(key="night", name="sw04-夜灯", on="night_light_on", off="night_light_off",
               icon="mdi:lightbulb", attr="night_light"),
    SwitchDesc(key="light_sensor", name="sw05-智能夜灯", on="light_sensor_on", off="light_sensor_off",
               icon="mdi:brightness-auto", attr="light_sensor"),
    SwitchDesc(key="pre_wetting", name="sw06-预润湿", on="pre_wetting_on", off="pre_wetting_off",
               icon="mdi:water-percent", attr="pre_wetting"),
    SwitchDesc(key="seat_bubble", name="sw07-落座发泡", on="seat_bubble_on", off="seat_bubble_off",
               icon="mdi:chart-bubble", attr=None),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: JomooCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(JomooSwitch(coordinator, desc) for desc in SWITCHES)


class JomooSwitch(JomooEntity, SwitchEntity):
    def __init__(self, coordinator: JomooCoordinator, desc: SwitchDesc) -> None:
        super().__init__(coordinator, desc.key, desc.name, desc.icon)
        self.desc = desc
        # 乐观状态键：优先用状态字段名，便于上报到达后自动清除
        self._opt_key = desc.attr or desc.key

    @property
    def is_on(self) -> bool | None:
        if self._opt_key in self.coordinator.optimistic:
            return bool(self.coordinator.optimistic[self._opt_key])
        state = self.state_obj
        if state is None or not state.valid or self.desc.attr is None:
            return None
        return getattr(state, self.desc.attr)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_send(self.desc.on, self._opt_key, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_send(self.desc.off, self._opt_key, False)
