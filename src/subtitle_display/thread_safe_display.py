"""
线程安全的字幕显示组件

使用独立的GUI线程来彻底解决tkinter的线程安全问题。
"""

import threading
import queue
import time
import logging
from typing import Optional, Callable
from dataclasses import dataclass

try:
    import tkinter as tk
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False
    tk = None

from ..utils.error_handler import ComponentInitializationError
from ..config.models import SubtitleDisplayConfig


@dataclass
class SubtitleMessage:
    """字幕显示消息"""
    text: str
    confidence: float
    action: str  # 'show', 'clear', 'start', 'stop', 'update_config'


class ThreadSafeSubtitleDisplay:
    """
    线程安全的字幕显示组件

    通过独立的GUI线程和消息队列来确保线程安全，
    彻底解决tkinter的线程安全问题。
    """

    def __init__(self, config: SubtitleDisplayConfig):
        """
        初始化线程安全的字幕显示组件

        Args:
            config: 字幕显示配置
        """
        self.logger = logging.getLogger(__name__)
        self.config = config

        # 验证tkinter可用性
        if not TKINTER_AVAILABLE:
            raise ComponentInitializationError("tkinter不可用，无法启用字幕显示功能")

        # 验证配置
        self.config.validate()

        # GUI线程相关
        self._gui_thread: Optional[threading.Thread] = None
        self._message_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._started_event = threading.Event()

        # GUI组件引用（只在GUI线程中访问）
        self._root = None
        self._label = None
        self._clear_timer = None

        # 状态标志
        self._is_running = False
        self._gui_thread_id = None

        # 启动GUI线程
        self._start_gui_thread()

    def _start_gui_thread(self) -> None:
        """启动独立的GUI线程"""
        self._gui_thread = threading.Thread(
            target=self._gui_thread_main,
            name="SubtitleDisplayGUI",
            daemon=True
        )
        self._gui_thread.start()

        # 等待GUI线程初始化完成
        if not self._started_event.wait(timeout=5.0):
            raise ComponentInitializationError("GUI线程启动超时")

        self.logger.info("字幕显示GUI线程启动成功")

    def _gui_thread_main(self) -> None:
        """GUI线程主函数"""
        try:
            # 记录GUI线程ID
            self._gui_thread_id = threading.get_ident()

            # 创建tkinter应用
            self._create_gui()

            # 通知主线程GUI已准备就绪
            self._started_event.set()

            # 进入消息循环
            self._message_loop()

        except Exception as e:
            self.logger.error(f"GUI线程异常: {e}")
            self._started_event.set()  # 即使失败也要设置事件，避免主线程一直等待

    def _create_gui(self) -> None:
        """创建GUI组件"""
        try:
            # 创建主窗口
            self._root = tk.Tk()
            self._setup_window()

            # 创建字幕标签
            self._create_label()

            # 设置窗口位置
            self._position_window()

            # 初始隐藏窗口
            self._root.withdraw()

            self.logger.info("GUI组件创建完成")

        except Exception as e:
            self.logger.error(f"GUI组件创建失败: {e}")
            raise ComponentInitializationError(f"GUI组件创建失败: {e}")

    def _setup_window(self) -> None:
        """设置窗口属性"""
        if not self._root:
            return

        # 设置窗口标题
        self._root.title("实时字幕")

        # 无边框窗口
        self._root.overrideredirect(True)

        # 置顶显示
        self._root.attributes("-topmost", True)

        # 设置透明度
        self._root.attributes("-alpha", self.config.opacity)

        # 设置背景色
        self._root.configure(bg=self.config.background_color)

        # 使窗口可拖拽
        self._make_draggable()

    def _create_label(self) -> None:
        """创建字幕标签"""
        if not self._root:
            return

        # 创建标签
        self._label = tk.Label(
            self._root,
            text="",
            font=(self.config.font_family, self.config.font_size),
            fg=self.config.text_color,
            bg=self.config.background_color,
            wraplength=750,  # 文本换行宽度
            justify="center"
        )

        # 布局标签
        self._label.pack(expand=True, fill="both", padx=10, pady=5)

    def _make_draggable(self) -> None:
        """使窗口可拖拽移动"""
        if not self._root:
            return

        def on_click(event):
            """鼠标点击事件"""
            self._start_x = event.x
            self._start_y = event.y

        def on_drag(event):
            """鼠标拖拽事件"""
            if hasattr(self, '_start_x') and hasattr(self, '_start_y'):
                x = event.x_root - self._start_x
                y = event.y_root - self._start_y
                self._root.geometry(f"+{x}+{y}")

        def on_release(event):
            """鼠标释放事件"""
            if hasattr(self, '_start_x'):
                delattr(self, '_start_x')
            if hasattr(self, '_start_y'):
                delattr(self, '_start_y')

        # 绑定事件
        self._root.bind("<Button-1>", on_click)
        self._root.bind("<B1-Motion>", on_drag)
        self._root.bind("<ButtonRelease-1>", on_release)

    def _position_window(self) -> None:
        """根据配置设置窗口位置"""
        if not self._root:
            return

        try:
            # 获取屏幕尺寸
            screen_width = self._root.winfo_screenwidth()
            screen_height = self._root.winfo_screenheight()

            # 获取窗口尺寸（初始设置）
            window_width = 800
            window_height = 100

            # 根据位置配置计算窗口位置
            position = self.config.position.lower()

            if position == "top":
                # 顶部居中
                x = (screen_width - window_width) // 2
                y = 50  # 距离顶部50像素

            elif position == "center":
                # 屏幕居中
                x = (screen_width - window_width) // 2
                y = (screen_height - window_height) // 2

            elif position == "bottom":
                # 底部居中
                x = (screen_width - window_width) // 2
                y = screen_height - window_height - 50  # 距离底部50像素

            else:
                # 默认底部位置
                x = (screen_width - window_width) // 2
                y = screen_height - window_height - 50
                self.logger.warning(f"未知的位置配置: {position}，使用默认底部位置")

            # 设置窗口位置
            self._root.geometry(f"{window_width}x{window_height}+{x}+{y}")

            self.logger.info(f"字幕窗口位置设置: {position} ({x}, {y})")

        except Exception as e:
            self.logger.error(f"设置窗口位置失败: {e}")
            # 使用默认位置
            self._root.geometry("800x100+100+100")

    def _message_loop(self) -> None:
        """消息循环"""
        # 启动tkinter主循环，并集成消息处理
        self._root.after(100, self._process_pending_messages)  # 每100ms检查一次消息队列

        # 启动tkinter主循环（这是关键！）
        try:
            self._root.mainloop()
        except Exception as e:
            self.logger.error(f"tkinter主循环异常: {e}")
        finally:
            # 清理GUI组件
            self._cleanup_gui()

    def _process_pending_messages(self) -> None:
        """处理待处理的消息（在主循环中定期调用）"""
        if self._stop_event.is_set():
            if self._root:
                self._root.quit()  # 退出主循环
            return

        # 处理所有待处理的消息
        while True:
            try:
                # 非阻塞获取消息
                message = self._message_queue.get_nowait()
                self._process_message(message)
            except queue.Empty:
                # 没有更多消息，继续处理tkinter事件
                break
            except Exception as e:
                self.logger.error(f"处理消息时出错: {e}")

        # 继续下一次检查
        if self._root and not self._stop_event.is_set():
            self._root.after(50, self._process_pending_messages)  # 每50ms检查一次

    def _process_message(self, message: SubtitleMessage) -> None:
        """处理字幕消息"""
        try:
            if message.action == "show":
                self._handle_show_message(message)
            elif message.action == "clear":
                self._handle_clear_message()
            elif message.action == "start":
                self._handle_start_message()
            elif message.action == "stop":
                self._handle_stop_message()
            elif message.action == "update_config":
                self._handle_update_config(message)
            else:
                self.logger.warning(f"未知消息类型: {message.action}")

        except Exception as e:
            self.logger.error(f"处理消息失败: {e}")

    def _handle_show_message(self, message: SubtitleMessage) -> None:
        """处理显示字幕消息"""
        if not self._label or not self._root:
            return

        # 清除之前的定时器
        if self._clear_timer:
            self._root.after_cancel(self._clear_timer)
            self._clear_timer = None

        # 过滤和清理文本
        clean_text = self._clean_text(message.text)
        if not clean_text:
            self._clear_label_text()
            return

        # 格式化显示文本
        display_text = self._format_display_text(clean_text, message.confidence)

        # 更新标签文本
        self._update_label_text(display_text)

        # 设置自动清除定时器
        self._clear_timer = self._root.after(
            int(self.config.max_display_time * 1000),
            self._clear_label_text
        )

    def _handle_clear_message(self) -> None:
        """处理清除字幕消息"""
        if self._clear_timer:
            self._root.after_cancel(self._clear_timer)
            self._clear_timer = None
        self._clear_label_text()

    def _handle_start_message(self) -> None:
        """处理启动消息"""
        if self._root:
            self._root.deiconify()  # 显示窗口
            self._root.lift()       # 提升到前台
            self._is_running = True
            self.logger.info("字幕显示已启动")

    def _handle_stop_message(self) -> None:
        """处理停止消息"""
        if self._root:
            self._root.withdraw()  # 隐藏窗口
        self._is_running = False
        self.logger.info("字幕显示已停止")

    def _handle_update_config(self, message: SubtitleMessage) -> None:
        """处理配置更新消息"""
        # 这里可以实现配置的动态更新
        pass

    def _clean_text(self, text: str) -> str:
        """清理和过滤文本内容"""
        if not text:
            return ""

        # 移除多余空白字符
        cleaned = " ".join(text.split())

        # 限制文本长度
        max_length = 200
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length] + "..."

        return cleaned

    def _format_display_text(self, text: str, confidence: float) -> str:
        """格式化显示文本"""
        if confidence < 0.7:
            return f"{text} (置信度: {confidence:.2f})"
        return text

    def _update_label_text(self, text: str) -> None:
        """更新标签文本"""
        if self._label:
            self._label.config(text=text)
            # 自动调整窗口大小（延迟执行，避免阻塞）
            self._root.after_idle(self._adjust_window_size)

    def _adjust_window_size(self) -> None:
        """调整窗口大小以适应文本内容"""
        try:
            if self._root and self._label:
                self._root.update_idletasks()  # 更新布局
                # 获取标签所需大小
                self._label.update_idletasks()
                req_width = self._label.winfo_reqwidth() + 20  # 加一些边距
                req_height = self._label.winfo_reqheight() + 10

                # 限制最大尺寸
                max_width = 800
                max_height = 200

                width = min(req_width, max_width)
                height = min(req_height, max_height)

                # 设置窗口大小
                self._root.geometry(f"{width}x{height}")
        except Exception as e:
            self.logger.debug(f"调整窗口大小失败: {e}")

    def _clear_label_text(self) -> None:
        """清除标签文本"""
        if self._label:
            self._label.config(text="")

    def _cleanup_gui(self) -> None:
        """清理GUI组件"""
        try:
            if self._root:
                self._root.destroy()
                self._root = None
            self._label = None
            self.logger.info("GUI组件已清理")
        except Exception as e:
            self.logger.error(f"GUI组件清理失败: {e}")

    # 公共接口方法

    def start(self) -> None:
        """启动字幕显示"""
        if not self._is_running:
            self._send_message("start", "", 1.0)

    def stop(self) -> None:
        """停止字幕显示"""
        if self._is_running:
            self._send_message("stop", "", 1.0)

    def show_subtitle(self, text: str, confidence: float = 1.0) -> None:
        """
        显示字幕文本（线程安全）

        Args:
            text: 要显示的字幕文本
            confidence: 转录置信度 (0.0-1.0)
        """
        if self._is_running:
            self._send_message("show", text, confidence)

    def clear_subtitle(self) -> None:
        """清除当前显示的字幕（线程安全）"""
        if self._is_running:
            self._send_message("clear", "", 1.0)

    def _send_message(self, action: str, text: str, confidence: float) -> None:
        """发送消息到GUI线程"""
        try:
            message = SubtitleMessage(
                action=action,
                text=text,
                confidence=confidence
            )
            self._message_queue.put(message, timeout=1.0)
        except Exception as e:
            self.logger.error(f"发送消息失败: {e}")

    @property
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._is_running

    def __del__(self):
        """析构函数"""
        try:
            if hasattr(self, '_stop_event'):
                self._stop_event.set()
            if hasattr(self, '_gui_thread') and self._gui_thread and self._gui_thread.is_alive():
                self._gui_thread.join(timeout=2.0)
        except:
            pass