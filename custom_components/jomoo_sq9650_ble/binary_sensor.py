"""二进制传感器（状态上报 0x30）."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import JomooCoordinator
from .entity import JomooEntity


@dataclass(frozen=True, kw_only=True)
class BinaryDesc:
    key: str
    name: str
    icon: str
    device_class: BinarySensorDeviceClass | None
    read: str | None  # ToiletState 属性名；None 表示蓝牙连接状态


BINARY_SENSORS: tuple[BinaryDesc, ...] = (
    BinaryDesc(key="connected", name="蓝牙连接", icon="mdi:bluetooth",
               device_class=BinarySensorDeviceClass.CONNECTIVITY, read=None),
    BinaryDesc(key="on_seat", name="着座", icon="mdi:human-male",
               device_class=BinarySensorDeviceClass.OCCUPANCY, read="on_seat"),
    BinaryDesc(key="cover", name="盖板", icon="mdi:toilet",
               device_class=BinarySensorDeviceClass.OPENING, read="cover_open"),
    BinaryDesc(key="ring", name="座圈", icon="mdi:toilet",
               device_class=BinarySensorDeviceClass.OPENING, read="ring_open"),
    BinaryDesc(key="flushing", name="冲水", icon="mdi:water",
               device_class=None, read="flushing"),
    BinaryDesc(key="fault", name="故障", icon="mdi:alert",
               device_class=BinarySensorDeviceClass.PROBLEM, read="fault"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: JomooCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(JomooBinarySensor(coordinator, desc) for desc in BINARY_SENSORS)


class JomooBinarySensor(JomooEntity, BinarySensorEntity):
    def __init__(self, coordinator: JomooCoordinator, desc: BinaryDesc) -> None:
        super().__init__(coordinator, desc.key, desc.name, desc.icon)
        self.desc = desc
        if desc.device_class is not None:
            self._attr_device_class = desc.device_class

    @property
    def is_on(self) -> bool | None:
        if self.desc.read is None:
            return self.coordinator.connected
        state = self.state_obj
        if state is None or not state.valid:
            return None
        return bool(getattr(state, self.desc.read))
