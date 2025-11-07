"""GUI数据模型

定义GUI层使用的数据结构和枚举
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from src.audio.models import AudioSourceType


class TranscriptionState(Enum):
    """转录状态枚举

    GUI层使用的状态定义，简化Pipeline的状态展示
    """
    READY = "ready"           # 就绪 - 未开始或已停止
    RUNNING = "running"       # 运行中 - 正在转录
    PAUSED = "paused"         # 暂停中 - 暂停转录（仅实时模式）
    STOPPED = "stopped"       # 已停止 - 转录结束
    ERROR = "error"           # 错误 - 发生错误

    def to_display_text(self) -> str:
        """获取显示文本"""
        display_map = {
            TranscriptionState.READY: "就绪",
            TranscriptionState.RUNNING: "运行中",
            TranscriptionState.PAUSED: "暂停中",
            TranscriptionState.STOPPED: "已停止",
            TranscriptionState.ERROR: "错误",
        }
        return display_map.get(self, "未知")

    def to_color(self) -> str:
        """获取状态颜色（十六进制）"""
        color_map = {
            TranscriptionState.READY: "#9E9E9E",     # 灰色
            TranscriptionState.RUNNING: "#4CAF50",   # 绿色
            TranscriptionState.PAUSED: "#FF9800",    # 橙色
            TranscriptionState.STOPPED: "#2196F3",   # 蓝色
            TranscriptionState.ERROR: "#F44336",     # 红色
        }
        return color_map.get(self, "#000000")


@dataclass
class AudioSourceInfo:
    """音频源信息"""
    source_type: AudioSourceType    # 音频源类型
    display_name: str               # 显示名称
    device_id: Optional[int] = None # 设备ID（麦克风/系统音频）
    file_path: Optional[str] = None # 文件路径（文件模式）

    def __str__(self) -> str:
        if self.source_type == AudioSourceType.MICROPHONE:
            return f"麦克风 (设备{self.device_id if self.device_id is not None else '默认'})"
        elif self.source_type == AudioSourceType.SYSTEM_AUDIO:
            return "系统音频"
        elif self.source_type == AudioSourceType.FILE:
            return f"文件: {self.file_path}"
        return "未知"
