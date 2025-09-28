#!/usr/bin/env python3
"""
实时语音转录系统主程序

基于sherpa-onnx和silero_vad的高性能语音识别系统
支持麦克风和系统音频捕获，提供实时语音转文本功能

系统架构：
- 事件驱动的流水线架构
- 支持实时音频捕获 (PyAudio)
- VAD语音活动检测 (Silero VAD)
- 语音转录引擎 (sherpa-onnx + sense-voice)
- 多格式输出支持 (控制台/JSON/文件)
- GPU/CPU自适应处理
"""

import sys
import os
import logging
import argparse
from pathlib import Path
from typing import Optional

# 添加项目根目录到Python路径，确保可以导入src模块
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入项目核心组件
from src.config.manager import ConfigManager
from src.coordinator.pipeline import TranscriptionPipeline, PipelineState
from src.coordinator.pipeline import EventType, PipelineEvent


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    设置日志系统，支持控制台和文件输出

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        log_file: 日志文件路径，None表示只输出到控制台

    Note:
        使用UTF-8编码确保中文日志正确显示
        同时配置第三方库的日志级别避免干扰
    """
    # 创建统一的日志格式，包含时间戳、模块名、级别和消息
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # 初始化处理器列表
    handlers = []

    # 配置控制台处理器 - 所有日志都会输出到控制台
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    handlers.append(console_handler)

    # 配置文件处理器 - 如果指定了日志文件路径
    if log_file:
        log_path = Path(log_file)
        # 确保日志目录存在
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # 使用UTF-8编码确保中文日志正确写入
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        handlers.append(file_handler)

    # 配置根日志器，force=True确保重新配置
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        handlers=handlers,
        force=True
    )

    # 设置第三方库的日志级别，避免过多的调试信息干扰
    logging.getLogger('pyaudio').setLevel(logging.WARNING)      # PyAudio音频库
    logging.getLogger('onnxruntime').setLevel(logging.WARNING)  # ONNX推理引擎
    logging.getLogger('torch').setLevel(logging.WARNING)        # PyTorch深度学习框架


def print_banner():
    """
    打印程序启动横幅信息

    显示项目名称、版本信息和核心技术栈
    """
    banner = """
════════════════════════════════════════════════════════════════
                  实时语音转录系统 v1.0
                Real-time Speech Transcription

  基于 sherpa-onnx + silero_vad + sense-voice
  支持麦克风和系统音频实时转录

  作者: AI Assistant
  项目: speech2subtitles
════════════════════════════════════════════════════════════════
"""
    print(banner)


def print_system_info():
    """
    打印系统信息，包括操作系统、Python版本、硬件配置等

    信息包括：
    - 操作系统版本
    - Python版本
    - CPU信息
    - 内存大小
    - GPU可用性和详细信息
    """
    import platform

    # 获取内存信息，优雅处理psutil可能不可用的情况
    try:
        import psutil
        memory_gb = psutil.virtual_memory().total // (1024**3)
    except ImportError:
        memory_gb = "未知"

    print("\n系统信息:")
    print(f"  操作系统: {platform.system()} {platform.release()}")
    print(f"  Python版本: {platform.python_version()}")
    print(f"  CPU: {platform.processor()}")
    print(f"  内存: {memory_gb} GB")

    # 检测GPU信息，包括CUDA可用性和GPU详细信息
    try:
        from src.hardware.gpu_detector import GPUDetector
        gpu_detector = GPUDetector()
        cuda_available = gpu_detector.detect_cuda()
        print(f"  CUDA可用: {'是' if cuda_available else '否'}")

        # 如果CUDA可用，显示GPU详细信息
        if cuda_available:
            system_info = gpu_detector.get_system_info()
            if system_info and system_info.gpus:
                for i, gpu in enumerate(system_info.gpus):
                    print(f"  GPU {i}: {gpu.name} ({gpu.total_memory} MB)")
    except Exception as e:
        print(f"  GPU检测失败: {e}")


def add_pipeline_event_handlers(pipeline: TranscriptionPipeline) -> None:
    """
    为流水线添加事件处理器，处理状态变化和错误事件

    Args:
        pipeline: 流水线实例

    Note:
        事件处理器用于监控流水线状态变化和错误，提供用户反馈
    """
    def on_state_change(event: PipelineEvent):
        """
        处理流水线状态变化事件

        Args:
            event: 包含状态变化信息的事件对象
        """
        if event.data and isinstance(event.data, dict):
            old_state = event.data.get('old')
            new_state = event.data.get('new')
            print(f"\n[状态变化] {old_state} -> {new_state}")

    def on_error(event: PipelineEvent):
        """
        处理流水线错误事件

        Args:
            event: 包含错误信息的事件对象
        """
        error_msg = event.data if isinstance(event.data, str) else str(event.data)
        print(f"\n[错误] {event.source}: {error_msg}")

    # 注册状态变化和错误事件处理器
    pipeline.add_event_handler(EventType.STATE_CHANGE, on_state_change)
    pipeline.add_event_handler(EventType.ERROR, on_error)

    # 添加系统级错误回调，处理流水线无法捕获的异常
    def error_callback(exception: Exception):
        """
        系统级错误回调函数

        Args:
            exception: 发生的异常对象
        """
        print(f"\n[系统错误] {exception}")

    pipeline.add_error_callback(error_callback)


def print_usage_instructions():
    """
    打印使用说明和注意事项

    包括：
    - 基本操作说明
    - 音频源类型说明
    - 模型要求
    - 权限要求
    """
    instructions = """
