"""
简单的字幕显示实现

作为线程安全实现的后备方案，在控制台输出字幕。
"""

import logging
import threading
import time
from typing import Optional

from ..config.models import SubtitleDisplayConfig


class SimpleSubtitleDisplay:
    """
    简单的字幕显示实现

    在控制台输出字幕，作为GUI实现的后备方案。
    线程安全，但���提供GUI显示功能。
    """

    def __init__(self, config: SubtitleDisplayConfig):
        """
        初始化简单字幕显示

        Args:
            config: 字幕显示配置对象
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self._is_running = False
        self._lock = threading.Lock()

        self.logger.info("简单字幕显示组件初始化完成（控制台模式）")

    def start(self) -> None:
        """启动字幕显示"""
        with self._lock:
            if not self._is_running:
                self._is_running = True
                print("\n" + "="*50)
                print("🎬 字幕显示已启动（控制台模式）")
                print("="*50 + "\n")
                self.logger.info("简单字幕显示已启动")

    def stop(self) -> None:
        """停止字幕显示"""
        with self._lock:
            if self._is_running:
                self._is_running = False
                print("\n" + "="*50)
                print("⏹️  字幕显示已停止")
                print("="*50 + "\n")
                self.logger.info("简单字幕显示已停止")

    def show_subtitle(self, text: str, confidence: float = 1.0) -> None:
        """
        显示字幕文本

        Args:
            text: 要显示的字幕文本
            confidence: 转录置信度 (0.0-1.0)
        """
        if not self._is_running:
            return

        # 清理文本
        clean_text = text.strip()
        if not clean_text:
            return

        # 格式化输出
        timestamp = time.strftime("%H:%M:%S")
        confidence_str = f"({confidence:.2f})" if confidence < 0.9 else ""

        output_text = f"[{timestamp}] {confidence_str} 📺 {clean_text}"

        print(f"\033[92m{output_text}\033[0m")  # 绿色输出
        self.logger.info(f"显示字幕: {clean_text}")

    def clear_subtitle(self) -> None:
        """清除当前显示的字幕"""
        # 在控制台模式下，清除操作是可选的
        pass

    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._is_running