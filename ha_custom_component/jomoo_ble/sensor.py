"""文本传感器：工作状态."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import JomooCoordinator
from .entity import JomooEntity
from .protocol import WORK_STATE_OPTIONS


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: JomooCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([JomooWorkStateSensor(coordinator)])


class JomooWorkStateSensor(JomooEntity, SensorEntity):
    _attr_icon = "mdi:toilet"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = WORK_STATE_OPTIONS

    def __init__(self, coordinator: JomooCoordinator) -> None:
        super().__init__(coordinator, "work_state", "工作状态")

    @property
    def native_value(self) -> str | None:
        state = self.state_obj
        if state is None or not state.valid:
            return None
        return state.work_text
