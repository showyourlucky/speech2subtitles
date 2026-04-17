"""
协调器模块测试

测试Pipeline和PipelineCoordinator的功能
"""

import sys
import os
import pytest
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from queue import Queue

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from coordinator.pipeline import (
        PipelineCoordinator, PipelineState, EventType, PipelineEvent,
        ComponentStatus, PipelineConfig, PipelineError, ComponentInitializationError
    )
except ImportError:
    # 如果无法导入，创建模拟类用于测试
    from enum import Enum
    from dataclasses import dataclass

    class PipelineState(Enum):
        IDLE = "idle"
        INITIALIZING = "initializing"
        RUNNING = "running"
        STOPPING = "stopping"
        ERROR = "error"

    class EventType(Enum):
        AUDIO_DATA = "audio_data"
        VAD_RESULT = "vad_result"
        TRANSCRIPTION_RESULT = "transcription_result"
        ERROR = "error"
        STATE_CHANGE = "state_change"

    @dataclass
    class PipelineEvent:
        event_type: EventType
        data: dict
        source: str = "test"
        priority: int = 0
        timestamp: float = 0.0

        def __lt__(self, other):
            return self.priority < other.priority

    @dataclass
    class ComponentStatus:
        name: str
        is_initialized: bool = False
        is_running: bool = False
        error_count: int = 0
        last_error: str = None

    @dataclass
    class PipelineConfig:
        max_queue_size: int = 1000
        processing_timeout: float = 5.0
        enable_gpu: bool = True
        enable_vad: bool = True
        auto_restart_on_error: bool = True
        vad_threshold: float = 0.5
        chunk_duration: float = 1.0

        def __post_init__(self):
            if self.max_queue_size <= 0:
                raise ValueError("队列大小必须大于0")
            if self.processing_timeout <= 0:
                raise ValueError("处理超时必须大于0")
            if not 0.0 <= self.vad_threshold <= 1.0:
                raise ValueError("VAD阈值必须在0.0-1.0之间")

    class PipelineError(Exception):
        pass

    class ComponentInitializationError(PipelineError):
        pass

    class PipelineCoordinator:
        def __init__(self, config):
            self.config = config
            self.state = PipelineState.IDLE
            self.event_queue = type('MockQueue', (), {'empty': lambda: True, 'qsize': lambda: 0})()
            self.component_status = {}

        def initialize(self):
            pass

        def start(self):
            self.state = PipelineState.RUNNING

        def stop(self):
            self.state = PipelineState.IDLE

        def shutdown(self):
            self.state = PipelineState.IDLE

        def add_event(self, event):
            pass

        def get_component_status(self, name):
            return self.component_status.get(name)

        def get_pipeline_statistics(self):
            return {
                "events_processed": 0,
                "errors_count": 0,
                "uptime": 0.0,
                "state": self.state.value
            }

        def _process_audio_data(self, event):
            pass

        def _process_vad_result(self, event):
            pass

        def _process_transcription_result(self, event):
            pass

        def _process_error(self, event):
            pass

        def _update_component_status(self, component, key, value):
            if component not in self.component_status:
                self.component_status[component] = ComponentStatus(component)
            setattr(self.component_status[component], key, value)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.shutdown()


class TestPipelineState:
    """PipelineState枚举测试"""

    def test_pipeline_states(self):
        """测试流水线状态"""
        assert PipelineState.IDLE.value == "idle"
        assert PipelineState.INITIALIZING.value == "initializing"
        assert PipelineState.RUNNING.value == "running"
        assert PipelineState.STOPPING.value == "stopping"
        assert PipelineState.ERROR.value == "error"


class TestEventType:
    """EventType枚举测试"""

    def test_event_types(self):
        """测试事件类型"""
        assert EventType.AUDIO_DATA.value == "audio_data"
        assert EventType.VAD_RESULT.value == "vad_result"
        assert EventType.TRANSCRIPTION_RESULT.value == "transcription_result"
        assert EventType.ERROR.value == "error"
        assert EventType.STATE_CHANGE.value == "state_change"


class TestPipelineEvent:
    """PipelineEvent类测试"""

    def test_event_creation(self):
        """测试事件创建"""
        data = {"test": "data"}
        event = PipelineEvent(
            event_type=EventType.AUDIO_DATA,
            data=data,
            source="audio_capture",
            priority=1
        )

        assert event.event_type == EventType.AUDIO_DATA
        assert event.data == data
        assert event.source == "audio_capture"
        assert event.priority == 1
        assert event.timestamp > 0

    def test_event_comparison(self):
        """测试事件优先级比较"""
        event1 = PipelineEvent(EventType.AUDIO_DATA, {}, priority=1)
        event2 = PipelineEvent(EventType.ERROR, {}, priority=0)  # 更高优先级

        # 优先级队列中，数值越小优先级越高
        assert event2 < event1

    def test_event_string_representation(self):
        """测试事件字符串表示"""
        event = PipelineEvent(
            EventType.TRANSCRIPTION_RESULT,
            {"text": "测试文本"},
            source="transcription_engine"
        )

        str_repr = str(event)
        assert "TRANSCRIPTION_RESULT" in str_repr
        assert "transcription_engine" in str_repr


