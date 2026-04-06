#!/usr/bin/env python3
"""
Speech2Subtitles GUI启动程序

基于PySide6的图形用户界面，提供更友好的用户体验
"""

import sys
import logging
import logging.handlers
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def setup_logging(
    level: str = "INFO",
    console_enabled: bool = False,
    file_enabled: bool = True,
) -> None:
    """配置日志系统

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        console_enabled: 是否输出到控制台
        file_enabled: 是否输出到日志文件
    """
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)
    root_logger = logging.getLogger()

    # force=True 等效处理：清理历史 handler，避免重复输出
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if file_enabled:
        log_dir = project_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_dir / "gui.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    if console_enabled:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # 没有任何输出目标时挂一个空 handler，避免日志回退到控制台
    if not root_logger.handlers:
        root_logger.addHandler(logging.NullHandler())

    # 设置第三方库的日志级别
    logging.getLogger('pyaudio').setLevel(logging.WARNING)
    logging.getLogger('onnxruntime').setLevel(logging.WARNING)
    logging.getLogger('torch').setLevel(logging.WARNING)


def main():
    """GUI主程序入口"""
    # 配置日志
    setup_logging(level="INFO", console_enabled=False, file_enabled=True)
    logger = logging.getLogger(__name__)

    logger.info("启动Speech2Subtitles GUI")

    try:
        # 导入PySide6
        from PySide6.QtWidgets import QApplication
        from src.gui.main_window import MainWindow

        # 创建Qt应用
        app = QApplication(sys.argv)
        app.setApplicationName("Speech2Subtitles")
        app.setOrganizationName("Speech2Subtitles")
        app.setStyle("Fusion")  # 使用Fusion风格，更现代

        # 创建主窗口
        window = MainWindow()
        window.show()

        logger.info("GUI窗口已显示")

        # 运行事件循环
        sys.exit(app.exec())

    except ImportError as e:
        print(f"\n错误: 无法导入PySide6")
        print(f"详细信息: {e}")
        print("\n请安装PySide6:")
        print("  uv pip install PySide6")
        print("  或")
        print("  pip install PySide6")
        sys.exit(1)

    except Exception as e:
        logger.error(f"GUI启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
