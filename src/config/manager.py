"""
配置管理器

负责命令行参数解析、配置验证和默认值管理
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from .models import Config


class ConfigManager:
    """配置管理器类"""

    def __init__(self):
        """初始化配置管理器"""
        self.parser = self._create_parser()

    def _create_parser(self) -> argparse.ArgumentParser:
        """创建命令行参数解析器"""

        parser = argparse.ArgumentParser(
            prog="speech2subtitles",
            description="实时语音转录系统 - 基于sherpa-onnx和silero_vad的高性能语音识别",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
使用示例:
  %(prog)s --model-path models/sense-voice.onnx --input-source microphone
  %(prog)s --model-path models/sense-voice.onnx --input-source system --no-gpu
  %(prog)s --model-path models/sense-voice.onnx --input-source microphone --vad-sensitivity 0.7

支持的输入源:
  microphone    从麦克风捕获音频
  system        从系统音频输出捕获音频 (如浏览器、播放器等)

模型要求:
  支持 .onnx 和 .bin 格式的sense-voice模型文件
            """
        )

        # 必需参数
        required = parser.add_argument_group("必需参数")
        required.add_argument(
            "--model-path",
            type=str,
            required=True,
            help="sense-voice模型文件路径 (.onnx 或 .bin)"
        )
        required.add_argument(
            "--input-source",
            type=str,
            required=True,
            choices=["microphone", "system"],
            help="音频输入源: microphone(麦克风) 或 system(系统音频)"
        )

        # 可选参数
        optional = parser.add_argument_group("可选参数")
        optional.add_argument(
            "--no-gpu",
            action="store_true",
            help="禁用GPU加速，强制使用CPU模式"
        )
        optional.add_argument(
            "--vad-sensitivity",
            type=float,
            default=0.5,
            metavar="FLOAT",
            help="VAD语音检测敏感度 (0.0-1.0, 默认: 0.5)"
        )
        optional.add_argument(
            "--device-id",
            type=int,
            metavar="INT",
            help="指定音频设备ID (不指定则使用默认设备)"
        )

        # 音频参数
        audio = parser.add_argument_group("音频参数")
        audio.add_argument(
            "--sample-rate",
            type=int,
            default=16000,
            choices=[8000, 16000, 22050, 44100, 48000],
            help="音频采样率 (默认: 16000Hz)"
        )
        audio.add_argument(
            "--chunk-size",
            type=int,
            default=1024,
            metavar="INT",
            help="音频块大小 (默认: 1024)"
        )

        # VAD参数
        vad = parser.add_argument_group("VAD参数")
        vad.add_argument(
            "--vad-window-size",
            type=float,
            default=0.512,
            metavar="FLOAT",
            help="VAD窗口大小，单位秒 (默认: 0.512)"
        )
        vad.add_argument(
            "--vad-threshold",
            type=float,
            default=0.5,
            metavar="FLOAT",
            help="VAD检测阈值 (0.0-1.0, 默认: 0.5)"
        )

        # 输出参数
        output = parser.add_argument_group("输出参数")
        output.add_argument(
            "--output-format",
            type=str,
            default="text",
            choices=["text", "json"],
            help="输出格式 (默认: text)"
        )
        output.add_argument(
            "--no-confidence",
            action="store_true",
            help="不显示置信度信息"
        )
        output.add_argument(
            "--no-timestamp",
            action="store_true",
            help="不显示时间戳信息"
        )

        return parser

    def parse_arguments(self, args: Optional[list] = None) -> Config:
        """
        解析命令行参数并返回配置对象

        Args:
            args: 命令行参数列表，None表示使用sys.argv

        Returns:
            Config: 配置对象

        Raises:
            SystemExit: 参数解析失败或验证失败时退出
        """
        try:
            # 解析参数
            parsed_args = self.parser.parse_args(args)

            # 创建配置对象
            config = Config(
                model_path=parsed_args.model_path,
                input_source=parsed_args.input_source,
                use_gpu=not parsed_args.no_gpu,
                vad_sensitivity=parsed_args.vad_sensitivity,
                output_format=parsed_args.output_format,
                device_id=parsed_args.device_id,
                sample_rate=parsed_args.sample_rate,
                chunk_size=parsed_args.chunk_size,
                vad_window_size=parsed_args.vad_window_size,
                vad_threshold=parsed_args.vad_threshold,
                show_confidence=not parsed_args.no_confidence,
                show_timestamp=not parsed_args.no_timestamp,
            )

            return config

        except ValueError as e:
            self.parser.error(f"配置验证失败: {e}")
        except Exception as e:
            self.parser.error(f"参数解析失败: {e}")

    def get_default_config(self) -> Config:
        """
        获取默认配置

        Returns:
            Config: 使用默认值的配置对象

        Note:
            模型路径需要单独设置，因为没有合理的默认值
        """
        return Config(
            model_path="models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx",  # 需要用户指定
            input_source="microphone",
            use_gpu=True,
            vad_sensitivity=0.5,
            output_format="text",
            device_id=None,
            sample_rate=16000,
            chunk_size=1024,
            vad_window_size=0.512,
            vad_threshold=0.5,
            show_confidence=True,
            show_timestamp=True,
        )

    def validate_config(self, config: Config) -> bool:
        """
        验证配置对象

        Args:
            config: 要验证的配置对象

        Returns:
            bool: 验证是否通过

        Raises:
            ValueError: 配置验证失败
        """
        try:
            config.validate()
            return True
        except ValueError:
            raise

    def print_help(self):
        """打印帮助信息"""
        self.parser.print_help()

    def print_config(self, config: Config):
        """
        打印配置信息

        Args:
            config: 要打印的配置对象
        """
        print("当前配置:")
        print(f"  模型路径: {config.model_path}")
        print(f"  输入源: {config.input_source}")
        print(f"  GPU加速: {'启用' if config.use_gpu else '禁用'}")
        print(f"  VAD敏感度: {config.vad_sensitivity}")
        print(f"  采样率: {config.sample_rate}Hz")
        print(f"  音频块大小: {config.chunk_size}")
        print(f"  输出格式: {config.output_format}")
        if config.device_id is not None:
            print(f"  音频设备ID: {config.device_id}")
        print(f"  显示置信度: {'是' if config.show_confidence else '否'}")
        print(f"  显示时间戳: {'是' if config.show_timestamp else '否'}")