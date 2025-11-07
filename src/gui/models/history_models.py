"""
转录历史记录数据模型

定义转录记录的数据结构和序列化方法
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
import json

from src.audio.models import AudioSourceType


@dataclass
class TranscriptionRecord:
    """转录记录数据模型

    对应数据库表: transcription_history
    """
    id: Optional[int] = None  # 数据库自增ID
    timestamp: datetime = None  # 转录时间
    audio_source: AudioSourceType = None  # 音频源类型
    audio_path: Optional[str] = None  # 文件路径（文件模式）
    duration: float = 0.0  # 转录时长（秒）
    text: str = ""  # 转录文本
    model_name: str = ""  # 使用的模型
    config_snapshot: str = ""  # 配置快照（JSON字符串）

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（用于数据库存储）

        Returns:
            Dict[str, Any]: 字典表示
        """
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'audio_source': self.audio_source.value if self.audio_source else None,
            'audio_path': self.audio_path,
            'duration': self.duration,
            'text': self.text,
            'model_name': self.model_name,
            'config_snapshot': self.config_snapshot
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TranscriptionRecord':
        """从字典反序列化

        Args:
            data: 字典数据

        Returns:
            TranscriptionRecord: 记录对象
        """
        # 解析时间戳
        timestamp = None
        if data.get('timestamp'):
            try:
                timestamp = datetime.fromisoformat(data['timestamp'])
            except (ValueError, TypeError):
                timestamp = None

        # 解析音频源类型
        audio_source = None
        if data.get('audio_source'):
            try:
                audio_source = AudioSourceType(data['audio_source'])
            except (ValueError, TypeError):
                audio_source = None

        return cls(
            id=data.get('id'),
            timestamp=timestamp,
            audio_source=audio_source,
            audio_path=data.get('audio_path'),
            duration=data.get('duration', 0.0),
            text=data.get('text', ''),
            model_name=data.get('model_name', ''),
            config_snapshot=data.get('config_snapshot', '')
        )

    def get_audio_source_display(self) -> str:
        """获取音频源的显示名称

        Returns:
            str: 显示名称
        """
        if not self.audio_source:
            return "未知"

        source_names = {
            AudioSourceType.MICROPHONE: "麦克风",
            AudioSourceType.SYSTEM_AUDIO: "系统音频",
            AudioSourceType.FILE: "音频文件"
        }

        display_name = source_names.get(self.audio_source, self.audio_source.value)

        # 如果是文件模式，添加文件名
        if self.audio_source == AudioSourceType.FILE and self.audio_path:
            from pathlib import Path
            filename = Path(self.audio_path).name
            display_name += f" ({filename})"

        return display_name

    def get_duration_display(self) -> str:
        """获取时长的显示格式

        Returns:
            str: 格式化的时长（如: 1:23:45）
        """
        if self.duration <= 0:
            return "0秒"

        hours = int(self.duration // 3600)
        minutes = int((self.duration % 3600) // 60)
        seconds = int(self.duration % 60)

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        elif minutes > 0:
            return f"{minutes}:{seconds:02d}"
        else:
            return f"{seconds}秒"

    def get_config_snapshot_dict(self) -> Dict[str, Any]:
        """获取配置快照的字典格式

        Returns:
            Dict[str, Any]: 配置字典，解析失败返回空字典
        """
        try:
            return json.loads(self.config_snapshot)
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_text_preview(self, max_length: int = 100) -> str:
        """获取转录文本的预览

        Args:
            max_length: 最大预览长度

        Returns:
            str: 文本预览，超出长度添加省略号
        """
        if not self.text:
            return ""

        if len(self.text) <= max_length:
            return self.text

        return self.text[:max_length-3] + "..."

    def __str__(self) -> str:
        """字符串表示

        Returns:
            str: 记录的简要描述
        """
        timestamp_str = self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else "未知时间"
        source_str = self.get_audio_source_display()
        text_preview = self.get_text_preview(50)

        return f"[{timestamp_str}] {source_str}: {text_preview}"