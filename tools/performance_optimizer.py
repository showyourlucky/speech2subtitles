#!/usr/bin/env python3
"""
性能优化器

自动分析系统性能瓶颈并提供优化建议和自动优化功能
"""

import time
import psutil
import logging
import json
import sys
import os
from typing import Dict, List, Any, Optional
from pathlib import Path
import subprocess

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import setup_logging, get_logger, LogConfig, LogLevel

# 配置日志
setup_logging(LogConfig(level=LogLevel.INFO))
logger = get_logger('performance_optimizer')

class PerformanceOptimizer:
    """性能优化器类"""

    def __init__(self):
        self.optimization_results = {}
        self.recommendations = []

    def analyze_system_performance(self) -> Dict[str, Any]:
        """分析系统性能"""
        logger.info("开始系统性能分析...")

        analysis = {
            'cpu_analysis': self._analyze_cpu(),
            'memory_analysis': self._analyze_memory(),
            'gpu_analysis': self._analyze_gpu(),
            'disk_analysis': self._analyze_disk(),
            'process_analysis': self._analyze_processes(),
            'recommendations': []
        }

        # 生成优化建议
        analysis['recommendations'] = self._generate_recommendations(analysis)

        return analysis

    def _analyze_cpu(self) -> Dict[str, Any]:
        """分析CPU性能"""
        logger.info("分析CPU性能...")

        # CPU使用率监控
        cpu_percentages = []
        for _ in range(10):
            cpu_percentages.append(psutil.cpu_percent(interval=0.1))

        cpu_info = {
            'count': psutil.cpu_count(),
            'count_logical': psutil.cpu_count(logical=True),
            'current_usage': cpu_percentages[-1],
            'avg_usage': sum(cpu_percentages) / len(cpu_percentages),
            'max_usage': max(cpu_percentages),
            'min_usage': min(cpu_percentages),
            'freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
            'load_avg': os.getloadavg() if hasattr(os, 'getloadavg') else None
        }

        # CPU性能评估
        cpu_info['performance_level'] = self._evaluate_cpu_performance(cpu_info)

        return cpu_info

    def _analyze_memory(self) -> Dict[str, Any]:
        """分析内存性能"""
        logger.info("分析内存性能...")

        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()

        memory_info = {
            'total_gb': round(memory.total / (1024**3), 2),
            'available_gb': round(memory.available / (1024**3), 2),
            'used_gb': round(memory.used / (1024**3), 2),
            'percent': memory.percent,
            'swap_total_gb': round(swap.total / (1024**3), 2),
            'swap_used_gb': round(swap.used / (1024**3), 2),
            'swap_percent': swap.percent
        }

        # 内存性能评估
        memory_info['performance_level'] = self._evaluate_memory_performance(memory_info)

        return memory_info

    def _analyze_gpu(self) -> Dict[str, Any]:
        """分析GPU性能"""
        logger.info("分析GPU性能...")

        gpu_info = {
            'cuda_available': False,
            'gpu_count': 0,
            'gpus': [],
            'performance_level': 'unknown'
        }

        try:
            # 检查CUDA
            import torch
            gpu_info['cuda_available'] = torch.cuda.is_available()

            if gpu_info['cuda_available']:
                gpu_info['gpu_count'] = torch.cuda.device_count()

                for i in range(gpu_info['gpu_count']):
                    props = torch.cuda.get_device_properties(i)
                    memory_info = torch.cuda.mem_get_info(i)

                    gpu_data = {
                        'id': i,
                        'name': props.name,
                        'total_memory_gb': round(props.total_memory / (1024**3), 2),
                        'memory_free_gb': round(memory_info[0] / (1024**3), 2),
                        'memory_used_gb': round((props.total_memory - memory_info[0]) / (1024**3), 2),
                        'memory_percent': ((props.total_memory - memory_info[0]) / props.total_memory) * 100,
                        'compute_capability': f"{props.major}.{props.minor}",
                        'multiprocessor_count': props.multi_processor_count
                    }

                    gpu_info['gpus'].append(gpu_data)

                # GPU性能评估
                gpu_info['performance_level'] = self._evaluate_gpu_performance(gpu_info)

        except ImportError:
            logger.warning("PyTorch未安装，无法检测GPU")
        except Exception as e:
            logger.warning(f"GPU分析失败: {e}")

        return gpu_info

    def _analyze_disk(self) -> Dict[str, Any]:
        """分析磁盘性能"""
        logger.info("分析磁盘性能...")

        # 获取项目目录所在磁盘
        project_disk = project_root.anchor if project_root.is_absolute() else "/"

        try:
            disk_usage = psutil.disk_usage(project_disk)
            disk_io = psutil.disk_io_counters()

            disk_info = {
                'total_gb': round(disk_usage.total / (1024**3), 2),
                'free_gb': round(disk_usage.free / (1024**3), 2),
                'used_gb': round(disk_usage.used / (1024**3), 2),
                'percent': (disk_usage.used / disk_usage.total) * 100,
                'io_stats': {
                    'read_bytes': disk_io.read_bytes if disk_io else 0,
                    'write_bytes': disk_io.write_bytes if disk_io else 0,
                    'read_count': disk_io.read_count if disk_io else 0,
                    'write_count': disk_io.write_count if disk_io else 0
                } if disk_io else {}
            }

            # 磁盘性能评估
            disk_info['performance_level'] = self._evaluate_disk_performance(disk_info)

        except Exception as e:
            logger.warning(f"磁盘分析失败: {e}")
            disk_info = {'error': str(e)}

        return disk_info

    def _analyze_processes(self) -> Dict[str, Any]:
        """分析进程性能"""
        logger.info("分析进程性能...")

        current_process = psutil.Process()

        # 获取Python进程信息
        python_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']):
            try:
                if 'python' in proc.info['name'].lower():
                    python_processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'memory_mb': round(proc.info['memory_info'].rss / (1024**2), 2),
                        'cpu_percent': proc.info['cpu_percent']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        process_info = {
            'current_process': {
                'pid': current_process.pid,
                'memory_mb': round(current_process.memory_info().rss / (1024**2), 2),
                'cpu_percent': current_process.cpu_percent(),
                'num_threads': current_process.num_threads(),
                'connections': len(current_process.connections())
            },
            'python_processes': python_processes,
            'total_processes': len(list(psutil.process_iter()))
        }

        return process_info

    def _evaluate_cpu_performance(self, cpu_info: Dict[str, Any]) -> str:
        """评估CPU性能级别"""
        avg_usage = cpu_info['avg_usage']
        cpu_count = cpu_info['count']

        if avg_usage > 80:
            return 'poor'
        elif avg_usage > 60:
            return 'fair'
        elif avg_usage > 40:
            return 'good'
        else:
            return 'excellent'

    def _evaluate_memory_performance(self, memory_info: Dict[str, Any]) -> str:
        """评估内存性能级别"""
        memory_percent = memory_info['percent']
        total_gb = memory_info['total_gb']

        if memory_percent > 90:
            return 'critical'
        elif memory_percent > 80:
            return 'poor'
        elif memory_percent > 60:
            return 'fair'
        elif total_gb < 8:
            return 'limited'
        else:
            return 'excellent'

    def _evaluate_gpu_performance(self, gpu_info: Dict[str, Any]) -> str:
        """评估GPU性能级别"""
        if not gpu_info['cuda_available']:
            return 'no_gpu'

        if gpu_info['gpu_count'] == 0:
            return 'no_gpu'

        # 检查GPU内存使用情况
        gpu_data = gpu_info['gpus'][0]  # 使用第一个GPU
        memory_percent = gpu_data['memory_percent']
        total_memory = gpu_data['total_memory_gb']

        if memory_percent > 90:
            return 'overloaded'
        elif memory_percent > 70:
            return 'high_usage'
        elif total_memory < 4:
            return 'limited'
        else:
            return 'excellent'

    def _evaluate_disk_performance(self, disk_info: Dict[str, Any]) -> str:
        """评估磁盘性能级别"""
        if 'error' in disk_info:
            return 'unknown'

        percent_used = disk_info['percent']
        free_gb = disk_info['free_gb']

        if percent_used > 95:
            return 'critical'
        elif percent_used > 85:
            return 'poor'
        elif free_gb < 2:
            return 'limited'
        else:
            return 'good'

    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成优化建议"""
        logger.info("生成优化建议...")

        recommendations = []

        # CPU优化建议
        cpu_analysis = analysis['cpu_analysis']
        if cpu_analysis['performance_level'] in ['poor', 'fair']:
            recommendations.append({
                'category': 'cpu',
                'priority': 'high',
                'title': 'CPU使用率过高',
                'description': f"CPU平均使用率: {cpu_analysis['avg_usage']:.1f}%",
                'suggestions': [
                    "考虑使用GPU加速以减轻CPU负担",
                    "调整VAD敏感度以减少处理频率",
                    "关闭其他占用CPU的应用程序",
                    "增加音频处理的缓冲区大小"
                ]
            })

        # 内存优化建议
        memory_analysis = analysis['memory_analysis']
        if memory_analysis['performance_level'] in ['critical', 'poor', 'limited']:
            recommendations.append({
                'category': 'memory',
                'priority': 'high' if memory_analysis['performance_level'] == 'critical' else 'medium',
                'title': '内存使用不足',
                'description': f"内存使用率: {memory_analysis['percent']:.1f}%，总内存: {memory_analysis['total_gb']} GB",
                'suggestions': [
                    "增加系统内存容量",
                    "关闭不必要的应用程序",
                    "优化模型缓存策略",
                    "使用较小的模型文件",
                    "调整音频缓冲区大小"
                ]
            })

        # GPU优化建议
        gpu_analysis = analysis['gpu_analysis']
        if gpu_analysis['performance_level'] == 'no_gpu':
            recommendations.append({
                'category': 'gpu',
                'priority': 'medium',
                'title': 'GPU不可用',
                'description': "系统未检测到可用的GPU或CUDA环境",
                'suggestions': [
                    "安装NVIDIA GPU驱动程序",
                    "安装CUDA Toolkit",
                    "安装GPU版本的PyTorch",
                    "验证GPU硬件兼容性"
                ]
            })
        elif gpu_analysis['performance_level'] in ['overloaded', 'high_usage']:
            recommendations.append({
                'category': 'gpu',
                'priority': 'medium',
                'title': 'GPU内存使用率高',
                'description': f"GPU内存使用率: {gpu_analysis['gpus'][0]['memory_percent']:.1f}%",
                'suggestions': [
                    "关闭其他使用GPU的应用程序",
                    "减少批处理大小",
                    "使用较小的模型",
                    "启用混合精度计算"
                ]
            })

        # 磁盘优化建议
        disk_analysis = analysis['disk_analysis']
        if disk_analysis['performance_level'] in ['critical', 'poor', 'limited']:
            recommendations.append({
                'category': 'disk',
                'priority': 'medium',
                'title': '磁盘空间不足',
                'description': f"磁盘使用率: {disk_analysis['percent']:.1f}%，剩余空间: {disk_analysis['free_gb']} GB",
                'suggestions': [
                    "清理临时文件和日志",
                    "移动模型文件到其他磁盘",
                    "压缩或删除旧的测试数据",
                    "增加磁盘容量"
                ]
            })

        # 通用性能优化建议
        recommendations.append({
            'category': 'general',
            'priority': 'low',
            'title': '通用性能优化',
            'description': '提升系统整体性能的建议',
            'suggestions': [
                "设置合适的环境变量 (OMP_NUM_THREADS)",
                "使用专用的Python虚拟环境",
                "定期更新依赖包到最新版本",
                "配置系统电源管理为高性能模式",
                "禁用不必要的系统服务"
            ]
        })

        return recommendations

    def apply_automatic_optimizations(self) -> Dict[str, Any]:
        """应用自动优化"""
        logger.info("应用自动优化...")

        optimizations = {
            'environment_variables': self._optimize_environment_variables(),
            'system_settings': self._optimize_system_settings(),
            'project_settings': self._optimize_project_settings(),
            'cleanup': self._perform_cleanup()
        }

        return optimizations

    def _optimize_environment_variables(self) -> Dict[str, Any]:
        """优化环境变量"""
        logger.info("优化环境变量...")

        optimizations = {}

        # 设置OpenMP线程数
        cpu_count = psutil.cpu_count()
        optimal_threads = min(cpu_count, 8)  # 最多8个线程

        os.environ['OMP_NUM_THREADS'] = str(optimal_threads)
        optimizations['OMP_NUM_THREADS'] = optimal_threads

        # 设置PyTorch线程数
        os.environ['TORCH_NUM_THREADS'] = str(optimal_threads)
        optimizations['TORCH_NUM_THREADS'] = optimal_threads

        # 禁用TensorFlow GPU内存增长（如果使用）
        os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'
        optimizations['TF_FORCE_GPU_ALLOW_GROWTH'] = True

        # 设置CUDA缓存目录
        cache_dir = project_root / ".cache" / "cuda"
        cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ['CUDA_CACHE_PATH'] = str(cache_dir)
        optimizations['CUDA_CACHE_PATH'] = str(cache_dir)

        # 设置Python优化
        os.environ['PYTHONOPTIMIZE'] = '1'
        optimizations['PYTHONOPTIMIZE'] = '1'

        logger.info(f"环境变量优化完成: {optimizations}")
        return optimizations

    def _optimize_system_settings(self) -> Dict[str, Any]:
        """优化系统设置"""
        logger.info("优化系统设置...")

        optimizations = {}

        try:
            # Windows特定优化
            if os.name == 'nt':
                # 设置进程优先级
                current_process = psutil.Process()
                current_process.nice(psutil.HIGH_PRIORITY_CLASS)
                optimizations['process_priority'] = 'high'

                # 优化内存管理
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetProcessWorkingSetSize(-1, -1, -1)
                    optimizations['memory_trim'] = True
                except Exception as e:
                    logger.warning(f"内存优化失败: {e}")

        except Exception as e:
            logger.warning(f"系统设置优化失败: {e}")
            optimizations['error'] = str(e)

        return optimizations

    def _optimize_project_settings(self) -> Dict[str, Any]:
        """优化项目设置"""
        logger.info("优化项目设置...")

        optimizations = {}

        # 创建优化配置文件
        config_dir = project_root / "config"
        config_dir.mkdir(exist_ok=True)

        optimized_config = {
            'performance': {
                'use_gpu': True,
                'batch_size': 1,
                'num_workers': min(4, psutil.cpu_count()),
                'prefetch_factor': 2,
                'pin_memory': True
            },
            'audio': {
                'chunk_size': 1024,  # 优化音频缓冲区
                'sample_rate': 16000,
                'channels': 1
            },
            'vad': {
                'sensitivity': 0.6,  # 平衡敏感度
                'min_speech_duration_ms': 250,
                'min_silence_duration_ms': 100
            },
            'logging': {
                'level': 'INFO',  # 减少日志输出
                'max_log_size_mb': 50,
                'backup_count': 3
            }
        }

        config_file = config_dir / "optimized.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(optimized_config, f, indent=2, ensure_ascii=False)

        optimizations['config_file'] = str(config_file)
        optimizations['settings'] = optimized_config

        return optimizations

    def _perform_cleanup(self) -> Dict[str, Any]:
        """执行清理操作"""
        logger.info("执行清理操作...")

        cleanup_results = {
            'cache_cleaned': False,
            'logs_cleaned': False,
            'temp_cleaned': False,
            'space_freed_mb': 0
        }

        try:
            # 清理缓存目录
            cache_dir = project_root / ".cache"
            if cache_dir.exists():
                space_before = self._get_directory_size(cache_dir)
                self._clean_directory(cache_dir, keep_recent_days=7)
                space_after = self._get_directory_size(cache_dir)
                cleanup_results['cache_cleaned'] = True
                cleanup_results['space_freed_mb'] += (space_before - space_after) / (1024**2)

            # 清理日志文件
            logs_dir = project_root / "logs"
            if logs_dir.exists():
                space_before = self._get_directory_size(logs_dir)
                self._clean_old_logs(logs_dir, keep_days=30)
                space_after = self._get_directory_size(logs_dir)
                cleanup_results['logs_cleaned'] = True
                cleanup_results['space_freed_mb'] += (space_before - space_after) / (1024**2)

            # 清理临时文件
            temp_dirs = [project_root / "temp", project_root / "__pycache__"]
            for temp_dir in temp_dirs:
                if temp_dir.exists():
                    space_before = self._get_directory_size(temp_dir)
                    self._clean_directory(temp_dir)
                    space_after = self._get_directory_size(temp_dir) if temp_dir.exists() else 0
                    cleanup_results['temp_cleaned'] = True
                    cleanup_results['space_freed_mb'] += (space_before - space_after) / (1024**2)

        except Exception as e:
            logger.warning(f"清理操作失败: {e}")
            cleanup_results['error'] = str(e)

        logger.info(f"清理完成，释放空间: {cleanup_results['space_freed_mb']:.1f} MB")
        return cleanup_results

    def _get_directory_size(self, directory: Path) -> int:
        """获取目录大小（字节）"""
        total_size = 0
        try:
            for file_path in directory.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except Exception as e:
            logger.warning(f"计算目录大小失败 {directory}: {e}")
        return total_size

    def _clean_directory(self, directory: Path, keep_recent_days: int = 0):
        """清理目录（删除旧文件）"""
        import time
        current_time = time.time()
        cutoff_time = current_time - (keep_recent_days * 24 * 3600)

        try:
            for file_path in directory.rglob('*'):
                if file_path.is_file():
                    if keep_recent_days == 0 or file_path.stat().st_mtime < cutoff_time:
                        file_path.unlink()
                        logger.debug(f"删除文件: {file_path}")
        except Exception as e:
            logger.warning(f"清理目录失败 {directory}: {e}")

    def _clean_old_logs(self, logs_dir: Path, keep_days: int = 30):
        """清理旧日志文件"""
        import time
        current_time = time.time()
        cutoff_time = current_time - (keep_days * 24 * 3600)

        try:
            for log_file in logs_dir.glob('*.log*'):
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    logger.debug(f"删除旧日志: {log_file}")
        except Exception as e:
            logger.warning(f"清理日志失败: {e}")

    def generate_optimization_report(self, analysis: Dict[str, Any], optimizations: Dict[str, Any]):
        """生成优化报告"""
        logger.info("生成优化报告...")

        reports_dir = project_root / "reports"
        reports_dir.mkdir(exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_path = reports_dir / f"optimization_report_{timestamp}.json"

        report = {
            'timestamp': timestamp,
            'analysis': analysis,
            'optimizations': optimizations,
            'summary': {
                'total_recommendations': len(analysis['recommendations']),
                'high_priority_issues': len([r for r in analysis['recommendations'] if r['priority'] == 'high']),
                'optimizations_applied': len(optimizations),
                'space_freed_mb': optimizations.get('cleanup', {}).get('space_freed_mb', 0)
            }
        }

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        # 生成文本报告
        text_report_path = reports_dir / f"optimization_report_{timestamp}.txt"
        with open(text_report_path, 'w', encoding='utf-8') as f:
            f.write("实时语音转录系统性能优化报告\n")
            f.write("=" * 50 + "\n\n")

            # 系统分析结果
            f.write("系统分析结果:\n")
            f.write("-" * 20 + "\n")
            f.write(f"CPU性能: {analysis['cpu_analysis']['performance_level']}\n")
            f.write(f"内存性能: {analysis['memory_analysis']['performance_level']}\n")
            f.write(f"GPU性能: {analysis['gpu_analysis']['performance_level']}\n")
            f.write(f"磁盘性能: {analysis['disk_analysis']['performance_level']}\n\n")

            # 优化建议
            f.write("优化建议:\n")
            f.write("-" * 20 + "\n")
            for i, rec in enumerate(analysis['recommendations'], 1):
                f.write(f"{i}. {rec['title']} (优先级: {rec['priority']})\n")
                f.write(f"   {rec['description']}\n")
                for suggestion in rec['suggestions']:
                    f.write(f"   - {suggestion}\n")
                f.write("\n")

            # 应用的优化
            f.write("已应用的优化:\n")
            f.write("-" * 20 + "\n")
            for category, details in optimizations.items():
                f.write(f"{category}: {details}\n")

        logger.info(f"优化报告已生成: {report_path}")


def main():
    """主函数"""
    print("实时语音转录系统性能优化器")
    print("=" * 50)

    optimizer = PerformanceOptimizer()

    # 分析系统性能
    print("正在分析系统性能...")
    analysis = optimizer.analyze_system_performance()

    # 显示分析结果
    print("\n系统性能分析结果:")
    print("-" * 30)
    print(f"CPU性能: {analysis['cpu_analysis']['performance_level']}")
    print(f"内存性能: {analysis['memory_analysis']['performance_level']}")
    print(f"GPU性能: {analysis['gpu_analysis']['performance_level']}")
    print(f"磁盘性能: {analysis['disk_analysis']['performance_level']}")

    # 显示建议数量
    recommendations = analysis['recommendations']
    high_priority = [r for r in recommendations if r['priority'] == 'high']
    print(f"\n发现 {len(recommendations)} 条优化建议，其中 {len(high_priority)} 条高优先级")

    # 自动应用优化（在CI环境中）
    apply_optimizations = True
    print("\n自动应用优化...")

    if apply_optimizations:
        print("正在应用自动优化...")
        optimizations = optimizer.apply_automatic_optimizations()
        print("自动优化完成")

        # 生成优化报告
        optimizer.generate_optimization_report(analysis, optimizations)
        print("优化报告已生成到 reports/ 目录")
    else:
        print("跳过自动优化，仅生成分析报告")
        optimizer.generate_optimization_report(analysis, {})

    print("\n优化完成！建议重启应用程序以确保所有优化生效。")


if __name__ == "__main__":
    main()