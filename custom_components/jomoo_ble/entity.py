"""jomoo_sq9650_ble 实体基类."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import JomooCoordinator
from .protocol import ToiletState


class JomooEntity(CoordinatorEntity[JomooCoordinator]):
    """所有实体的公共部分（设备信息/唯一 ID/状态读取）."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: JomooCoordinator,
        key: str,
        name: str,
        icon: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.address}_{key}"
        self._attr_name = name
        if icon is not None:
            self._attr_icon = icon

    @property
    def available(self) -> bool:
        # 设备在墙面/固定位置，蓝牙偶发不可达时不希望整组实体变灰
        return True

    @property
    def state_obj(self) -> ToiletState | None:
        return self.coordinator.data

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.client.address)},
            name=self.coordinator.entry.title,
            manufacturer="JOMOO",
            model="SQ9650",
        )