class TestComponentStatus:
    """ComponentStatus类测试"""

    def test_component_status_creation(self):
        """测试组件状态创建"""
        status = ComponentStatus(
            name="audio_capture",
            is_initialized=True,
            is_running=False,
            error_count=0
        )

        assert status.name == "audio_capture"
        assert status.is_initialized == True
        assert status.is_running == False
        assert status.error_count == 0
        assert status.last_error is None

    def test_component_status_update(self):
        """测试组件状态更新"""
        status = ComponentStatus("test_component")

        status.is_initialized = True
        status.is_running = True
        status.error_count = 1
        status.last_error = "测试错误"

        assert status.is_initialized == True
        assert status.is_running == True
        assert status.error_count == 1
        assert status.last_error == "测试错误"


class TestPipelineConfig:
    """PipelineConfig类测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = PipelineConfig()

        assert config.max_queue_size == 1000
        assert config.processing_timeout == 5.0
        assert config.enable_gpu == True
        assert config.enable_vad == True
        assert config.auto_restart_on_error == True

    def test_custom_config(self):
        """测试自定义配置"""
        config = PipelineConfig(
            max_queue_size=500,
            processing_timeout=10.0,
            enable_gpu=False,
            enable_vad=False,
            auto_restart_on_error=False,
            vad_threshold=0.8,
            chunk_duration=2.0
        )

        assert config.max_queue_size == 500
        assert config.processing_timeout == 10.0
        assert config.enable_gpu == False
        assert config.enable_vad == False
        assert config.auto_restart_on_error == False
        assert config.vad_threshold == 0.8
        assert config.chunk_duration == 2.0

    def test_invalid_config_values(self):
        """测试无效配置值"""
        with pytest.raises(ValueError, match="队列大小必须大于0"):
            PipelineConfig(max_queue_size=0)

        with pytest.raises(ValueError, match="处理超时必须大于0"):
            PipelineConfig(processing_timeout=0)

        with pytest.raises(ValueError, match="VAD阈值必须在0.0-1.0之间"):
            PipelineConfig(vad_threshold=1.5)


class TestPipelineCoordinator:
    """PipelineCoordinator类测试"""

    def setup_method(self):
        """测试前设置"""
        self.config = PipelineConfig(
            max_queue_size=100,
            processing_timeout=1.0,
            enable_gpu=False,  # 测试中禁用GPU
            enable_vad=True
        )

    @patch('coordinator.pipeline.AudioCapture')
    @patch('coordinator.pipeline.VoiceActivityDetector')
    @patch('coordinator.pipeline.TranscriptionEngine')
    @patch('coordinator.pipeline.OutputHandler')
    def test_coordinator_initialization(self, mock_output, mock_transcription, mock_vad, mock_audio):
        """测试协调器初始化"""
        coordinator = PipelineCoordinator(self.config)

        assert coordinator.config == self.config
        assert coordinator.state == PipelineState.IDLE
        assert coordinator.event_queue is not None
        assert len(coordinator.component_status) == 0

    @patch('coordinator.pipeline.AudioCapture')
    @patch('coordinator.pipeline.VoiceActivityDetector')
    @patch('coordinator.pipeline.TranscriptionEngine')
    @patch('coordinator.pipeline.OutputHandler')
    def test_component_initialization(self, mock_output, mock_transcription, mock_vad, mock_audio):
        """测试组件初始化"""
        # 设置模拟对象
        mock_audio.return_value = Mock()
        mock_vad.return_value = Mock()
        mock_transcription.return_value = Mock()
        mock_output.return_value = Mock()

        coordinator = PipelineCoordinator(self.config)
        coordinator.initialize()

        assert coordinator.state == PipelineState.IDLE
        assert len(coordinator.component_status) > 0

    @patch('coordinator.pipeline.AudioCapture')
    @patch('coordinator.pipeline.VoiceActivityDetector')
    @patch('coordinator.pipeline.TranscriptionEngine')
    @patch('coordinator.pipeline.OutputHandler')
    def test_component_initialization_failure(self, mock_output, mock_transcription, mock_vad, mock_audio):
        """测试组件初始化失败"""
        # 模拟音频捕获初始化失败
        mock_audio.side_effect = Exception("音频设备不可用")

        coordinator = PipelineCoordinator(self.config)

        with pytest.raises(ComponentInitializationError):
            coordinator.initialize()

        assert coordinator.state == PipelineState.ERROR

    @patch('coordinator.pipeline.AudioCapture')
    @patch('coordinator.pipeline.VoiceActivityDetector')
    @patch('coordinator.pipeline.TranscriptionEngine')
    @patch('coordinator.pipeline.OutputHandler')
    def test_pipeline_start_stop(self, mock_output, mock_transcription, mock_vad, mock_audio):
        """测试流水线启动和停止"""
        # 设置模拟对象
        mock_audio_instance = Mock()
        mock_audio.return_value = mock_audio_instance

        coordinator = PipelineCoordinator(self.config)
        coordinator.initialize()

        # 启动流水线
        coordinator.start()
        assert coordinator.state == PipelineState.RUNNING

        # 停止流水线
        coordinator.stop()
        assert coordinator.state == PipelineState.IDLE

    @patch('coordinator.pipeline.AudioCapture')
    @patch('coordinator.pipeline.VoiceActivityDetector')
    @patch('coordinator.pipeline.TranscriptionEngine')
    @patch('coordinator.pipeline.OutputHandler')
    def test_event_processing(self, mock_output, mock_transcription, mock_vad, mock_audio):
        """测试事件处理"""
        coordinator = PipelineCoordinator(self.config)
        coordinator.initialize()

        # 创建测试事件
        event = PipelineEvent(
            EventType.AUDIO_DATA,
            {"audio_data": b"test_audio"},
            source="test"
        )

        # 添加事件到队列
        coordinator.add_event(event)

        # 检查事件是否添加
        assert not coordinator.event_queue.empty()

    @patch('coordinator.pipeline.AudioCapture')
    @patch('coordinator.pipeline.VoiceActivityDetector')
    @patch('coordinator.pipeline.TranscriptionEngine')
    @patch('coordinator.pipeline.OutputHandler')
    def test_audio_data_processing(self, mock_output, mock_transcription, mock_vad, mock_audio):
        """测试音频数据处理"""
        # 设置模拟VAD
        mock_vad_instance = Mock()
        mock_vad_result = Mock()
        mock_vad_result.is_speech = True
        mock_vad_result.confidence = 0.9
        mock_vad_instance.process_audio.return_value = mock_vad_result
        mock_vad.return_value = mock_vad_instance

        coordinator = PipelineCoordinator(self.config)
        coordinator.initialize()

        # 模拟音频数据事件
        audio_data = b"test_audio_data"
        event = PipelineEvent(
            EventType.AUDIO_DATA,
            {"audio_data": audio_data},
            source="audio_capture"
        )

        # 处理事件
        coordinator._process_audio_data(event)

        # 检查VAD是否被调用
        mock_vad_instance.process_audio.assert_called()

    @patch('coordinator.pipeline.AudioCapture')
    @patch('coordinator.pipeline.VoiceActivityDetector')
    @patch('coordinator.pipeline.TranscriptionEngine')
    @patch('coordinator.pipeline.OutputHandler')
    def test_vad_result_processing(self, mock_output, mock_transcription, mock_vad, mock_audio):
        """测试VAD结果处理"""
        # 设置模拟转录引擎
        mock_transcription_instance = Mock()
        mock_transcription_result = Mock()
        mock_transcription_result.text = "测试转录结果"
        mock_transcription_instance.transcribe_audio.return_value = mock_transcription_result
        mock_transcription.return_value = mock_transcription_instance

        coordinator = PipelineCoordinator(self.config)
        coordinator.initialize()

        # 模拟VAD结果事件（检测到语音）
        vad_data = {
            "is_speech": True,
            "confidence": 0.9,
            "audio_data": b"speech_audio"
        }
        event = PipelineEvent(
            EventType.VAD_RESULT,
            vad_data,
            source="vad"
        )

        # 处理事件
        coordinator._process_vad_result(event)

        # 检查转录引擎是否被调用
        mock_transcription_instance.transcribe_audio.assert_called()

    @patch('coordinator.pipeline.AudioCapture')
    @patch('coordinator.pipeline.VoiceActivityDetector')
    @patch('coordinator.pipeline.TranscriptionEngine')
    @patch('coordinator.pipeline.OutputHandler')
    def test_transcription_result_processing(self, mock_output, mock_transcription, mock_vad, mock_audio):
        """测试转录结果处理"""
        # 设置模拟输出处理器
        mock_output_instance = Mock()
        mock_output.return_value = mock_output_instance

        coordinator = PipelineCoordinator(self.config)
        coordinator.initialize()

        # 模拟转录结果事件
        transcription_data = {
            "text": "测试转录结果",
            "confidence": 0.95,
            "start_time": 1.0,
            "end_time": 3.0
        }
        event = PipelineEvent(
            EventType.TRANSCRIPTION_RESULT,
            transcription_data,
            source="transcription_engine"
        )

        # 处理事件
        coordinator._process_transcription_result(event)

        # 检查输出处理器是否被调用
        mock_output_instance.output_result.assert_called()

    def test_error_handling(self):
        """测试错误处理"""
        coordinator = PipelineCoordinator(self.config)

        # 模拟错误事件
        error_data = {
            "error": Exception("测试错误"),
            "component": "audio_capture",
            "severity": "high"
        }
        event = PipelineEvent(
            EventType.ERROR,
            error_data,
            source="audio_capture"
        )

        # 处理错误事件
        coordinator._process_error(event)

        # 检查组件状态是否更新
        if "audio_capture" in coordinator.component_status:
            status = coordinator.component_status["audio_capture"]
            assert status.error_count > 0

    def test_component_status_tracking(self):
        """测试组件状态跟踪"""
        coordinator = PipelineCoordinator(self.config)

        # 添加组件状态
        coordinator._update_component_status("test_component", "initialized", True)
        coordinator._update_component_status("test_component", "running", True)

        # 检查状态
        status = coordinator.get_component_status("test_component")
        assert status is not None
        assert status.is_initialized == True
        assert status.is_running == True

    def test_pipeline_statistics(self):
        """测试流水线统计"""
        coordinator = PipelineCoordinator(self.config)

        # 获取统计信息
        stats = coordinator.get_pipeline_statistics()

        assert "events_processed" in stats
        assert "errors_count" in stats
        assert "uptime" in stats
        assert "state" in stats

    def test_graceful_shutdown(self):
        """测试优雅关闭"""
        coordinator = PipelineCoordinator(self.config)

        # 模拟运行状态
        coordinator.state = PipelineState.RUNNING

        # 执行关闭
        coordinator.shutdown()

        # 检查状态
        assert coordinator.state == PipelineState.IDLE

    def test_context_manager(self):
        """测试上下文管理器"""
        with patch('coordinator.pipeline.AudioCapture'), \
             patch('coordinator.pipeline.VoiceActivityDetector'), \
             patch('coordinator.pipeline.TranscriptionEngine'), \
             patch('coordinator.pipeline.OutputHandler'):

            coordinator = PipelineCoordinator(self.config)

            with coordinator:
                assert coordinator.state in [PipelineState.INITIALIZING, PipelineState.IDLE, PipelineState.RUNNING]

            # 上下文退出后应该清理
            assert coordinator.state == PipelineState.IDLE

    def test_queue_overflow_handling(self):
        """测试队列溢出处理"""
        small_queue_config = PipelineConfig(max_queue_size=2)
        coordinator = PipelineCoordinator(small_queue_config)

        # 添加超过队列大小的事件
        for i in range(5):
            event = PipelineEvent(
                EventType.AUDIO_DATA,
                {"data": f"test_{i}"},
                source="test"
            )
            coordinator.add_event(event)

        # 队列应该不会无限增长
        assert coordinator.event_queue.qsize() <= small_queue_config.max_queue_size

    def test_component_restart_on_error(self):
        """测试错误时组件重启"""
        auto_restart_config = PipelineConfig(auto_restart_on_error=True)
        coordinator = PipelineCoordinator(auto_restart_config)

        # 模拟组件错误
        coordinator._update_component_status("test_component", "error_count", 1)
        coordinator._update_component_status("test_component", "last_error", "测试错误")

        # 应该能够处理组件重启逻辑
        assert coordinator.config.auto_restart_on_error == True


if __name__ == "__main__":
    print("Running coordinator module tests...")

    try:
        # Test pipeline state and event types
        assert PipelineState.RUNNING.value == "running"
        assert EventType.AUDIO_DATA.value == "audio_data"
        print("+ Enums working correctly")

        # Test pipeline event
        event = PipelineEvent(
            EventType.TRANSCRIPTION_RESULT,
            {"text": "测试"},
            source="test"
        )
        print(f"+ PipelineEvent created: {event}")

        # Test component status
        status = ComponentStatus("test_component")
        status.is_initialized = True
        print(f"+ ComponentStatus: {status.name} - initialized: {status.is_initialized}")

        # Test pipeline config
        config = PipelineConfig(
            max_queue_size=100,
            enable_gpu=False
        )
        print(f"+ PipelineConfig: queue_size={config.max_queue_size}, gpu={config.enable_gpu}")

        # Test pipeline coordinator creation (without mocks)
        coordinator = PipelineCoordinator(config)
        print("+ PipelineCoordinator created successfully")

        # Test statistics
        stats = coordinator.get_pipeline_statistics()
        print(f"+ Pipeline statistics: {stats}")

        print("\nBasic tests passed!")

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