使用说明:
  - 程序将开始实时音频捕获和转录
  - 转录结果将实时显示在控制台
  - 按 Ctrl+C 停止程序
  - 确保麦克风权限已授予（如使用麦克风输入）
  - 确保系统音频可访问（如使用系统音频输入）

音频源说明:
  - microphone: 从默认麦克风捕获音频
  - system: 从系统音频输出捕获音频（如播放器、浏览器等）

模型要求:
  - 支持 .onnx 和 .bin 格式的 sense-voice 模型
  - 推荐使用GPU加速以获得更好性能
  - VAD模型将自动下载（silero_vad）

注意事项:
  - 首次运行可能需要下载模型文件
  - 确保网络连接正常以下载VAD模型
  - Windows用户可能需要启用"立体声混音"使用系统音频捕获
"""
    print(instructions)


def validate_runtime_environment() -> bool:
    """
    验证运行时环境，检查必要依赖是否安装

    Returns:
        bool: 环境是否有效，True表示所有依赖都可用

    Note:
        检查关键依赖库的可用性，包括音频处理、深度学习框架等
    """
    # 检查必要的依赖库
    missing_deps = []

    # 检查PyAudio音频库
    try:
        import pyaudio
    except ImportError:
        missing_deps.append("pyaudio")

    # 检查PyTorch深度学习框架
    try:
        import torch
    except ImportError:
        missing_deps.append("torch")

    # 检查NumPy数值计算库
    try:
        import numpy
    except ImportError:
        missing_deps.append("numpy")

    # 如果有缺失的依赖，提供安装指导
    if missing_deps:
        print(f"\n❌ 缺少必要依赖: {', '.join(missing_deps)}")
        print("请运行以下命令安装:")
        for dep in missing_deps:
            if dep == "pyaudio":
                print("  pip install PyAudio")
            else:
                print(f"  pip install {dep}")
        return False

    print("\n✅ 依赖检查通过")
    return True


def main():
    """
    主程序入口点

    程序执行流程：
    1. 显示启动信息
    2. 验证运行环境
    3. 解析配置参数
    4. 设置日志系统
    5. 创建和配置流水线
    6. 运行语音转录
    7. 优雅退出和清理
    """
    try:
        # 步骤1: 显示程序启动横幅
        print_banner()

        # 步骤2: 验证运行环境，确保必要依赖可用
        if not validate_runtime_environment():
            sys.exit(1)

        # 步骤3: 显示系统硬件信息
        print_system_info()

        # 步骤4: 初始化配置管理器
        config_manager = ConfigManager()

        # 步骤5: 解析命令行参数或使用调试模式
        try:
            # 检查是否有命令行参数
            if len(sys.argv) == 1:
                # 调试模式：没有提供参数时使用默认配置
                config = config_manager.get_default_config()
                # config.model_path = ""  # 占位符，实际使用时需要真实路径
                print("\n[调试模式] 使用默认配置")
                print("在生产环境中，请提供正确的命令行参数")
                print("示例: python main.py --model-path models/sense-voice.onnx --input-source microphone")
            else:
                # 正常模式：解析命令行参数
                config = config_manager.parse_arguments()
        except SystemExit as e:
            # argparse 调用了 sys.exit()
            if e.code == 0:
                # 正常退出（如 --help）
                return
            else:
                # 参数错误
                print("\n❌ 命令行参数错误")
                config_manager.print_help()
                sys.exit(1)
        except Exception as e:
            print(f"\n❌ 配置解析失败: {e}")
            sys.exit(1)

        # 步骤6: 设置日志系统
        # 根据配置确定日志级别，调试模式使用DEBUG级别
        log_level = "DEBUG" if hasattr(config, 'debug') and config.debug else "INFO"
        setup_logging(level=log_level)

        logger = logging.getLogger(__name__)
        logger.info("实时语音转录系统启动")

        # 步骤7: 打印配置信息
        print("\n" + "="*60)
        config_manager.print_config(config)
        print("="*60)

        # 步骤8: 打印使用说明
        print_usage_instructions()

        # 步骤9: 创建和配置转录流水线
        print("\n[初始化] 创建转录流水线...")
        pipeline = TranscriptionPipeline(config)
        add_pipeline_event_handlers(pipeline)

        # 步骤10: 运行流水线
        print("\n[启动] 开始实时语音转录...")
        print("按 Ctrl+C 停止程序\n")

        # 使用上下文管理器确保资源正确清理
        with pipeline:
            pipeline.run()

        print("\n[完成] 程序正常退出")

    except KeyboardInterrupt:
        # 用户按Ctrl+C中断程序
        print("\n\n[中断] 用户中断程序")

    except Exception as e:
        # 处理未预期的异常
        print(f"\n❌ 程序异常退出: {e}")
        logging.exception("Unhandled exception in main")
        sys.exit(1)

    finally:
        # 无论如何都会执行的清理代码
        print("\n感谢使用实时语音转录系统！")


def cli():
    """
    命令行接口入口（用于 setuptools entry_points）

    这个函数可以通过安装包后的命令行工具调用
    例如：pip install -e . 后可以直接运行 speech2subtitles 命令
    """
    main()


# 程序入口点
if __name__ == "__main__":
    main()