"""九牧 SQ9650 马桶 BLE 集成入口."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .client import JomooBleClient
from .const import CONF_ADDRESS, DOMAIN
from .coordinator import JomooCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = JomooBleClient(hass, entry.data[CONF_ADDRESS])
    coordinator = JomooCoordinator(hass, client, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # 默认不连接：需要用 HA 控制时点“连接”，用完点“断开”释放给手机小程序
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: JomooCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.client.async_disconnect()
    return unload_ok
