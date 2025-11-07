"""
导出器模块

提供多种格式的转录记录导出功能：
- TXT: 纯文本格式
- SRT: 字幕文件格式
- JSON: 结构化数据格式
- VTT: WebVTT字幕格式
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import timedelta
import json

from src.gui.models.history_models import TranscriptionRecord

logger = logging.getLogger(__name__)


class BaseExporter:
    """导出器基类"""

    def export(self, record: TranscriptionRecord, output_path: str, options: Dict[str, Any]) -> bool:
        """导出记录

        Args:
            record: 转录记录
            output_path: 输出文件路径
            options: 导出选项

        Returns:
            bool: 是否成功
        """
        raise NotImplementedError

    def _validate_output_path(self, output_path: str) -> bool:
        """验证输出路径

        Args:
            output_path: 输出文件路径

        Returns:
            bool: 路径是否有效
        """
        try:
            path = Path(output_path)
            # 确保父目录存在
            path.parent.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Invalid output path: {e}")
            return False


class TXTExporter(BaseExporter):
    """TXT格式导出器"""

    def export(self, record: TranscriptionRecord, output_path: str, options: Dict[str, Any]) -> bool:
        """导出为TXT格式

        Args:
            record: 转录记录
            output_path: 输出文件路径
            options: 导出选项
                - include_timestamp: 是否包含时间戳
                - include_metadata: 是否包含元数据

        Returns:
            bool: 是否成功
        """
        try:
            if not self._validate_output_path(output_path):
                return False

            with open(output_path, 'w', encoding='utf-8') as f:
                # 元数据
                if options.get('include_metadata', False):
                    f.write(f"# 转录记录\n")
                    f.write(f"# 时间: {record.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"# 音频源: {record.get_audio_source_display()}\n")
                    if record.audio_path:
                        f.write(f"# 文件: {record.audio_path}\n")
                    f.write(f"# 时长: {record.get_duration_display()}\n")
                    f.write(f"# 模型: {record.model_name}\n")
                    f.write(f"\n")

                # 时间戳
                if options.get('include_timestamp', True):
                    timestamp_str = record.timestamp.strftime('[%H:%M:%S]')
                    f.write(f"{timestamp_str} {record.text}\n")
                else:
                    f.write(f"{record.text}\n")

            logger.info(f"Exported to TXT: {output_path}")
            return True

        except Exception as e:
            logger.error(f"TXT export failed: {e}")
            return False


class SRTExporter(BaseExporter):
    """SRT字幕格式导出器"""

    def export(self, record: TranscriptionRecord, output_path: str, options: Dict[str, Any]) -> bool:
        """导出为SRT字幕格式

        Args:
            record: 转录记录
            output_path: 输出文件路径
            options: 导出选项

        Returns:
            bool: 是否成功
        """
        try:
            if not self._validate_output_path(output_path):
                return False

            with open(output_path, 'w', encoding='utf-8') as f:
                # SRT格式示例:
                # 1
                # 00:00:00,000 --> 00:00:05,000
                # 转录文本内容

                # 简化实现：整个转录作为一个字幕块
                f.write("1\n")
                f.write(f"00:00:00,000 --> {self._format_timecode(record.duration)}\n")
                f.write(f"{record.text}\n")

            logger.info(f"Exported to SRT: {output_path}")
            return True

        except Exception as e:
            logger.error(f"SRT export failed: {e}")
            return False

    def _format_timecode(self, seconds: float) -> str:
        """格式化时间码为SRT格式

        Args:
            seconds: 秒数

        Returns:
            str: SRT时间码 (HH:MM:SS,mmm)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


class JSONExporter(BaseExporter):
    """JSON格式导出器"""

    def export(self, record: TranscriptionRecord, output_path: str, options: Dict[str, Any]) -> bool:
        """导出为JSON格式

        Args:
            record: 转录记录
            output_path: 输出文件路径
            options: 导出选项

        Returns:
            bool: 是否成功
        """
        try:
            if not self._validate_output_path(output_path):
                return False

            # 构建导出数据
            data = record.to_dict()

            # 添加额外的显示信息
            if options.get('include_display_info', False):
                data['display_info'] = {
                    'audio_source_display': record.get_audio_source_display(),
                    'duration_display': record.get_duration_display(),
                    'text_preview': record.get_text_preview()
                }

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported to JSON: {output_path}")
            return True

        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            return False


