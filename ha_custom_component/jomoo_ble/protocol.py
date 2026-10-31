"""九牧 SQ9650 私有 BLE 协议（Techramic bleProtocol=1）.

帧格式:
    FC <SUM> 01 00 00 00 <CMD> [<SUB> <VAL>] FC
校验和:
    SUM = sum(frame[2..len-2]) & 0xFF   （累加和，不是异或）
"""

from __future__ import annotations

from dataclasses import dataclass

SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"


def _build(cmd: int, *values: int) -> bytes:
    """构造指令帧，values 为子命令/参数（0~2 个字节）."""
    frame = bytearray((0xFC, 0x00, 0x01, 0x00, 0x00, 0x00, cmd, *values, 0xFC))
    frame[1] = sum(frame[2:-1]) & 0xFF
    return bytes(frame)


# 语义命令 -> 指令帧
COMMANDS: dict[str, bytes] = {
    # 冲水 / 动作
    "flush_large": _build(53, 2),
    "flush_small": _build(53, 1),
    "magic_bubble": _build(0x46, 1),  # 魔力泡：小程序 startBubble -> _setSwitch(70, true)
    "hibernate": _build(23, 1),
    "query_state": _build(17, 0),
    # 盖板 / 座圈
    "cover_open": _build(51, 1),
    "cover_close": _build(51, 0),
    "ring_open": _build(52, 1),
    "ring_close": _build(52, 0),
    # 座温：硬件只支持 0=常温 / 3=中温 / 5=高温（1、2、4 会被忽略）
    "seat_ambient": _build(60, 0),
    "seat_low": _build(60, 3),
    "seat_high": _build(60, 5),
    # 0x40H 双值开关
    "foot_on": _build(0x40, 0x0E, 1),
    "foot_off": _build(0x40, 0x0E, 0),
    "auto_flush_on": _build(0x40, 0x05, 1),
    "auto_flush_off": _build(0x40, 0x05, 0),
    "light_sensor_on": _build(0x40, 0x02, 1),  # 智能夜灯：setLightSensor -> _set40H(2, t)
    "light_sensor_off": _build(0x40, 0x02, 0),
    "pre_wetting_on": _build(0x40, 0x12, 1),
    "pre_wetting_off": _build(0x40, 0x12, 0),
    "close_cover_flush_on": _build(0x40, 0x14, 1),
    "close_cover_flush_off": _build(0x40, 0x14, 0),
    "seat_bubble_on": _build(0x40, 0x0C, 1),  # 落座发泡：setAutoBubble -> _set40H(12, t)
    "seat_bubble_off": _build(0x40, 0x0C, 0),
    # 0x41H 夜灯
    "night_light_on": _build(0x41, 0x00, 1),
    "night_light_off": _build(0x41, 0x00, 0),
}

# 座温档位 -> 显示文案
SEAT_TEMP_TEXT = {0: "常温", 3: "中温", 5: "高温"}
SEAT_TEMP_TEXT_REVERSE = {v: k for k, v in SEAT_TEMP_TEXT.items()}

WORK_STATE_TEXT = {
    0: "待机",
    1: "休眠中",
    16: "自清洁中",
    17: "预湿润中",
    31: "自检中",
}
WORK_STATE_OPTIONS = [*WORK_STATE_TEXT.values(), "工作中"]


@dataclass
class ToiletState:
    """由 0x30 状态上报帧解析出的马桶状态."""

    valid: bool = False
    work_state: int = 0
    on_seat: bool = False
    cover_open: bool = False
    ring_open: bool = False
    cover_running: bool = False
    ring_running: bool = False
    flushing_large: bool = False
    flushing_small: bool = False
    seat_temp: int = 0
    night_light: bool = False
    light_sensor: bool = False
    auto_flush: bool = False
    auto_cover: bool = False
    smart_power: bool = False
    foot_sensor: bool = False
    auto_temp: bool = False
    regular_flush: bool = False
    auto_small_flush: bool = False
    close_cover_flush: bool = False
    pre_wetting: bool = False
    fault: bool = False

    @property
    def flushing(self) -> bool:
        return self.flushing_large or self.flushing_small

    @property
    def work_text(self) -> str:
        return WORK_STATE_TEXT.get(self.work_state, "工作中")

    @property
    def seat_temp_text(self) -> str:
        return SEAT_TEMP_TEXT.get(self.seat_temp, "未知")


def parse_frame(frame: bytes) -> ToiletState | None:
    """解析 notify 上报帧，非 0x30 状态帧返回 None."""
    if len(frame) < 26 or frame[0] != 0xFC or frame[6] != 0x30:
        return None

    t = frame[7:]  # t[0] 对应帧[7]

    def bit(index: int, shift: int) -> bool:
        return bool((t[index] >> shift) & 0x01)

    flush_level = t[5] & 0x03
    return ToiletState(
        valid=True,
        work_state=t[0] & 0x1F,
        fault=bool(t[1] | t[2] | t[3]),
        foot_sensor=bit(4, 3),
        cover_open=bit(4, 4),
        ring_open=bit(4, 5),
        on_seat=bit(4, 7),
        flushing_large=flush_level == 2,
        flushing_small=flush_level == 1,
        auto_temp=bit(5, 2),
        ring_running=bit(6, 0),
        cover_running=bit(6, 1),
        auto_small_flush=bit(6, 3),
        close_cover_flush=bit(6, 4),
        regular_flush=bit(6, 7),
        pre_wetting=bit(6, 2),
        auto_cover=bit(8, 7),
        night_light=bit(9, 6),
        light_sensor=bit(9, 7),
        auto_flush=bit(10, 7),
        seat_temp=(t[10] >> 3) & 0x07,
        smart_power=bit(10, 6),
    )
