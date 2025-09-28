"""
Coordinator模块 - 流程协调

实现事件驱动的转录流水线，协调音频捕获、VAD检测、
语音转录等组件的整体工作流程。

核心组件:
- TranscriptionPipeline: 主流水线协调器
- PipelineEvent: 事件数据结构
- PipelineStatistics: 流水线统计信息
- PipelineState/EventType: 状态和事件类型枚举

使用示例:
    from src.coordinator import TranscriptionPipeline
    from src.config.models import Config

    config = Config(...)
    with TranscriptionPipeline(config) as pipeline:
        pipeline.run()
"""

# 导入核心类和枚举
from .pipeline import (
    TranscriptionPipeline,     # 主流水线协调器
    PipelineEvent,            # 事件数据结构
    PipelineStatistics,       # 统计信息
    PipelineState,            # 流水线状态
    EventType                 # 事件类型枚举
)

__all__ = [
    "TranscriptionPipeline",
    "PipelineEvent",
    "PipelineStatistics",
    "PipelineState",
    "EventType"
]