class VTTExporter(BaseExporter):
    """WebVTT字幕格式导出器"""

    def export(self, record: TranscriptionRecord, output_path: str, options: Dict[str, Any]) -> bool:
        """导出为VTT字幕格式

        Args:
            record: 转录记录
            output_path: 输出文件路径
            options: 导出选项

        Returns:
            bool: 是否成功
        """
        try:
            if not self._validate_output_path(output_path):
                return False

            with open(output_path, 'w', encoding='utf-8') as f:
                # WebVTT格式
                f.write("WEBVTT\n\n")
                f.write("1\n")
                f.write(f"00:00:00.000 --> {self._format_timecode(record.duration)}\n")
                f.write(f"{record.text}\n")

            logger.info(f"Exported to VTT: {output_path}")
            return True

        except Exception as e:
            logger.error(f"VTT export failed: {e}")
            return False

    def _format_timecode(self, seconds: float) -> str:
        """格式化时间码为VTT格式

        Args:
            seconds: 秒数

        Returns:
            str: VTT时间码 (HH:MM:SS.mmm)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


class BatchExporter:
    """批量导出器"""

    def __init__(self):
        """初始化批量导出器"""
        self.exporter_factory = ExporterFactory()

    def export_multiple(self, records: List[TranscriptionRecord], output_dir: str,
                       format_type: str, options: Dict[str, Any] = None) -> Tuple[int, List[str]]:
        """批量导出多个记录

        Args:
            records: 转录记录列表
            output_dir: 输出目录
            format_type: 导出格式
            options: 导出选项

        Returns:
            Tuple[int, List[str]]: (成功数量, 错误消息列表)
        """
        if not options:
            options = {}

        success_count = 0
        errors = []

        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            exporter = self.exporter_factory.get_exporter(format_type)

            for i, record in enumerate(records):
                try:
                    # 生成文件名
                    timestamp_str = record.timestamp.strftime('%Y%m%d_%H%M%S')
                    filename = f"transcription_{timestamp_str}_{i+1}.{format_type}"
                    file_path = output_path / filename

                    # 导出记录
                    if exporter.export(record, str(file_path), options):
                        success_count += 1
                        logger.debug(f"Exported record {i+1} to {file_path}")
                    else:
                        errors.append(f"记录 {i+1} 导出失败")

                except Exception as e:
                    error_msg = f"记录 {i+1} 导出出错: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)

            logger.info(f"Batch export completed: {success_count}/{len(records)} successful")
            return success_count, errors

        except Exception as e:
            error_msg = f"批量导出失败: {e}"
            errors.append(error_msg)
            logger.error(error_msg)
            return 0, errors


class ExporterFactory:
    """导出器工厂类"""

    @staticmethod
    def get_exporter(format_type: str) -> BaseExporter:
        """根据格式类型获取导出器

        Args:
            format_type: 格式类型 (txt/srt/json/vtt)

        Returns:
            BaseExporter: 导出器实例

        Raises:
            ValueError: 不支持的格式
        """
        exporters = {
            'txt': TXTExporter(),
            'srt': SRTExporter(),
            'json': JSONExporter(),
            'vtt': VTTExporter(),
        }

        exporter = exporters.get(format_type.lower())
        if not exporter:
            raise ValueError(f"Unsupported format: {format_type}")

        return exporter

    @staticmethod
    def get_supported_formats() -> List[str]:
        """获取支持的导出格式列表

        Returns:
            List[str]: 支持的格式列表
        """
        return ['txt', 'srt', 'json', 'vtt']

    @staticmethod
    def get_format_description(format_type: str) -> str:
        """获取格式的描述

        Args:
            format_type: 格式类型

        Returns:
            str: 格式描述
        """
        descriptions = {
            'txt': 'TXT 文本文件',
            'srt': 'SRT 字幕文件',
            'json': 'JSON 数据文件',
            'vtt': 'WebVTT 网页字幕'
        }

        return descriptions.get(format_type.lower(), '未知格式')

    @staticmethod
    def get_file_extension(format_type: str) -> str:
        """获取格式的文件扩展名

        Args:
            format_type: 格式类型

        Returns:
            str: 文件扩展名
        """
        return f".{format_type.lower()}"