"""
硬件信息模型定义模块

定义用于存储GPU和系统硬件信息的数据结构
主要包含GPUInfo和SystemInfo两个核心数据类
"""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class GPUInfo:
    """
    GPU设备信息数据类

    存储单个GPU设备的完整信息，包括基本信息、内存状态、计算能力等
    用于GPU检测、内存管理、性能评估等场景
    """

    # === 基本GPU设备信息 ===
    id: int                           # GPU设备ID (0, 1, 2, ...)
    name: str                        # GPU设备名称 (如 "NVIDIA GeForce RTX 3080")
    is_available: bool               # GPU是否可用于计算任务

    # === 内存信息 ===
    total_memory: int                # GPU总内存容量 (MB)
    available_memory: int            # GPU可用内存 (MB)
    used_memory: int                 # GPU已使用内存 (MB)

    # === 能力信息 (可选) ===
    compute_capability: Optional[str] = None  # CUDA计算能力版本 (如 "8.6")
    driver_version: Optional[str] = None      # 驱动程序版本
    cuda_version: Optional[str] = None        # CUDA运行时版本

    # === 运行时状态信息 (可选) ===
    temperature: Optional[int] = None         # GPU温度 (摄氏度)
    utilization: Optional[int] = None         # GPU利用率百分比 (0-100)

    def __str__(self) -> str:
        """
        GPU信息的字符串表示

        Returns:
            str: 格式化的GPU信息字符串，包含设备名、状态、内存使用等
        """
        # 生成状态标识和内存信息
        status = "Available" if self.is_available else "Unavailable"
        memory_info = f"{self.used_memory}/{self.total_memory}MB"

        # 构建基本信息
        result = f"GPU {self.id}: {self.name} [{status}]"
        result += f"\n  Memory: {memory_info}"

        # 添加可选的详细信息
        if self.compute_capability:
            result += f"\n  Compute Capability: {self.compute_capability}"
        if self.driver_version:
            result += f"\n  Driver Version: {self.driver_version}"
        if self.temperature is not None:
            result += f"\n  Temperature: {self.temperature}°C"
        if self.utilization is not None:
            result += f"\n  Utilization: {self.utilization}%"

        return result

    @property
    def memory_usage_percent(self) -> float:
        """
        计算GPU内存使用率

        Returns:
            float: 内存使用率百分比 (0.0-100.0)
        """
        if self.total_memory == 0:
            return 0.0
        return (self.used_memory / self.total_memory) * 100

    def has_sufficient_memory(self, required_mb: int) -> bool:
        """
        检查GPU是否有足够的可用内存

        Args:
            required_mb: 所需内存容量 (MB)

        Returns:
            bool: 如果可用内存足够则返回True
        """
        return self.available_memory >= required_mb

    def is_suitable_for_inference(self, min_memory_mb: int = 1024) -> bool:
        """
        检查GPU是否适合进行推理任务

        Args:
            min_memory_mb: 最小内存要求 (MB)，默认1GB

        Returns:
            bool: 如果GPU适合推理任务则返回True

        评估标准:
        1. GPU必须可用
        2. 可用内存必须满足最小要求
        3. 内存使用率不能超过90% (避免OOM)
        """
        return (
            self.is_available and
            self.has_sufficient_memory(min_memory_mb) and
            self.memory_usage_percent < 90  # 不使用内存使用率>90%的GPU
        )


@dataclass
class SystemInfo:
    """
    系统硬件信息数据类

    存储完整的系统硬件信息，包括CPU、内存、GPU、平台等
    用于系统环境检测、硬件适配、性能优化等场景
    """

    # === CPU信息 ===
    cpu_count: int                   # CPU核心数量
    cpu_name: Optional[str] = None   # CPU型号名称

    # === 内存信息 ===
    total_ram_mb: int = 0           # 系统总内存 (MB)
    available_ram_mb: int = 0       # 系统可用内存 (MB)

    # === GPU信息 ===
    gpus: List[GPUInfo] = field(default_factory=list)  # 系统中的GPU设备列表

    # === 平台信息 ===
    platform: Optional[str] = None  # 操作系统平台信息
    python_version: Optional[str] = None  # Python版本信息

    def __post_init__(self):
        """
        初始化后处理

        执行必要的数据验证和初始化
        """
        # 使用field(default_factory=list)后，gpus已经默认为空列表，无需手动初始化
        pass

    def get_best_gpu(self, min_memory_mb: int = 1024) -> Optional[GPUInfo]:
        """
        获取最适合推理的GPU设备

        Args:
            min_memory_mb: 最小内存要求 (MB)，默认1GB

        Returns:
            Optional[GPUInfo]: 最佳GPU设备，如果没有合适设备则返回None

        选择策略:
        1. 过滤出满足推理要求的GPU
        2. 按可用内存大小排序，选择内存最多的
        """
        # 筛选符合推理要求的GPU
        suitable_gpus = [
            gpu for gpu in self.gpus
            if gpu.is_suitable_for_inference(min_memory_mb)
        ]

        if not suitable_gpus:
            return None

        # 按可用内存降序排列，选择内存最大的GPU
        return max(suitable_gpus, key=lambda gpu: gpu.available_memory)

    def has_cuda_gpu(self) -> bool:
        """
        检查系统是否有CUDA兼容的GPU

        Returns:
            bool: 如果有可用的CUDA GPU则返回True
        """
        return any(gpu.is_available for gpu in self.gpus)

    def get_total_gpu_memory(self) -> int:
        """
        获取所有GPU的总内存容量

        Returns:
            int: 所有GPU的总内存 (MB)
        """
        return sum(gpu.total_memory for gpu in self.gpus)

    def __str__(self) -> str:
        """
        系统信息的字符串表示

        Returns:
            str: 格式化的系统信息字符串，包含平台、CPU、内存、GPU等详细信息
        """
        result = f"System Information:\n"
        result += f"  Platform: {self.platform}\n"
        result += f"  Python: {self.python_version}\n"
        result += f"  CPU Cores: {self.cpu_count}\n"
        if self.cpu_name:
            result += f"  CPU: {self.cpu_name}\n"
        result += f"  RAM: {self.available_ram_mb}/{self.total_ram_mb}MB\n"
        result += f"  GPUs: {len(self.gpus)}\n"

        # 添加每个GPU的详细信息（缩进显示）
        for gpu in self.gpus:
            gpu_lines = str(gpu).split('\n')
            for line in gpu_lines:
                result += f"    {line}\n"

        return result.rstrip()