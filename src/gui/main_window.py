"""主窗口实现
PySide6 GUI的主入口点
"""

import logging
import sys
from typing import Optional
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QMessageBox, QStatusBar, QMenuBar, QMenu,
    QComboBox, QLabel, QGroupBox, QPushButton
)
from PySide6.QtCore import Slot, Qt, QThread
from PySide6.QtGui import QAction, QCloseEvent

# 导入自定义组件
from src.gui.widgets.control_panel import TranscriptionControlPanel
from src.gui.widgets.audio_source_selector import AudioSourceSelector
from src.gui.widgets.status_monitor import StatusMonitorPanel
from src.gui.widgets.result_display import TranscriptionResultDisplay
from src.gui.bridges.pipeline_bridge import PipelineBridge
from src.gui.bridges.config_bridge import ConfigBridge
from src.gui.models.gui_models import TranscriptionState, AudioSourceInfo

# 导入 Phase 2 新增组件
from src.gui.dialogs.settings_dialog import SettingsDialog
from src.gui.dialogs.export_dialog import ExportDialog
from src.gui.dialogs.history_dialog import HistoryDialog
from src.gui.dialogs.file_transcription_dialog import FileTranscriptionDialog
from src.gui.storage.history_manager import HistoryManager
from src.gui.models.history_models import TranscriptionRecord

# 导入核心组件
from src.config.manager import ConfigManager
from src.config.models import Config, SubtitleDisplayConfig
from src.coordinator.pipeline import TranscriptionPipeline
from src.audio.models import AudioSourceType
from src.transcription.models import TranscriptionResult
from datetime import datetime
import json
from dataclasses import asdict

logger = logging.getLogger(__name__)


class PipelineThread(QThread):
    """Pipeline运行线程

    将TranscriptionPipeline放在独立线程运行，避免阻塞GUI
    """

    def __init__(self, pipeline: TranscriptionPipeline, parent=None):
        """初始化Pipeline线程

        Args:
            pipeline: TranscriptionPipeline实例
            parent: 父对象
        """
        super().__init__(parent)
        self.pipeline = pipeline

    def run(self) -> None:
        """线程主循环

        Pipeline.run()方法会：
        1. 调用start()完成初始化
        2. 进入阻塞主循环直到停止
        """
        try:
            logger.info("管道线程已启动")

            # Pipeline的run()会内部调用start()并阻塞直到停止
            # start()会调用initialize()初始化所有组件
            self.pipeline.run()

        except KeyboardInterrupt:
            logger.info("管道线程被用户中断")
        except Exception as e:
            logger.error(f"管道线程错误: {e}", exc_info=True)
        finally:
            # 确保Pipeline停止
            try:
                if self.pipeline and self.pipeline.is_running:
                    self.pipeline.stop()
            except Exception as e:
                logger.warning(f"Error stopping pipeline in thread cleanup: {e}")

            logger.info("Pipeline thread stopped")


