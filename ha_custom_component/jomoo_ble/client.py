"""九牧马桶 BLE 连接管理（手动连接 + 空闲超时断开）."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    close_stale_connections_by_address,
    establish_connection,
)

from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later

from .const import IDLE_DISCONNECT_SECONDS, LOGGER, STATE_TIMEOUT
from .protocol import CHARACTERISTIC_UUID, COMMANDS, ToiletState, parse_frame


class JomooBleClient:
    """维护到马桶的 GATT 连接，缓存最近一次状态上报."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        self.hass = hass
        self.address = address
        self.on_state: Callable[[ToiletState], None] | None = None
        self.on_connectivity: Callable[[bool], None] | None = None
        self._client: BleakClient | None = None
        self._lock = asyncio.Lock()
        self._state: ToiletState | None = None
        self._state_event = asyncio.Event()
        self._idle_unsub: Callable[[], None] | None = None
        self._prev_fault: bool | None = None
        self._stable_fault = False

    @property
    def state(self) -> ToiletState | None:
        return self._state

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    async def async_connect(self) -> None:
        """连接并订阅 FFE1 通知."""
        if self.connected:
            return

        # 清掉 BlueZ/代理中残留的同地址连接，避免 "already in progress"
        try:
            await close_stale_connections_by_address(self.address)
        except Exception as err:  # noqa: BLE001
            LOGGER.debug("清理残留连接失败: %s", err)

        info = self._best_service_info()
        if info is None:
            info = async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
        if info is None:
            raise HomeAssistantError(
                f"蓝牙范围内未找到 {self.address}，请确认 HA 蓝牙适配器或蓝牙代理可连接"
            )

        # habluetooth 的 BluetoothServiceInfoBleak 不是 BLEDevice，bleak 需要底层 device
        device = self._as_ble_device(info)
        source = getattr(info, "source", None) or getattr(
            getattr(info, "details", None), "source", None
        )
        LOGGER.debug(
            "开始连接 %s（name=%s, source=%s, rssi=%s）",
            self.address,
            getattr(info, "name", None),
            source,
            getattr(info, "rssi", None),
        )

        try:
            client = await establish_connection(
                BleakClientWithServiceCache,
                device,
                self.address,
                max_attempts=3,
                ble_device_callback=self._best_fresh_device,
                disconnected_callback=self._handle_disconnect,
            )
            await client.start_notify(CHARACTERISTIC_UUID, self._handle_notify)
            # 与小程序 onDeviceReady 一致：新连接先发一帧状态查询
            # （该帧可能被马桶丢弃，用它代替真实指令，避免用户第一次操作无效）
            try:
                await client.write_gatt_char(
                    CHARACTERISTIC_UUID, COMMANDS["query_state"], response=False
                )
            except BleakError as err:
                LOGGER.debug("连接后查询状态失败: %s", err)
        except Exception as err:  # noqa: BLE001
            infos = self._log_advertisement_sources()
            src_text = (
                "; ".join(
                    f"{info.source} rssi={info.rssi} connectable={info.connectable}"
                    for info in infos
                )
                or "无可用广播缓存"
            )
            LOGGER.warning(
                "连接 %s 失败: %s: %r",
                self.address,
                type(err).__name__,
                err,
                exc_info=True,
            )
            raise HomeAssistantError(
                f"连接马桶失败（{type(err).__name__}: {err or '无错误信息'}；"
                f"广播 {src_text}）"
            ) from err

        self._client = client
        self._notify_connectivity(True)
        self._schedule_idle_disconnect()
        LOGGER.debug("%s 已连接", self.address)

    @callback
    def _matching_infos(self) -> list:
        """该 MAC 近期（120s 内）的可连接广播缓存，过期的不参与连接."""
        now = time.monotonic()
        try:
            return [
                info
                for info in async_discovered_service_info(self.hass, connectable=True)
                if info.address.upper() == self.address.upper()
                and getattr(info, "time", now) >= now - 120
            ]
        except Exception as err:  # noqa: BLE001
            LOGGER.warning("读取广播缓存失败: %s", err)
            return []

    def _best_service_info(self):
        """优先使用本机适配器（hci*）的广播发起连接，避免走远端代理."""
        infos = self._matching_infos()
        if not infos:
            return None
        local = [info for info in infos if str(info.source).lower().startswith("hci")]
        return local[0] if local else infos[0]

    @staticmethod
    def _as_ble_device(info):
        """把蓝牙广播信息转成 bleak 需要的 BLEDevice（新版取其 .device）."""
        device = getattr(info, "device", None)
        return device if device is not None else info

    def _best_fresh_device(self):
        info = self._best_service_info() or async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        return self._as_ble_device(info) if info is not None else None

    @callback
    def _log_advertisement_sources(self) -> list:
        """把 HA 缓存的广播来源/ RSSI 打到日志并返回，便于判断是代理还是本机适配器."""
        infos = self._matching_infos()
        if not infos:
            LOGGER.warning("%s 没有可连接的广播缓存（可能只被被动扫描器看到）", self.address)
        for info in infos:
            LOGGER.warning(
                "%s 广播来源=%s rssi=%s connectable=%s name=%s",
                self.address,
                info.source,
                info.rssi,
                info.connectable,
                info.name,
            )
        return infos

    async def async_send(self, frame: bytes) -> None:
        """下发一帧指令（写 FFE1，不需要响应）."""
        async with self._lock:
            if not self.connected:
                await self.async_connect()
            assert self._client is not None
            try:
                await self._client.write_gatt_char(
                    CHARACTERISTIC_UUID, frame, response=False
                )
            except BleakError as err:
                await self._drop_connection()
                raise HomeAssistantError(f"指令下发失败: {err}") from err
            self._schedule_idle_disconnect()

    async def async_query_state(self, timeout: float = STATE_TIMEOUT) -> ToiletState | None:
        """查询状态并等待 0x30 上报；超时返回 None."""
        async with self._lock:
            if not self.connected:
                await self.async_connect()
            assert self._client is not None

            self._state_event.clear()
            try:
                await self._client.write_gatt_char(
                    CHARACTERISTIC_UUID, COMMANDS["query_state"], response=False
                )
            except BleakError as err:
                await self._drop_connection()
                raise HomeAssistantError(f"状态查询失败: {err}") from err
            self._schedule_idle_disconnect()

            try:
                await asyncio.wait_for(self._state_event.wait(), timeout)
            except asyncio.TimeoutError:
                LOGGER.debug("等待 %s 状态上报超时", self.address)
                return None
            return self._state

    async def async_connect_now(self) -> None:
        """手动连接（“连接”按钮）：成功后空闲 1 分钟无操作自动断开."""
        async with self._lock:
            await self.async_connect()
        self._schedule_idle_disconnect()

    async def async_disconnect(self) -> None:
        """断开连接（“断开”按钮/卸载集成时调用）."""
        if self._idle_unsub is not None:
            self._idle_unsub()
            self._idle_unsub = None
        await self._drop_connection()

    async def _drop_connection(self) -> None:
        client, self._client = self._client, None
        if client is None:
            return
        try:
            await client.disconnect()
        except BleakError:
            pass
        self._notify_connectivity(False)
        LOGGER.debug("%s 已断开", self.address)

    def _schedule_idle_disconnect(self) -> None:
        """重置空闲计时，超时后自动断开."""
        if self._idle_unsub is not None:
            self._idle_unsub()
        self._idle_unsub = async_call_later(
            self.hass, IDLE_DISCONNECT_SECONDS, self._idle_disconnect
        )

    @callback
    def _idle_disconnect(self, _now=None) -> None:
        self._idle_unsub = None
        self.hass.async_create_task(self.async_disconnect())

    @callback
    def _handle_disconnect(self, client: BleakClient) -> None:
        """链路被对端/代理断开时清掉引用，下次操作会重新连接."""
        if client is self._client:
            self._client = None
            self._notify_connectivity(False)
        LOGGER.debug("%s 链路已断开", self.address)

    def _notify_connectivity(self, connected: bool) -> None:
        if self.on_connectivity is not None:
            self.on_connectivity(connected)

    def _handle_notify(self, _char, data: bytearray) -> None:
        raw = bytes(data)
        LOGGER.debug("%s 收到上报 %s", self.address, raw.hex())
        state = parse_frame(raw)
        if state is None:
            return
        LOGGER.debug(
            "%s 解析: work=%s fault=%02X %02X %02X",
            self.address,
            state.work_state,
            raw[8] if len(raw) > 8 else 0,
            raw[9] if len(raw) > 9 else 0,
            raw[10] if len(raw) > 10 else 0,
        )
        # 故障位需连续两帧一致才对外公布，过滤设备逐帧抖动的单个状态位
        if state.fault == self._prev_fault:
            self._stable_fault = state.fault
        self._prev_fault = state.fault
        state.fault = self._stable_fault
        self._state = state
        self._state_event.set()
        if self.on_state is not None:
            self.on_state(state)
