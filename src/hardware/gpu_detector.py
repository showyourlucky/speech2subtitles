"""
GPU检测和管理模块

负责GPU检测、内存管理、CPU/GPU自适应切换等功能
支持PyTorch和ONNX Runtime的GPU环境检测和配置

主要功能:
1. CUDA GPU检测 (PyTorch + 手动检测)
2. ONNX Runtime GPU Provider检测
3. GPU信息收集 (内存、温度、利用率等)
4. 系统硬件信息统计
5. 执行提供器推荐 (GPU/CPU)
6. GPU内存检查和管理

技术栈:
- PyTorch: 主要的CUDA检测方式
- ONNX Runtime: 推理执行提供器
- nvidia-smi: 备用GPU信息获取
- pynvml: 详细GPU状态监控
- psutil: 系统信息收集
"""

import os
import platform
import psutil
import sys
from typing import Optional, List
import logging

from .models import GPUInfo, SystemInfo

# 设置日志记录器
logger = logging.getLogger(__name__)


class GPUDetector:
    """
    GPU检测和管理核心类

    提供全面的GPU硬件检测、信息收集、性能评估等功能
    支持多种检测方式的容错处理，确保在不同环境下的稳定运行

    主要特性:
    1. 智能缓存机制: 避免重复检测开销
    2. 多重检测策略: PyTorch + 手动检测保证兼容性
    3. 详细信息收集: 内存、温度、利用率等运行时状态
    4. 自动推荐策略: 根据硬件条件推荐最优执行提供器
    """

    def __init__(self):
        """
        初始化GPU检测器

        设置内部缓存变量，避免重复检测的性能开销
        """
        self._system_info: Optional[SystemInfo] = None          # 系统信息缓存
        self._cuda_available: Optional[bool] = None             # CUDA可用性缓存
        self._onnxruntime_gpu_available: Optional[bool] = None  # ONNX Runtime GPU支持缓存

    def detect_cuda(self) -> bool:
        """
        检测CUDA可用性

        使用多重检测策略确保在各种环境下的兼容性:
        1. 优先使用PyTorch的CUDA检测 (最准确)
        2. 如果PyTorch不可用,则使用手动检测方式

        Returns:
            bool: CUDA可用返回True,否则返图False
        """
        # 如果已经检测过CUDA，直接返回缓存结果
        if self._cuda_available is not None:
            return self._cuda_available

        try:
            # 首选方式：使用PyTorch的CUDA检测
            import torch
            self._cuda_available = torch.cuda.is_available()
            logger.info(f"CUDA detection via PyTorch: {self._cuda_available}")
        except ImportError:
            # 备用方式：PyTorch不可用时使用手动检测
            logger.warning("PyTorch not available, falling back to manual CUDA detection")
            self._cuda_available = self._manual_cuda_detection()

        return self._cuda_available

    def _manual_cuda_detection(self) -> bool:
        """
        手动CUDA检测 (不依赖PyTorch)

        当PyTorch不可用时的备用检测方式:
        1. Windows: 使用nvidia-smi命令检测GPU
        2. 检查CUDA环境变量 (CUDA_PATH, CUDA_HOME)

        Returns:
            bool: 检测到CUDA返回True
        """
        try:
            # 方法1: 检查NVIDIA驱动程序 (仅Windows)
            if platform.system() == "Windows":
                import subprocess
                try:
                    # 尝试运行nvidia-smi命令查询GPU名称
                    result = subprocess.run(
                        ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    # 如果命令成功执行且有输出，说明NVIDIA GPU存在
                    return result.returncode == 0 and result.stdout.strip()
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    # nvidia-smi命令不存在或超时
                    pass

            # 方法2: 检查CUDA环境变量
            cuda_path = os.environ.get('CUDA_PATH') or os.environ.get('CUDA_HOME')
            if cuda_path and os.path.exists(cuda_path):
                return True

            # 都检查不到CUDA环境
            return False

        except Exception as e:
            logger.error(f"Error in manual CUDA detection: {e}")
            return False

    def detect_onnxruntime_gpu(self) -> bool:
        """
        检测ONNX Runtime GPU提供器可用性

        检查ONNX Runtime是否支持CUDAExecutionProvider
        这对于判断是否可以使用GPU进行推理至关重要

        Returns:
            bool: ONNX Runtime GPU提供器可用返回True
        """
        if self._onnxruntime_gpu_available is not None:
            return self._onnxruntime_gpu_available

        try:
            import onnxruntime as ort
            providers = ort.get_available_providers()
            self._onnxruntime_gpu_available = 'CUDAExecutionProvider' in providers
            logger.info(f"ONNX Runtime GPU provider available: {self._onnxruntime_gpu_available}")
            return self._onnxruntime_gpu_available
        except ImportError:
            logger.warning("ONNX Runtime not available")
            self._onnxruntime_gpu_available = False
            return False

    def get_gpu_info(self) -> List[GPUInfo]:
        """
        获取详细的GPU信息

        收集系统中所有GPU设备的详细信息:
        - 基本信息: 设备ID、名称、可用性
        - 内存信息: 总量、已用、可用
        - 性能信息: 计算能力、温度、利用率
        - 驱动信息: 驱动版本、CUDA版本

        Returns:
            List[GPUInfo]: GPU信息对象列表
        """
        gpus = []

        if not self.detect_cuda():
            logger.info("No CUDA GPUs detected")
            return gpus

        try:
            import torch
            gpu_count = torch.cuda.device_count()
            logger.info(f"Detected {gpu_count} CUDA GPU(s)")

            for i in range(gpu_count):
                try:
                    gpu_info = self._get_torch_gpu_info(i)
                    gpus.append(gpu_info)
                except Exception as e:
                    logger.error(f"Error getting info for GPU {i}: {e}")

        except ImportError:
            logger.warning("PyTorch not available, using fallback GPU detection")
            gpus = self._get_fallback_gpu_info()

        return gpus

    def _get_torch_gpu_info(self, device_id: int) -> GPUInfo:
        """
        使用PyTorch获取GPU信息

        PyTorch提供了最准确和完整的GPU信息获取方式
        包括设备属性、内存状态、计算能力等

        Args:
            device_id: GPU设备ID

        Returns:
            GPUInfo: GPU设备信息对象
        """
        import torch

        device = torch.device(f'cuda:{device_id}')
        props = torch.cuda.get_device_properties(device)

        # Get memory information
        total_memory = props.total_memory // (1024 * 1024)  # Convert to MB
        allocated_memory = torch.cuda.memory_allocated(device) // (1024 * 1024)
        available_memory = total_memory - allocated_memory

        # Get additional info
        capability = f"{props.major}.{props.minor}"

        gpu_info = GPUInfo(
            id=device_id,
            name=props.name,
            is_available=True,
            total_memory=total_memory,
            available_memory=available_memory,
            used_memory=allocated_memory,
            compute_capability=capability
        )

        # Try to get temperature and utilization via nvidia-ml-py if available
        try:
            self._add_nvidia_ml_info(gpu_info, device_id)
        except Exception as e:
            logger.debug(f"Could not get additional GPU info: {e}")

        return gpu_info

    def _get_fallback_gpu_info(self) -> List[GPUInfo]:
        """
        备用GPU检测方式 (不依赖PyTorch)

        当PyTorch不可用时使用nvidia-smi命令获取GPU信息
        功能有限但可以提供基本的GPU设备信息

        Returns:
            List[GPUInfo]: GPU信息列表
        """
        gpus = []

        try:
            import subprocess
            if platform.system() == "Windows":
                # Try nvidia-smi
                result = subprocess.run([
                    "nvidia-smi",
                    "--query-gpu=index,name,memory.total,memory.used,memory.free",
                    "--format=csv,noheader,nounits"
                ], capture_output=True, text=True, timeout=10)

                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            parts = [p.strip() for p in line.split(',')]
                            if len(parts) >= 5:
                                gpu_info = GPUInfo(
                                    id=int(parts[0]),
                                    name=parts[1],
                                    is_available=True,
                                    total_memory=int(parts[2]),
                                    used_memory=int(parts[3]),
                                    available_memory=int(parts[4])
                                )
                                gpus.append(gpu_info)

        except Exception as e:
            logger.error(f"Error in fallback GPU detection: {e}")

        return gpus

    def _add_nvidia_ml_info(self, gpu_info: GPUInfo, device_id: int):
        """
        使用nvidia-ml-py添加额外的GPU信息

        通过pynvml库获取更详细的GPU运行时状态:
        - GPU温度
        - GPU利用率
        - 驱动程序版本

        Args:
            gpu_info: 要更新的GPU信息对象
            device_id: GPU设备ID
        """
        try:
            import pynvml
            pynvml.nvmlInit()

            handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)

            # Get temperature
            try:
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                gpu_info.temperature = temp
            except:
                pass

            # Get utilization
            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_info.utilization = util.gpu
            except:
                pass

            # Get driver version
            try:
                driver_version = pynvml.nvmlSystemGetDriverVersion()
                gpu_info.driver_version = driver_version.decode('utf-8')
            except:
                pass

        except ImportError:
            # pynvml not available
            pass
        except Exception as e:
            logger.debug(f"Error getting nvidia-ml info: {e}")

    def get_system_info(self) -> SystemInfo:
        """
        获取综合系统信息

        收集完整的系统硬件信息包括:
        - CPU信息: 核心数、型号
        - 内存信息: 总量、可用量
        - GPU信息: 所有GPU设备的详细信息
        - 平台信息: 操作系统、Python版本

        Returns:
            SystemInfo: 系统信息对象
        """
        if self._system_info is not None:
            return self._system_info

        # Get CPU information
        cpu_count = psutil.cpu_count()
        try:
            cpu_name = platform.processor() or "Unknown"
        except:
            cpu_name = "Unknown"

        # Get memory information
        memory = psutil.virtual_memory()
        total_ram_mb = memory.total // (1024 * 1024)
        available_ram_mb = memory.available // (1024 * 1024)

        # Get GPU information
        gpus = self.get_gpu_info()

        # Get platform information
        platform_info = f"{platform.system()} {platform.release()}"
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        self._system_info = SystemInfo(
            cpu_count=cpu_count,
            cpu_name=cpu_name,
            total_ram_mb=total_ram_mb,
            available_ram_mb=available_ram_mb,
            gpus=gpus,
            platform=platform_info,
            python_version=python_version
        )

        return self._system_info

    def check_memory(self, required_mb: int, device_id: Optional[int] = None) -> bool:
        """
        检查指定GPU是否有足够内存

        用于在模型加载前预检查内存条件,避免OOM错误

        Args:
            required_mb: 所需内存大小 (MB)
            device_id: GPU设备ID,为None时检查最佳可用GPU

        Returns:
            bool: 内存足够返回True
        """
        system_info = self.get_system_info()

        if device_id is not None:
            # Check specific GPU
            gpu = next((g for g in system_info.gpus if g.id == device_id), None)
            if gpu is None:
                return False
            return gpu.has_sufficient_memory(required_mb)
        else:
            # Check best available GPU
            best_gpu = system_info.get_best_gpu(required_mb)
            return best_gpu is not None

    def get_recommended_provider(self, prefer_gpu: bool = True) -> str:
        """
        获取推荐的ONNX Runtime执行提供器

        根据系统硬件条件和用户偏好推荐最优的执行提供器:
        1. 如果偏好GPU且有可用GPU -> CUDAExecutionProvider
        2. 否则 -> CPUExecutionProvider

        Args:
            prefer_gpu: 是否偏好GPU (如果可用)

        Returns:
            str: 推荐的提供器名称
        """
        if prefer_gpu and self.detect_cuda() and self.detect_onnxruntime_gpu():
            system_info = self.get_system_info()
            best_gpu = system_info.get_best_gpu()
            if best_gpu is not None:
                logger.info(f"Recommending GPU provider with {best_gpu.name}")
                return "CUDAExecutionProvider"

        logger.info("Recommending CPU provider")
        return "CPUExecutionProvider"

    def get_provider_options(self, provider: str, device_id: Optional[int] = None) -> dict:
        """
        获取提供器特定的配置选项

        为不同的执行提供器生成优化的配置参数
        GPU提供器包含内存限制、设备ID、算法搜索等配置

        Args:
            provider: 提供器名称
            device_id: GPU设备ID (仅适用于GPU提供器)

        Returns:
            dict: 提供器配置选项
        """
        if provider == "CUDAExecutionProvider":
            options = {
                'device_id': device_id or 0,
                'arena_extend_strategy': 'kSameAsRequested',
                'gpu_mem_limit': 2 * 1024 * 1024 * 1024,  # 2GB limit
                'cudnn_conv_algo_search': 'EXHAUSTIVE',
                'do_copy_in_default_stream': True,
            }
            return options
        else:
            return {}

    def print_system_info(self):
        """
        打印综合系统信息

        用于调试和环境检查,显示完整的系统硬件信息
        包括GPU支持、ONNX Runtime配置、推荐提供器等
        """
        system_info = self.get_system_info()
        print(system_info)

        # Additional ONNX Runtime info
        print(f"\nONNX Runtime GPU Support: {self.detect_onnxruntime_gpu()}")
        print(f"Recommended Provider: {self.get_recommended_provider()}")


# 全局GPU检测器实例，方便全局访问
# 避免重复创建对象，提高性能并保持状态一致性
gpu_detector = GPUDetector()