class MainWindow(QMainWindow):
    """主窗口类

    核心职责:
        1. 创建和管理所有UI组件
        2. 集成Pipeline和Config桥接器
        3. 处理用户交互和事件
        4. 管理应用生命周期
    """

    def __init__(self):
        """初始化主窗口"""
        super().__init__()

        # 核心组件（先初始化为None）
        self.config: Optional[Config] = None
        self.config_bridge: Optional[ConfigBridge] = None
        self.pipeline: Optional[TranscriptionPipeline] = None
        self.pipeline_bridge: Optional[PipelineBridge] = None
        self.pipeline_thread: Optional[PipelineThread] = None

        # Phase 2 新增组件
        self.history_manager: Optional[HistoryManager] = None

        # 文件转录队列管理
        self.file_queue: list[str] = []  # 待转录文件队列
        self.current_file_index: int = -1  # 当前转录文件索引
        self.is_batch_mode: bool = False  # 是否处于批量文件转录模式

        # UI组件
        self.control_panel: Optional[TranscriptionControlPanel] = None
        self.audio_source_selector: Optional[AudioSourceSelector] = None
        self.status_monitor: Optional[StatusMonitorPanel] = None
        self.result_display: Optional[TranscriptionResultDisplay] = None

        # VAD方案选择器
        self.vad_profile_selector: Optional[QComboBox] = None
        self.vad_settings_button: Optional[QPushButton] = None

        # 字幕窗口（保留tkinter实现）
        self.subtitle_display = None

        # 初始化配置
        self._init_config()

        # 初始化 Phase 2 组件
        self._init_phase2_components()

        # 设置UI
        self._setup_ui()

        # 连接信号槽
        self._connect_signals()

        # 应用启动后的初始化
        self._post_init()

        logger.info("主窗口已初始化")

    def _init_config(self) -> None:
        """初始化配置系统"""
        try:
            self.config_bridge = ConfigBridge()
            self.config = self.config_bridge.load_config()

            # 为GUI使用设置合理的默认值
            if not self.config.model_path or self.config.model_path == "":
                # 尝试查找默认模型
                default_model_path = Path("models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/model.onnx")
                if default_model_path.exists():
                    self.config.model_path = str(default_model_path.absolute())

            # 设置默认输入源为麦克风
            if not self.config.input_source:
                self.config.input_source = "microphone"

            logger.info("配置初始化完成")

        except Exception as e:
            logger.error(f"配置初始化失败: {e}")
            QMessageBox.critical(
                self,
                "配置错误",
                f"配置初始化失败: {e}\n\n程序将退出。"
            )
            sys.exit(1)

    def _init_phase2_components(self) -> None:
        """初始化 Phase 2 组件"""
        try:
            # 初始化历史记录管理器
            self.history_manager = HistoryManager()
            logger.info("Phase 2 components initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Phase 2 components: {e}")
            # 不阻止程序启动，只记录错误

    def _setup_ui(self) -> None:
        """设置UI"""
        # 设置窗口属性
        self.setWindowTitle("Speech2Subtitles - 实时语音转录系统")
        self.setGeometry(100, 100, 1000, 700)

        # 创建菜单栏
        self._create_menu_bar()

        # 创建中心组件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout(central_widget)

        # 创建水平分割器（左右布局）
        h_splitter = QSplitter(Qt.Horizontal)

        # 左侧面板（控制区域）
        left_panel = self._create_left_panel()
        h_splitter.addWidget(left_panel)

        # 右侧面板（显示区域）
        right_panel = self._create_right_panel()
        h_splitter.addWidget(right_panel)

        # 设置分割器比例
        h_splitter.setStretchFactor(0, 1)  # 左侧
        h_splitter.setStretchFactor(1, 2)  # 右侧

        main_layout.addWidget(h_splitter)

        # 创建状态栏
        self._create_status_bar()

        logger.debug("UI设置完成")

    def _create_menu_bar(self) -> None:
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件(&F)")

        # 批量转录文件操作
        batch_transcription_action = QAction("批量转录文件(&B)...", self)
        batch_transcription_action.setShortcut("Ctrl+B")
        batch_transcription_action.triggered.connect(self._show_batch_transcription_dialog)
        file_menu.addAction(batch_transcription_action)

        file_menu.addSeparator()

        # 退出操作
        exit_action = QAction("退出(&X)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 设置菜单（一级菜单）
        settings_menu = menubar.addMenu("设置(&S)")

        preferences_action = QAction("偏好设置(&P)...", self)
        preferences_action.setShortcut("Ctrl+,")
        preferences_action.triggered.connect(self._show_settings_dialog)
        settings_menu.addAction(preferences_action)

        # 新增：历史记录菜单
        history_menu = menubar.addMenu("历史记录(&H)")

        view_history_action = QAction("查看历史记录...", self)
        view_history_action.setShortcut("Ctrl+H")
        view_history_action.triggered.connect(self._show_history_panel)
        history_menu.addAction(view_history_action)

        export_current_action = QAction("导出当前转录...", self)
        export_current_action.setShortcut("Ctrl+E")
        export_current_action.triggered.connect(self._export_current_transcription)
        history_menu.addAction(export_current_action)

        history_menu.addSeparator()

        clear_history_action = QAction("清空历史记录", self)
        clear_history_action.triggered.connect(self._clear_history)
        history_menu.addAction(clear_history_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助(&H)")

        # 关于操作
        about_action = QAction("关于(&A)", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_status_bar(self) -> None:
        """创建状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    def _create_left_panel(self) -> QWidget:
        """创建左侧面板（控制区域）"""
        panel = QWidget()
        # 设置左侧面板的最大宽度，防止长文件名撑宽窗口
        panel.setMaximumWidth(400)
        layout = QVBoxLayout(panel)

        # 音频源选择器
        self.audio_source_selector = AudioSourceSelector()
        layout.addWidget(self.audio_source_selector)

        # VAD方案选择器组件
        vad_group = self._create_vad_profile_selector()
        layout.addWidget(vad_group)

        # 转录控制面板
        self.control_panel = TranscriptionControlPanel()
        layout.addWidget(self.control_panel)

        # 状态监控面板
        self.status_monitor = StatusMonitorPanel()
        layout.addWidget(self.status_monitor)

        # 添加弹簧（将组件推到顶部）
        layout.addStretch()

        return panel

    def _create_vad_profile_selector(self) -> QWidget:
        """创建VAD方案选择器组件

        Returns:
            QWidget: VAD方案选择组件
        """
        group_box = QGroupBox("VAD方案")
        layout = QVBoxLayout(group_box)

        # 方案选择器和设置按钮的水平布局
        selector_layout = QHBoxLayout()

        # 方案下拉选择框
        self.vad_profile_selector = QComboBox()
        self.vad_profile_selector.setMinimumHeight(30)
        self.vad_profile_selector.currentIndexChanged.connect(self._on_vad_profile_changed)
        selector_layout.addWidget(self.vad_profile_selector, stretch=1)

        # 设置按钮（快捷打开VAD设置页）
        self.vad_settings_button = QPushButton("⚙")
        self.vad_settings_button.setMaximumWidth(40)
        self.vad_settings_button.setToolTip("打开VAD设置")
        self.vad_settings_button.clicked.connect(self._open_vad_settings)
        selector_layout.addWidget(self.vad_settings_button)

        layout.addLayout(selector_layout)

        # 加载VAD方案列表
        self._load_vad_profiles()

        return group_box

    def _create_right_panel(self) -> QWidget:
        """创建右侧面板（显示区域）"""
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 转录结果显示
        self.result_display = TranscriptionResultDisplay()
        layout.addWidget(self.result_display)

        return panel

    def _connect_signals(self) -> None:
        """连接信号槽"""
        # 控制面板信号
        self.control_panel.start_requested.connect(self._on_start_transcription)
        self.control_panel.pause_requested.connect(self._on_pause_transcription)
        self.control_panel.stop_requested.connect(self._on_stop_transcription)

        # 音频源选择器信号
        self.audio_source_selector.source_changed.connect(self._on_audio_source_changed)

        logger.debug("Signals connected")

    def _post_init(self) -> None:
        """启动后初始化"""
        # 更新状态监控显示
        model_name = Path(self.config.model_path).name if self.config.model_path else "未指定"
        self.status_monitor.update_model(model_name)

        # 检测GPU
        from src.hardware.gpu_detector import GPUDetector
        gpu_detector = GPUDetector()
        gpu_available = gpu_detector.detect_cuda()
        gpu_info = f"(CUDA)" if gpu_available else ""
        self.status_monitor.update_gpu_status(gpu_available, gpu_info)

        # 更新音频源显示
        source_info = self.audio_source_selector.get_selected_source()
        if source_info:
            self.status_monitor.update_audio_source(str(source_info))

    @Slot()
    def _on_start_transcription(self) -> None:
        """处理开始转录请求"""
        try:
            # 获取当前音频源
            source_info = self.audio_source_selector.get_selected_source()
            if not source_info:
                QMessageBox.warning(self, "配置错误", "请先选择音频源")
                return

            # 验证文件模式的文件路径
            if source_info.source_type == AudioSourceType.FILE:
                # 获取所有文件
                file_paths = self.audio_source_selector.get_file_paths()
                if not file_paths:
                    QMessageBox.warning(self, "文件错误", "请选择有效的音频或视频文件")
                    return

                # 验证所有文件存在
                invalid_files = [f for f in file_paths if not Path(f).exists()]
                if invalid_files:
                    QMessageBox.warning(
                        self, "文件错误",
                        "以下文件不存在:\n" + "\n".join(invalid_files[:5])
                    )
                    return

                # 初始化文件队列
                self.file_queue = file_paths.copy()
                self.current_file_index = 0
                self.is_batch_mode = len(file_paths) > 1

                logger.info(f"批处理模式: {self.is_batch_mode}, 文件数: {len(self.file_queue)}")

                # 开始第一个文件的转录
                self._start_file_transcription(self.file_queue[0])
                return  # 文件模式单独处理，不继续执行下面的代码

            # 更新配置（实时音频模式）
            self._update_config_from_ui(source_info)

            # 验证配置
            success, error_msg = self.config_bridge.validate_config(self.config)
            if not success:
                QMessageBox.warning(self, "配置错误", f"配置验证失败:\n{error_msg}")
                return

            # 额外的模型文件验证
            if not self.config.model_path or not Path(self.config.model_path).exists():
                QMessageBox.critical(
                    self,
                    "模型文件错误",
                    f"模型文件不存在:\n{self.config.model_path}\n\n"
                    "请在配置中指定有效的模型文件路径。"
                )
                return

            # 创建Pipeline
            logger.info("创建转录管道e...")
            self.pipeline = TranscriptionPipeline(self.config)

            # 创建桥接器
            self.pipeline_bridge = PipelineBridge(self.pipeline)

            # 连接Pipeline信号
            self._connect_pipeline_signals()

            # 启动字幕显示（如果配置启用）- 在Pipeline启动前初始化
            if self.config.subtitle_display and self.config.subtitle_display.enabled:
                self._start_subtitle_display()

            # 在独立线程启动Pipeline
            self.pipeline_thread = PipelineThread(self.pipeline, self)
            self.pipeline_thread.start()

            # 更新UI状态
            self.control_panel.set_state(TranscriptionState.RUNNING)
            self.audio_source_selector.set_enabled(False)
            self.status_monitor.update_status("✅ 运行中")
            self.status_bar.showMessage("转录已启动")

            logger.info("转录开始")

        except Exception as e:
            logger.error(f"无法开始转录: {e}")
            QMessageBox.critical(
                self,
                "启动失败",
                f"无法启动转录:\n{e}"
            )
            self.control_panel.set_state(TranscriptionState.ERROR)

    @Slot()
    def _on_pause_transcription(self) -> None:
        """处理暂停转录请求"""
        # TODO: 实现暂停功能
        logger.warning("暂停功能尚未实现")
        QMessageBox.information(self, "功能提示", "暂停功能将在后续版本实现")

    def _start_file_transcription(self, file_path: str) -> None:
        """开始单个文件的转录

        Args:
            file_path: 文件路径
        """
        try:
            # 更新状态显示
            file_name = Path(file_path).name
            if self.is_batch_mode:
                progress = f"[{self.current_file_index + 1}/{len(self.file_queue)}]"
                self.status_bar.showMessage(f"{progress} 正在转录: {file_name}")
                logger.info(f"Starting file {self.current_file_index + 1}/{len(self.file_queue)}: {file_name}")
            else:
                self.status_bar.showMessage(f"正在转录: {file_name}")
                logger.info(f"开始文件转录: {file_name}")

            # 更新配置为当前文件
            source_info = AudioSourceInfo(
                source_type=AudioSourceType.FILE,
                display_name=file_name,
                file_path=file_path
            )
            self._update_config_from_ui(source_info)

            # 验证配置
            success, error_msg = self.config_bridge.validate_config(self.config)
            if not success:
                raise ValueError(f"配置验证失败: {error_msg}")

            # 验证模型文件
            if not self.config.model_path or not Path(self.config.model_path).exists():
                raise FileNotFoundError(f"模型文件不存在: {self.config.model_path}")

            # 创建Pipeline
            logger.info("为文件创建 TranscriptionPipeline...")
            self.pipeline = TranscriptionPipeline(self.config)

            # 创建桥接器
            self.pipeline_bridge = PipelineBridge(self.pipeline)

            # 连接Pipeline信号
            self._connect_pipeline_signals()

            # 启动字幕显示（如果配置启用）
            if self.config.subtitle_display and self.config.subtitle_display.enabled:
                self._start_subtitle_display()

            # 在独立线程启动Pipeline
            self.pipeline_thread = PipelineThread(self.pipeline, self)
            self.pipeline_thread.start()

            # 更新UI状态
            self.control_panel.set_state(TranscriptionState.RUNNING)
            self.audio_source_selector.set_enabled(False)
            self.status_monitor.update_status("✅ 运行中")

        except Exception as e:
            logger.error(f"无法启动文件转录: {e}")
            QMessageBox.critical(
                self,
                "转录失败",
                f"无法开始转录文件 {Path(file_path).name}:\n{e}"
            )
            self.control_panel.set_state(TranscriptionState.ERROR)
            # 清理队列状态
            self._reset_file_queue()

    def _reset_file_queue(self) -> None:
        """重置文件队列状态"""
        self.file_queue.clear()
        self.current_file_index = -1
        self.is_batch_mode = False
        logger.debug("文件队列重置")

    @Slot()
    def _on_stop_transcription(self) -> None:
        """处理停止转录请求"""
        try:
            if self.pipeline:
                # 停止Pipeline
                self.pipeline.stop()

                # 等待线程结束
                if self.pipeline_thread:
                    self.pipeline_thread.wait(3000)  # 最多等待3秒

                # 清理资源
                self.pipeline = None
                self.pipeline_bridge = None
                self.pipeline_thread = None

                # 停止字幕显示
                if self.subtitle_display:
                    self.subtitle_display.stop()
                    self.subtitle_display = None

            # 清理文件队列
            self._reset_file_queue()

            # 更新UI状态
            self.control_panel.set_state(TranscriptionState.STOPPED)
            self.audio_source_selector.set_enabled(True)
            self.status_monitor.update_status("🔵 已停止")
            self.status_bar.showMessage("转录已停止")

            logger.info("Transcription stopped")

        except Exception as e:
            logger.error(f"无法停止转录: {e}")
            QMessageBox.warning(
                self,
                "停止警告",
                f"停止转录时发生错误:\n{e}"
            )

    @Slot(object)
    def _on_audio_source_changed(self, source_info: AudioSourceInfo) -> None:
        """处理音频源变化

        Args:
            source_info: 音频源信息
        """
        self.status_monitor.update_audio_source(str(source_info))
        logger.debug(f"音频源已更改: {source_info}")

    def _update_config_from_ui(self, source_info: AudioSourceInfo) -> None:
        """从UI更新配置

        Args:
            source_info: 音频源信息
        """
        # 更新音频源
        if source_info.source_type == AudioSourceType.MICROPHONE:
            self.config.input_source = "microphone"
            self.config.input_file = None
        elif source_info.source_type == AudioSourceType.SYSTEM_AUDIO:
            self.config.input_source = "system"
            self.config.input_file = None
        elif source_info.source_type == AudioSourceType.FILE:
            # 文件模式：不设置 input_source，只设置 input_file
            self.config.input_source = None
            # 获取所有文件路径（支持多文件）
            file_paths = self.audio_source_selector.get_file_paths()
            self.config.input_file = file_paths if file_paths else None

        # 注意：这里不立即保存配置，避免在设置对话框操作时产生冲突
        # 配置保存将在设置对话框的保存操作中进行
        # self.config_bridge.save_config(self.config)  # 注释掉立即保存

    def _connect_pipeline_signals(self) -> None:
        """连接Pipeline桥接器信号"""
        if not self.pipeline_bridge:
            return

        # 转录结果信号
        self.pipeline_bridge.new_result.connect(self._on_new_result)

        # 状态变化信号
        self.pipeline_bridge.status_changed.connect(self._on_pipeline_status_changed)

        # 错误信号
        self.pipeline_bridge.error_occurred.connect(self._on_pipeline_error)

        # 音频电平信号
        self.pipeline_bridge.audio_level_changed.connect(
            self.status_monitor.update_audio_level
        )

        # 新增：转录停止信号（用于保存历史记录）
        self.pipeline_bridge.transcription_stopped.connect(self._on_transcription_completed)

        logger.debug("Pipeline signals connected")

    @Slot(object)
    def _on_new_result(self, result: TranscriptionResult) -> None:
        """处理新转录结果

        Args:
            result: 转录结果对象
        """
        # 显示在结果面板
        self.result_display.append_result(result)

        # 更新状态栏
        self.status_bar.showMessage(f"转录: {result.text[:30]}...")

    @Slot(str, str)
    def _on_pipeline_status_changed(self, old_state: str, new_state: str) -> None:
        """处理Pipeline状态变化

        Args:
            old_state: 旧状态
            new_state: 新状态
        """
        logger.info(f"Pipeline state: {old_state} -> {new_state}")

    @Slot(str, str)
    def _on_pipeline_error(self, error_type: str, error_message: str) -> None:
        """处理Pipeline错误

        Args:
            error_type: 错误类型
            error_message: 错误消息
        """
        logger.error(f"Pipeline error: {error_type} - {error_message}")

        # 显示错误对话框
        QMessageBox.critical(
            self,
            "转录错误",
            f"转录过程中发生错误:\n\n{error_message}"
        )

        # 更新UI状态
        self.control_panel.set_state(TranscriptionState.ERROR)
        self.status_monitor.update_status("🔴 错误")

    def _start_subtitle_display(self) -> None:
        """启动字幕显示（tkinter实现）"""
        try:
            # 获取字幕显示组件单例（确保全局只有一个字幕窗口）
            from src.subtitle_display import get_subtitle_display_instance

            self.subtitle_display = get_subtitle_display_instance(self.config.subtitle_display)
            self.subtitle_display.start()

            # 连接信号（将转录结果传递给字幕显示）
            if self.pipeline_bridge:
                # 注意：需要适配信号格式
                self.pipeline_bridge.new_result.connect(self._update_subtitle)

            logger.info("字幕显示开始")

        except Exception as e:
            logger.warning(f"无法启动字幕显示: {e}")

    @Slot(object)
    def _update_subtitle(self, result: TranscriptionResult) -> None:
        """更新字幕显示

        Args:
            result: 转录结果
        """
        if self.subtitle_display and result.is_final:
            try:
                self.subtitle_display.show_subtitle(
                    text=result.text,
                    confidence=result.confidence
                )
            except Exception as e:
                logger.warning(f"更新字幕失败: {e}")

    @Slot()
    def _show_about(self) -> None:
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于 Speech2Subtitles",
            """<h3>Speech2Subtitles</h3>
            <p>实时语音转录系统</p>
            <p>版本: 0.1.0</p>
            <p>基于 sherpa-onnx 和 silero-vad</p>
            <p><a href='https://github.com/yourusername/speech2subtitles'>GitHub仓库</a></p>
            """
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        """窗口关闭事件

        Args:
            event: 关闭事件
        """
        # 如果正在转录，询问用户
        if self.pipeline and self.control_panel._current_state == TranscriptionState.RUNNING:
            reply = QMessageBox.question(
                self,
                "确认退出",
                "转录正在进行中，确定要退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

        # 停止转录
        if self.pipeline:
            self._on_stop_transcription()

        # 停止字幕显示
        if self.subtitle_display:
            self.subtitle_display.stop()

        # 释放转录引擎资源（方案3：关闭主窗口时释放）
        try:
            from src.transcription.engine_manager import TranscriptionEngineManager
            logger.info("释放TranscriptionEngine资源（窗口关闭）")
            TranscriptionEngineManager.release()
        except Exception as e:
            logger.warning(f"释放转录引擎资源时出错: {e}")

        # 接受关闭事件
        event.accept()
        logger.info("主窗口关闭")

    # ========== Phase 2 新增方法 ==========

    @Slot()
    def _show_batch_transcription_dialog(self) -> None:
        """显示批量文件转录对话框"""
        try:
            # 验证模型配置
            if not self.config.model_path or not Path(self.config.model_path).exists():
                QMessageBox.warning(
                    self,
                    "配置错误",
                    "请先在设置中配置转录模型路径。\n\n"
                    "设置 → 偏好设置 → 模型路径"
                )
                return

            # 创建并显示批量转录对话框
            dialog = FileTranscriptionDialog(self.config, self)
            dialog.exec()

            logger.info("批量转录对话框完成")

        except Exception as e:
            logger.error(f"无法显示批量转录对话框: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"打开批量转录对话框失败: {e}")

    @Slot()
    def _show_settings_dialog(self) -> None:
        """显示设置对话框"""
        dialog = SettingsDialog(self.config, self.config_bridge, self)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec()

    @Slot(object)
    def _on_settings_changed(self, new_config: Config) -> None:
        """处理设置变化

        Args:
            new_config: 新配置对象
        """
        self.config = new_config

        # 更新状态监控显示
        model_name = Path(self.config.model_path).name if self.config.model_path else "未指定"
        self.status_monitor.update_model(model_name)

        # 更新GPU状态
        self.status_monitor.update_gpu_status(not self.config.use_gpu)

        logger.info("从对话框更新设置")

    @Slot()
    def _show_history_panel(self) -> None:
        """显示历史记录面板"""
        try:
            if not self.history_manager:
                QMessageBox.warning(self, "错误", "历史记录管理器未初始化")
                return

            # 创建并显示历史记录对话框
            dialog = HistoryDialog(self.history_manager, self)
            dialog.show()

            logger.info("历史记录对话框已打开")

        except Exception as e:
            logger.error(f"Failed to show history panel: {e}")
            QMessageBox.critical(self, "错误", f"打开历史记录面板失败: {e}")

    @Slot()
    def _clear_history(self) -> None:
        """清空历史记录"""
        try:
            if not self.history_manager:
                QMessageBox.warning(self, "错误", "历史记录管理器未初始化")
                return

            # 确认对话框
            reply = QMessageBox.question(
                self,
                "确认清空",
                "确定要清空所有历史记录吗？此操作不可恢复！",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                # 删除所有记录（通过删除30天前的记录实现）
                from datetime import datetime, timedelta
                cutoff_date = datetime.now() + timedelta(days=1)  # 明天，确保删除所有记录

                deleted_count = self.history_manager.delete_records_before(cutoff_date)

                if deleted_count > 0:
                    QMessageBox.information(
                        self,
                        "成功",
                        f"已清空 {deleted_count} 条历史记录"
                    )
                    logger.info(f"已清空 {deleted_count} 条历史记录")
                else:
                    QMessageBox.information(self, "提示", "没有历史记录需要清空")

        except Exception as e:
            logger.error(f"清除历史记录失败: {e}")
            QMessageBox.critical(self, "错误", f"清空历史记录失败: {e}")

    @Slot()
    def _export_current_transcription(self) -> None:
        """导出当前转录结果"""
        try:
            # 获取当前转录文本
            full_text = self.result_display.get_full_text()

            if not full_text or not full_text.strip():
                QMessageBox.warning(self, "导出失败", "没有可导出的转录内容")
                return

            # 创建临时转录记录
            from pathlib import Path
            model_name = Path(self.config.model_path).name if self.config.model_path else "未知模型"

            # 获取当前音频源信息
            source_info = self.audio_source_selector.get_selected_source()
            audio_source = source_info.source_type if source_info else AudioSourceType.MICROPHONE
            audio_path = source_info.file_path if source_info and source_info.file_path else None

            # 获取时长（从控制面板获取）
            duration = getattr(self.control_panel, '_elapsed_seconds', 0.0)

            # 配置快照
            config_snapshot = json.dumps(asdict(self.config), ensure_ascii=False, indent=2)

            # 创建记录对象
            record = TranscriptionRecord(
                timestamp=datetime.now(),
                audio_source=audio_source,
                audio_path=audio_path,
                duration=duration,
                text=full_text.strip(),
                model_name=model_name,
                config_snapshot=config_snapshot
            )

            # 打开导出对话框
            dialog = ExportDialog([record], self)
            dialog.exec()

        except Exception as e:
            logger.error(f"当前转录结果导出失败: {e}")
            QMessageBox.critical(self, "导出失败", f"导出当前转录时发生错误:\n{e}")

    @Slot()
    def _on_transcription_completed(self) -> None:
        """处理转录完成事件（保存历史记录）"""
        try:
            if not self.history_manager:
                logger.debug("历史记录不可用，跳过保存")
                return

            # 收集转录结果
            full_text = self.result_display.get_full_text()

            if not full_text or not full_text.strip():
                logger.debug("没有要保存的转录文本")
                return

            # 创建历史记录
            source_info = self.audio_source_selector.get_selected_source()
            audio_source = source_info.source_type if source_info else AudioSourceType.MICROPHONE
            audio_path = source_info.file_path if source_info and source_info.file_path else None

            # 计算时长（从控制面板获取）
            duration = getattr(self.control_panel, '_elapsed_seconds', 0.0)

            # 获取模型名称
            model_name = Path(self.config.model_path).name if self.config.model_path else "未知模型"

            # 配置快照
            config_snapshot = json.dumps(asdict(self.config), ensure_ascii=False, indent=2)

            # 创建记录对象
            record = TranscriptionRecord(
                timestamp=datetime.now(),
                audio_source=audio_source,
                audio_path=audio_path,
                duration=duration,
                text=full_text.strip(),
                model_name=model_name,
                config_snapshot=config_snapshot
            )

            # 保存到数据库
            record_id = self.history_manager.add_record(record)

            logger.info(f"转录已保存到历史记录: ID={record_id}")

            # 检查是否需要继续处理文件队列
            if self.is_batch_mode and self.file_queue:
                self._process_next_file()

        except Exception as e:
            logger.error(f"保存转录历史记录失败: {e}")
            # 即使保存失败，也继续处理队列
            if self.is_batch_mode and self.file_queue:
                self._process_next_file()

    def _process_next_file(self) -> None:
        """处理队列中的下一个文件"""
        try:
            # 增加索引
            self.current_file_index += 1

            # 检查是否还有文件
            if self.current_file_index < len(self.file_queue):
                next_file = self.file_queue[self.current_file_index]

                logger.info(f"处理下一个文件: {self.current_file_index + 1}/{len(self.file_queue)}")

                # 清理当前Pipeline
                if self.pipeline:
                    self.pipeline.stop()
                    if self.pipeline_thread:
                        self.pipeline_thread.wait(1000)
                    self.pipeline = None
                    self.pipeline_bridge = None
                    self.pipeline_thread = None

                # 清空结果显示（准备显示新文件的转录）
                self.result_display.clear()

                # 启动下一个文件的转录
                self._start_file_transcription(next_file)

            else:
                # 所有文件转录完成
                total_files = len(self.file_queue)
                logger.info(f"总共 {total_files} 个文件转录成功")

                # 更新UI（在清理状态之前）
                self.control_panel.set_state(TranscriptionState.STOPPED)
                self.audio_source_selector.set_enabled(True)
                self.status_monitor.update_status("✅ 全部完成")
                self.status_bar.showMessage(f"批量转录完成！共处理 {total_files} 个文件")

                # 清理状态
                self._reset_file_queue()

                # 显示完成消息
                QMessageBox.information(
                    self,
                    "批量转录完成",
                    f"成功完成 {total_files} 个文件的转录！"
                )

        except Exception as e:
            logger.error(f"处理下一个文件失败: {e}")
            QMessageBox.critical(
                self,
                "转录错误",
                f"处理下一个文件时发生错误:\n{e}\n\n批量转录已中止。"
            )
            # 清理状态
            self._reset_file_queue()
            self.control_panel.set_state(TranscriptionState.ERROR)
            self.audio_source_selector.set_enabled(True)

    # ========== VAD方案管理相关方法 ==========

    def _load_vad_profiles(self) -> None:
        """加载VAD方案列表到下拉框"""
        if self.vad_profile_selector is None:
            return

        # 清空下拉框
        self.vad_profile_selector.clear()

        # 加载所有VAD方案
        for profile_id, profile in self.config.vad_profiles.items():
            self.vad_profile_selector.addItem(profile.profile_name, profile_id)

        # 选中活跃方案
        active_profile_id = self.config.active_vad_profile_id
        for i in range(self.vad_profile_selector.count()):
            if self.vad_profile_selector.itemData(i) == active_profile_id:
                self.vad_profile_selector.setCurrentIndex(i)
                break

        logger.debug(f"已加载 {len(self.config.vad_profiles)} 个 VAD 配置文件, 正在使用 {active_profile_id} 方案")

    @Slot(int)
    def _on_vad_profile_changed(self, index: int) -> None:
        """处理VAD方案切换

        Args:
            index: 新选中的索引
        """
        if index < 0:
            return

        profile_id = self.vad_profile_selector.itemData(index)
        if profile_id is None or profile_id == self.config.active_vad_profile_id:
            return

        # 如果Pipeline正在运行,提示需要重启
        if self.pipeline is not None and hasattr(self.pipeline, 'is_running') and self.pipeline.is_running:
            QMessageBox.information(
                self,
                "VAD方案切换",
                "VAD方案已切换,将在下次启动转录时生效。\n如需立即生效,请先停止当前转录。"
            )

        # 更新活跃方案ID
        success, error_msg = self.config_bridge.set_active_vad_profile(profile_id)
        if not success:
            QMessageBox.warning(self, "切换失败", f"无法切换VAD方案: {error_msg}")
            # 恢复原选择
            for i in range(self.vad_profile_selector.count()):
                if self.vad_profile_selector.itemData(i) == self.config.active_vad_profile_id:
                    self.vad_profile_selector.setCurrentIndex(i)
                    break
            return

        profile_name = self.vad_profile_selector.currentText()
        logger.info(f"VAD 配置文件切换为: {profile_name} ({profile_id})")
        self.status_bar.showMessage(f"已切换到VAD方案: {profile_name}", 3000)

    @Slot()
    def _open_vad_settings(self) -> None:
        """打开VAD设置对话框(直接跳转到VAD页面)"""
        try:
            dialog = SettingsDialog(self.config, self.config_bridge, self)

            # 跳转到VAD设置页面(索引2: 通用0, 模型1, VAD2)
            if hasattr(dialog, 'nav_list') and dialog.nav_list is not None:
                dialog.nav_list.setCurrentRow(2)

            # 连接设置变更信号
            dialog.settings_changed.connect(self._on_settings_changed_vad)

            dialog.exec()

        except Exception as e:
            logger.error(f"无法打开 VAD 设置对话框: {e}")
            QMessageBox.critical(self, "错误", f"打开VAD设置失败:\n{e}")

    @Slot(object)
    def _on_settings_changed_vad(self, new_config: Config) -> None:
        """处理VAD设置变更

        Args:
            new_config: 新的配置对象
        """
        # 重新加载配置
        self.config = new_config

        # 刷新VAD方案列表
        self._load_vad_profiles()

        logger.info("设置对话框更新 VAD 设置")
