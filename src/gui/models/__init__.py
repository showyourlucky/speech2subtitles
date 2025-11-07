"""GUI数据模型模块

提供GUI相关的数据模型类
"""

from .gui_models import TranscriptionState, AudioSourceInfo
from .history_models import TranscriptionRecord

__all__ = [
    'TranscriptionState',
    'AudioSourceInfo',
    'TranscriptionRecord'
]
