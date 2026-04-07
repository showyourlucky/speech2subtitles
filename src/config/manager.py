"""
配置管理器

负责命令行参数解析、配置验证和默认值管理
"""

import argparse
import sys
from typing import Optional, Dict, Any, Set, List

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
使用示例 - 实时转录:
  %(prog)s --model-path models\\sherpa-onnx-sense-voice-funasr-nano-2025-12-17\\model.onnx --input-source microphone
  %(prog)s --model-path models\\sherpa-onnx-sense-voice-funasr-nano-2025-12-17\\model.onnx --input-source system --no-gpu

使用示例 - 媒体文件转字幕:
  %(prog)s --model-path models\\sherpa-onnx-sense-voice-funasr-nano-2025-12-17\\model.onnx --input-file video.mp4
  %(prog)s --model-path models\\sherpa-onnx-sense-voice-funasr-nano-2025-12-17\\model.onnx --input-file video1.mp4 audio1.mp3 --output-dir subtitles/
  %(prog)s --model-path models\\sherpa-onnx-sense-voice-funasr-nano-2025-12-17\\model.onnx --input-file videos/ --subtitle-format srt

支持的输入模式:
  实时转录:     --input-source (microphone/system)
  离线文件:     --input-file (单文件/多文件/目录)

模型要求:
  支持 .onnx 和 .bin 格式的sense-voice模型文件
            """
        )

        # 运行参数（未传入时使用配置文件中的值）
        required = parser.add_argument_group("运行参数（可选）")
        required.add_argument(
            "--model-path",
            type=str,
            required=False,
            help="sense-voice模型文件路径 (.onnx 或 .bin，未指定时沿用配置文件)"
        )

        # 输入模式 - 互斥组
        input_group = parser.add_mutually_exclusive_group(required=False)
        input_group.add_argument(
            "--input-source",
            type=str,
            choices=["microphone", "system"],
            help="实时音频输入源: microphone(麦克风) 或 system(系统音频)，未指定时沿用配置文件"
        )
        input_group.add_argument(
            "--input-file",
            type=str,
            nargs='+',
            metavar="FILE",
            help="离线文件输入: 单个文件、多个文件或目录路径，未指定时沿用配置文件"
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
        optional.add_argument(
            "--transcription-language",
            type=str,
            metavar="LANG",
            help="转录语言提示 (auto/zh/en，默认自动)"
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
            raw_args = self._resolve_raw_args(args)
            parsed_args = self.parser.parse_args(raw_args)
            explicit_options = self._extract_explicit_options(raw_args)

            cli_dict = self._args_to_dict(parsed_args, explicit_options)
            # CLI 解析路径统一走 v2 构建，确保扁平覆盖键可被兼容映射正确应用
            config = Config.from_dict_v2(cli_dict)

            # 手动验证配置 (因为__post_init__不再自动验证)
            config.validate()

            return config

        except ValueError as e:
            self.parser.error(f"配置验证失败: {e}")
        except Exception as e:
            self.parser.error(f"参数解析失败: {e}")

    def parse_arguments_to_dict(self, args: Optional[list] = None) -> Dict[str, Any]:
        """解析命令行参数并转换为字典"""
        raw_args = self._resolve_raw_args(args)
        parsed_args = self.parser.parse_args(raw_args)
        explicit_options = self._extract_explicit_options(raw_args)
        return self._args_to_dict(parsed_args, explicit_options)

    def parse_cli_overrides(self, args: Optional[list] = None) -> Dict[str, Any]:
        """解析CLI为覆盖字典（用于ConfigLoader合并）"""
        raw_args = self._resolve_raw_args(args)
        parsed_args = self.parser.parse_args(raw_args)
        explicit_options = self._extract_explicit_options(raw_args)
        return self._args_to_dict(parsed_args, explicit_options)

    def _resolve_raw_args(self, args: Optional[list]) -> List[str]:
        """规范化CLI参数列表，None时读取当前进程参数"""
        if args is None:
            return list(sys.argv[1:])
        return list(args)

    def _extract_explicit_options(self, args: List[str]) -> Set[str]:
        """
        提取用户显式输入的选项名（如 --vad-threshold）

        说明:
            - 支持 `--key value` 与 `--key=value` 两种形式
            - 只记录选项名，不记录值
        """
        explicit: Set[str] = set()
        for token in args:
            if not isinstance(token, str):
                continue
            if not token.startswith("--"):
                continue
            explicit.add(token.split("=", 1)[0])
        return explicit

    def _args_to_dict(
        self,
        parsed_args: argparse.Namespace,
        explicit_options: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """将解析后的命令行参数转换为配置字典"""
        explicit_options = explicit_options or set()

        # 仅显式传参才写入覆盖字典，其余参数沿用 config/gui_config.json
        cli_dict: Dict[str, Any] = {}

        def is_explicit(flag: str) -> bool:
            return flag in explicit_options

        # 运行时参数
        if is_explicit("--model-path"):
            cli_dict["model_path"] = parsed_args.model_path
        if is_explicit("--input-source"):
            cli_dict["input_source"] = parsed_args.input_source
        if is_explicit("--input-file"):
            cli_dict["input_file"] = parsed_args.input_file
        if is_explicit("--no-gpu"):
            cli_dict["use_gpu"] = not parsed_args.no_gpu
        if is_explicit("--transcription-language"):
            cli_dict["transcription_language"] = parsed_args.transcription_language

        # 音频参数
        if is_explicit("--sample-rate"):
            cli_dict["sample_rate"] = parsed_args.sample_rate
        if is_explicit("--chunk-size"):
            cli_dict["chunk_size"] = parsed_args.chunk_size
        if is_explicit("--device-id"):
            cli_dict["device_id"] = parsed_args.device_id

        # VAD 参数（显式覆盖活动方案）
        if is_explicit("--vad-threshold"):
            cli_dict["vad_threshold"] = parsed_args.vad_threshold
        elif is_explicit("--vad-sensitivity"):
            cli_dict["vad_threshold"] = parsed_args.vad_sensitivity
        if is_explicit("--vad-window-size"):
            cli_dict["vad_window_size"] = parsed_args.vad_window_size

        # 输出参数
        if is_explicit("--output-format"):
            cli_dict["output_format"] = parsed_args.output_format
        if is_explicit("--no-confidence"):
            cli_dict["show_confidence"] = not parsed_args.no_confidence
        if is_explicit("--no-timestamp"):
            cli_dict["show_timestamp"] = not parsed_args.no_timestamp

        # 字幕文件参数
        if is_explicit("--output-dir"):
            cli_dict["output_dir"] = parsed_args.output_dir
        if is_explicit("--subtitle-format"):
            cli_dict["subtitle_format"] = parsed_args.subtitle_format
        if is_explicit("--keep-temp"):
            cli_dict["keep_temp"] = parsed_args.keep_temp
        if is_explicit("--verbose"):
            cli_dict["verbose"] = parsed_args.verbose

        # 字幕显示参数（部分更新）
        subtitle_display_updates: Dict[str, Any] = {}
        if is_explicit("--show-subtitles"):
            subtitle_display_updates["enabled"] = parsed_args.show_subtitles
        if is_explicit("--subtitle-position"):
            subtitle_display_updates["position"] = parsed_args.subtitle_position
        if is_explicit("--subtitle-font-size"):
            subtitle_display_updates["font_size"] = parsed_args.subtitle_font_size
        if is_explicit("--subtitle-font-family"):
            subtitle_display_updates["font_family"] = parsed_args.subtitle_font_family
        if is_explicit("--subtitle-opacity"):
            subtitle_display_updates["opacity"] = parsed_args.subtitle_opacity
        if is_explicit("--subtitle-max-display-time"):
            subtitle_display_updates["max_display_time"] = parsed_args.subtitle_max_display_time
        if is_explicit("--subtitle-text-color"):
            subtitle_display_updates["text_color"] = parsed_args.subtitle_text_color
        if is_explicit("--subtitle-bg-color"):
            subtitle_display_updates["background_color"] = parsed_args.subtitle_bg_color
        if subtitle_display_updates:
            cli_dict["subtitle_display"] = subtitle_display_updates

        return self._prune_none(cli_dict)

    def _prune_none(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """移除None值，避免覆盖文件配置"""
        cleaned: Dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, dict):
                nested = self._prune_none(value)
                if nested:
                    cleaned[key] = nested
            elif value is not None:
                cleaned[key] = value
        return cleaned
    def get_default_config(self) -> Config:
        """
        获取默认配置

        Returns:
            Config: 使用默认值的配置对象

        Note:
            模型路径需要单独设置，因为没有合理的默认值
        """
        return Config.create_default()

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
