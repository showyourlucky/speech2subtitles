"""
硬件检测和管理模块

提供GPU检测、内存管理、硬件信息收集等功能
支持CUDA GPU检测、ONNX Runtime provider推荐、系统信息统计等

主要组件:
- GPUDetector: GPU检测和管理核心类
- gpu_detector: 全局GPU检测器实例
- GPUInfo: GPU设备信息数据类
- SystemInfo: 系统硬件信息数据类

使用示例:
    from src.hardware import gpu_detector, GPUInfo, SystemInfo

    # 检测CUDA是否可用
    if gpu_detector.detect_cuda():
        print("CUDA is available")

    # 获取系统信息
    system_info = gpu_detector.get_system_info()
    print(system_info)

    # 获取推荐的执行提供器
    provider = gpu_detector.get_recommended_provider()
    print(f"Recommended provider: {provider}")
"""

from .gpu_detector import GPUDetector, gpu_detector
from .models import GPUInfo, SystemInfo

__all__ = ["GPUDetector", "gpu_detector", "GPUInfo", "SystemInfo"]