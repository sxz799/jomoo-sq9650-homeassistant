"""jomoo_ble 常量定义."""

from __future__ import annotations

import logging

DOMAIN = "jomoo_ble"

CONF_ADDRESS = "address"

# 九牧 SQ9650 出厂 MAC（可在配置流程中修改）
DEFAULT_ADDRESS = "A4:C1:38:E4:5D:CC"

# 连接保持时长（秒）：每次下发/查询都会重置计时，空闲超时自动断开，把连接让给手机小程序
IDLE_DISCONNECT_SECONDS = 60

# 等待 0x30 状态上报的超时时间（秒）
STATE_TIMEOUT = 2.0

LOGGER = logging.getLogger(__package__)
