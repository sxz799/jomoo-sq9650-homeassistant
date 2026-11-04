"""座温选择器（常温 / 中温 / 高温）."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import JomooCoordinator
from .entity import JomooEntity
from .protocol import SEAT_TEMP_TEXT, SEAT_TEMP_TEXT_REVERSE


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: JomooCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([JomooSeatTempSelect(coordinator)])


class JomooSeatTempSelect(JomooEntity, SelectEntity):
    """座圈温度三档：硬件仅支持 0=常温 / 3=中温 / 5=高温."""

    _attr_icon = "mdi:thermometer"
    _attr_options = list(SEAT_TEMP_TEXT_REVERSE)

    def __init__(self, coordinator: JomooCoordinator) -> None:
        super().__init__(coordinator, "seat_temp", "座温")

    @property
    def current_option(self) -> str | None:
        state = self.state_obj
        if state is None or not state.valid:
            return None
        return SEAT_TEMP_TEXT.get(state.seat_temp)

    async def async_select_option(self, option: str) -> None:
        level = SEAT_TEMP_TEXT_REVERSE[option]
        await self.coordinator.async_send(
            {
                "常温": "seat_ambient",
                "中温": "seat_low",
                "高温": "seat_high",
            }[option],
            optimistic_key="seat_temp",
            optimistic_value=level,
        )
