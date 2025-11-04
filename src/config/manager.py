"""
配置管理器

负责命令行参数解析、配置验证和默认值管理
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from .models import Config, SubtitleDisplayConfig


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
使用示例 - 实时转录:
  %(prog)s --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source microphone
  %(prog)s --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-source system --no-gpu

使用示例 - 媒体文件转字幕:
  %(prog)s --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-file video.mp4
  %(prog)s --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-file video1.mp4 audio1.mp3 --output-dir subtitles/
  %(prog)s --model-path models\sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17\model.onnx --input-file videos/ --subtitle-format srt

支持的输入模式:
  实时转录:     --input-source (microphone/system)
  离线文件:     --input-file (单文件/多文件/目录)

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

        # 输入模式 - 互斥组
        input_group = parser.add_mutually_exclusive_group(required=True)
        input_group.add_argument(
            "--input-source",
            type=str,
            choices=["microphone", "system"],
            help="实时音频输入源: microphone(麦克风) 或 system(系统音频)"
        )
        input_group.add_argument(
            "--input-file",
            type=str,
            nargs='+',
            metavar="FILE",
            help="离线文件输入: 单个文件、多个文件或目录路径"
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
            help="实时转录输出格式 (默认: text)"
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

        # 字幕生成参数 (离线文件模式)
        subtitle = parser.add_argument_group("字幕生成参数 (--input-file模式)")
        subtitle.add_argument(
            "--output-dir",
            type=str,
            metavar="DIR",
            help="字幕输出目录 (默认: 与输入文件同目录)"
        )
        subtitle.add_argument(
            "--subtitle-format",
            type=str,
            default="srt",
            choices=["srt", "vtt", "ass"],
            help="字幕格式 (默认: srt)"
        )
        subtitle.add_argument(
            "--keep-temp",
            action="store_true",
            help="保留临时音频文件 (用于调试)"
        )
        subtitle.add_argument(
            "--verbose",
            action="store_true",
            help="显示详细处理过程"
        )

        # 字幕显示参数 (实时转录模式)
        subtitle_display = parser.add_argument_group("字幕显示参数 (--input-source模式)")
        subtitle_display.add_argument(
            "--show-subtitles",
            action="store_true",
            help="启用屏幕字幕显示 (仅在--input-source模式下有效)"
        )
        subtitle_display.add_argument(
            "--subtitle-position",
            type=str,
            choices=["top", "center", "bottom"],
            default="bottom",
            help="字幕位置: top(顶部)/center(居中)/bottom(底部) (默认: bottom)"
        )
        subtitle_display.add_argument(
            "--subtitle-font-size",
            type=int,
            default=24,
            metavar="INT",
            help="字幕字体大小 (默认: 24)"
        )
        subtitle_display.add_argument(
            "--subtitle-font-family",
            type=str,
            default="Microsoft YaHei",
            metavar="FONT",
            help="字幕字体 (默认: Microsoft YaHei)"
        )
        subtitle_display.add_argument(
            "--subtitle-opacity",
            type=float,
            default=0.8,
            metavar="FLOAT",
            help="字幕窗口透明度 (0.1-1.0, 默认: 0.8)"
        )
        subtitle_display.add_argument(
            "--subtitle-max-display-time",
            type=float,
            default=5.0,
            metavar="FLOAT",
            help="字幕最大显示时间，单位秒 (默认: 5.0)"
        )
        subtitle_display.add_argument(
            "--subtitle-text-color",
            type=str,
            default="#FFFFFF",
            metavar="COLOR",
            help="字幕文字颜色 (十六进制格式, 默认: #FFFFFF)"
        )
        subtitle_display.add_argument(
            "--subtitle-bg-color",
            type=str,
            default="#000000",
            metavar="COLOR",
            help="字幕背景颜色 (十六进制格式, 默认: #000000)"
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
                # 媒体文件转字幕参数
                input_file=parsed_args.input_file if hasattr(parsed_args, 'input_file') else None,
                output_dir=parsed_args.output_dir if hasattr(parsed_args, 'output_dir') else None,
                subtitle_format=parsed_args.subtitle_format if hasattr(parsed_args, 'subtitle_format') else "srt",
                keep_temp=parsed_args.keep_temp if hasattr(parsed_args, 'keep_temp') else False,
                verbose=parsed_args.verbose if hasattr(parsed_args, 'verbose') else False,
                # 字幕显示参数
                subtitle_display=SubtitleDisplayConfig(
                    enabled=getattr(parsed_args, 'show_subtitles', False),
                    position=getattr(parsed_args, 'subtitle_position', 'bottom'),
                    font_size=getattr(parsed_args, 'subtitle_font_size', 24),
                    font_family=getattr(parsed_args, 'subtitle_font_family', 'Microsoft YaHei'),
                    opacity=getattr(parsed_args, 'subtitle_opacity', 0.8),
                    max_display_time=getattr(parsed_args, 'subtitle_max_display_time', 5.0),
                    text_color=getattr(parsed_args, 'subtitle_text_color', '#FFFFFF'),
                    background_color=getattr(parsed_args, 'subtitle_bg_color', '#000000')
                ),
            )

            # 手动验证配置 (因为__post_init__不再自动验证)
            config.validate()

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

        # 判断运行模式
        if config.is_realtime_mode():
            print(f"  运行模式: 实时转录")
            print(f"  输入源: {config.input_source}")
            if config.device_id is not None:
                print(f"  音频设备ID: {config.device_id}")
            print(f"  输出格式: {config.output_format}")
            print(f"  显示置信度: {'是' if config.show_confidence else '否'}")
            print(f"  显示时间戳: {'是' if config.show_timestamp else '否'}")

            # 字幕显示配置
            if config.subtitle_display.enabled:
                print(f"  屏幕字幕显示: 启用")
                print(f"    字幕位置: {config.subtitle_display.position}")
                print(f"    字体大小: {config.subtitle_display.font_size}px")
                print(f"    字体: {config.subtitle_display.font_family}")
                print(f"    透明度: {config.subtitle_display.opacity}")
                print(f"    最大显示时间: {config.subtitle_display.max_display_time}秒")
            else:
                print(f"  屏幕字幕显示: 禁用")
        elif config.is_file_mode():
            print(f"  运行模式: 离线文件转字幕")
            print(f"  输入文件: {len(config.input_file)}个文件/目录")
            for f in config.input_file[:3]:  # 最多显示3个
                print(f"    - {f}")
            if len(config.input_file) > 3:
                print(f"    ... 还有 {len(config.input_file) - 3} 个文件")
            print(f"  输出目录: {config.output_dir or '(与输入同目录)'}")
            print(f"  字幕格式: {config.subtitle_format.upper()}")
            print(f"  保留临时文件: {'是' if config.keep_temp else '否'}")
            print(f"  详细模式: {'是' if config.verbose else '否'}")

        print(f"  GPU加速: {'启用' if config.use_gpu else '禁用'}")
        print(f"  VAD敏感度: {config.vad_sensitivity}")
        print(f"  采样率: {config.sample_rate}Hz")
        print(f"  音频块大小: {config.chunk_size}")