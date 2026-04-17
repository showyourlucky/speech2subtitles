#!/usr/bin/env python3
"""
性能测试脚本

用于测试系统各组件的性能指标，包括：
- 模型加载时间
- 音频处理延迟
- VAD检测性能
- 转录引擎性能
- 内存使用情况
- GPU利用率
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import psutil

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入项目组件
from src.audio.models import AudioChunk
from src.config.models import Config
from src.hardware.gpu_detector import GPUDetector
from src.output.handler import OutputHandler
from src.transcription.engine_manager import (
    TranscriptionEngineManager,  # 使用转录引擎管理器
)
from src.utils.logger import LogConfig, LogLevel, get_logger, setup_logging
from src.vad import VadManager  # 使用 VAD 管理器

# 配置日志
setup_logging(LogConfig(level=LogLevel.INFO))
logger = get_logger('performance_test')

class PerformanceTestSuite:
    """性能测试套件"""

    def __init__(self, config: Config):
        self.config = config
        self.results = {}
        self.gpu_detector = GPUDetector()

    def run_all_tests(self) -> dict[str, Any]:
        """运行所有性能测试"""
        logger.info("开始性能测试套件...")

        # 系统信息
        self.results['system_info'] = self._collect_system_info()

        # 组件性能测试
        self.results['gpu_detection'] = self._test_gpu_detection()
        self.results['vad_performance'] = self._test_vad_performance()
        self.results['transcription_performance'] = self._test_transcription_performance()
        self.results['memory_usage'] = self._test_memory_usage()
        self.results['integration_test'] = self._test_integration_performance()

        # 生成性能报告
        self._generate_performance_report()

        return self.results

    def _collect_system_info(self) -> dict[str, Any]:
        """收集系统信息"""
        logger.info("收集系统信息...")

        # CPU信息
        cpu_info = {
            'cpu_count': psutil.cpu_count(),
            'cpu_count_logical': psutil.cpu_count(logical=True),
            'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
        }

        # 内存信息
        memory = psutil.virtual_memory()
        memory_info = {
            'total_gb': round(memory.total / (1024**3), 2),
            'available_gb': round(memory.available / (1024**3), 2),
            'percent': memory.percent
        }

        # GPU信息
        gpu_info = {}
        try:
            system_info = self.gpu_detector.get_system_info()
            if system_info and system_info.gpu_info:
                gpu_info = {
                    'gpu_count': len(system_info.gpu_info),
                    'gpus': [
                        {
                            'name': gpu.name,
                            'memory_total': gpu.memory_total,
                            'memory_free': gpu.memory_free,
                            'utilization': gpu.utilization_gpu
                        }
                        for gpu in system_info.gpu_info
                    ]
                }
        except Exception as e:
            gpu_info = {'error': str(e)}

        return {
            'cpu': cpu_info,
            'memory': memory_info,
            'gpu': gpu_info
        }

    def _test_gpu_detection(self) -> dict[str, Any]:
        """测试GPU检测性能"""
        logger.info("测试GPU检测性能...")

        results = {
            'cuda_detection_time': 0,
            'system_info_time': 0,
            'cuda_available': False,
            'multiple_runs': []
        }

        # 测试CUDA检测时间
        for i in range(5):
            start_time = time.perf_counter()
            cuda_available = self.gpu_detector.detect_cuda()
            detection_time = time.perf_counter() - start_time

            results['multiple_runs'].append({
                'run': i + 1,
                'detection_time': detection_time,
                'cuda_available': cuda_available
            })

            if i == 0:
                results['cuda_available'] = cuda_available

        # 平均检测时间
        avg_detection_time = np.mean([run['detection_time'] for run in results['multiple_runs']])
        results['avg_detection_time'] = avg_detection_time

        # 测试系统信息获取时间
        start_time = time.perf_counter()
        system_info = self.gpu_detector.get_system_info()
        results['system_info_time'] = time.perf_counter() - start_time

        logger.info(f"GPU检测平均时间: {avg_detection_time:.4f}秒")

        return results

    def _test_vad_performance(self) -> dict[str, Any]:
        """测试VAD性能"""
        logger.info("测试VAD性能...")

        results = {
            'initialization_time': 0,
            'detection_times': [],
            'avg_detection_time': 0,
            'throughput_samples_per_second': 0
        }

        try:
            # 测试VAD初始化时间（使用 VadManager 实现智能复用）
            start_time = time.perf_counter()
            vad = VadManager.get_detector(self.config)
            results['initialization_time'] = time.perf_counter() - start_time

            # 生成测试音频数据
            sample_rate = 16000
            duration = 1.0  # 1秒
            samples = int(sample_rate * duration)

            # 测试不同音频数据的检测性能
            test_cases = [
                ('silence', np.zeros(samples, dtype=np.float32)),
                ('noise', np.random.normal(0, 0.1, samples).astype(np.float32)),
                ('sine_wave', np.sin(2 * np.pi * 440 * np.linspace(0, duration, samples)).astype(np.float32))
            ]

            for case_name, audio_data in test_cases:
                detection_times = []

                # 多次测试取平均值
                for _ in range(10):
                    start_time = time.perf_counter()

                    # 模拟音频数据处理
                    audio_chunk = AudioChunk(
                        data=audio_data,
                        sample_rate=sample_rate,
                        channels=1,
                        timestamp=time.time(),
                        duration_ms=duration * 1000
                    )

                    result = vad.detect_voice_activity(audio_chunk)
                    detection_time = time.perf_counter() - start_time
                    detection_times.append(detection_time)

                avg_time = np.mean(detection_times)
                results['detection_times'].append({
                    'case': case_name,
                    'avg_time': avg_time,
                    'min_time': np.min(detection_times),
                    'max_time': np.max(detection_times),
                    'std_time': np.std(detection_times)
                })

            # 计算整体平均检测时间
            all_times = [case['avg_time'] for case in results['detection_times']]
            results['avg_detection_time'] = np.mean(all_times)

            # 计算吞吐量（每秒处理的样本数）
            results['throughput_samples_per_second'] = samples / results['avg_detection_time']

            logger.info(f"VAD平均检测时间: {results['avg_detection_time']:.4f}秒")
            logger.info(f"VAD吞吐量: {results['throughput_samples_per_second']:.0f} 样本/秒")

        except Exception as e:
            results['error'] = str(e)
            logger.error(f"VAD性能测试失败: {e}")

        return results

    def _test_transcription_performance(self) -> dict[str, Any]:
        """测试转录引擎性能"""
        logger.info("测试转录引擎性能...")

        results = {
            'initialization_time': 0,
            'model_loading_time': 0,
            'transcription_tests': [],
            'error': None
        }

        try:
            # 检查模型文件是否存在
            if not os.path.exists(self.config.model_path):
                results['error'] = f"模型文件不存在: {self.config.model_path}"
                logger.warning(results['error'])
                return results

            # 测试转录引擎初始化时间
            start_time = time.perf_counter()
            engine = TranscriptionEngine(self.config)
            results['initialization_time'] = time.perf_counter() - start_time

            # 生成不同长度的测试音频
            sample_rate = 16000
            test_durations = [0.5, 1.0, 2.0, 5.0]  # 秒

            for duration in test_durations:
                samples = int(sample_rate * duration)
                # 生成正弦波作为测试音频
                audio_data = np.sin(2 * np.pi * 440 * np.linspace(0, duration, samples)).astype(np.float32)

                # 测试转录性能
                transcription_times = []
                for _ in range(3):  # 每个长度测试3次
                    start_time = time.perf_counter()

                    try:
                        audio_chunk = AudioChunk(
                            data=audio_data,
                            sample_rate=sample_rate,
                            channels=1,
                            timestamp=time.time(),
                            duration_ms=duration * 1000
                        )

                        result = engine.transcribe(audio_chunk)
                        transcription_time = time.perf_counter() - start_time
                        transcription_times.append(transcription_time)

                    except Exception as e:
                        logger.warning(f"转录测试失败 (duration={duration}s): {e}")
                        continue

                if transcription_times:
                    avg_time = np.mean(transcription_times)
                    real_time_factor = duration / avg_time  # 实时性能因子

                    results['transcription_tests'].append({
                        'duration': duration,
                        'avg_time': avg_time,
                        'min_time': np.min(transcription_times),
                        'max_time': np.max(transcription_times),
                        'real_time_factor': real_time_factor,
                        'faster_than_realtime': real_time_factor > 1.0
                    })

            logger.info("转录引擎性能测试完成")

        except Exception as e:
            results['error'] = str(e)
            logger.error(f"转录引擎性能测试失败: {e}")

        return results

    def _test_memory_usage(self) -> dict[str, Any]:
        """测试内存使用情况"""
        logger.info("测试内存使用情况...")

        results = {
            'baseline_memory': {},
            'component_memory': {},
            'peak_memory': {},
            'memory_growth': []
        }

        # 记录基线内存
        process = psutil.Process()
        baseline_memory = process.memory_info()
        results['baseline_memory'] = {
            'rss_mb': baseline_memory.rss / (1024 * 1024),
            'vms_mb': baseline_memory.vms / (1024 * 1024)
        }

        # 测试各组件的内存占用
        components = []

        try:
            # GPU检测器
            gpu_detector = GPUDetector()
            memory_after_gpu = process.memory_info()
            components.append(('gpu_detector', memory_after_gpu))

            # VAD检测器（使用 VadManager 实现智能复用）
            vad = VadManager.get_detector(self.config)
            memory_after_vad = process.memory_info()
            components.append(('vad', memory_after_vad))

            # 如果模型文件存在，测试转录引擎（使用 TranscriptionEngineManager 实现智能复用）
            if os.path.exists(self.config.model_path):
                engine = TranscriptionEngineManager.get_engine(self.config)
                memory_after_engine = process.memory_info()
                components.append(('transcription_engine', memory_after_engine))

            # 输出处理器
            output_handler = OutputHandler(self.config)
            memory_after_output = process.memory_info()
            components.append(('output_handler', memory_after_output))

        except Exception as e:
            logger.warning(f"内存测试中组件加载失败: {e}")

        # 计算组件内存增长
        prev_memory = baseline_memory
        for component_name, current_memory in components:
            memory_growth = current_memory.rss - prev_memory.rss
            results['component_memory'][component_name] = {
                'rss_mb': current_memory.rss / (1024 * 1024),
                'growth_mb': memory_growth / (1024 * 1024)
            }
            prev_memory = current_memory

        # 记录峰值内存
        peak_memory = process.memory_info()
        results['peak_memory'] = {
            'rss_mb': peak_memory.rss / (1024 * 1024),
            'total_growth_mb': (peak_memory.rss - baseline_memory.rss) / (1024 * 1024)
        }

        logger.info(f"峰值内存使用: {results['peak_memory']['rss_mb']:.1f} MB")
        logger.info(f"总内存增长: {results['peak_memory']['total_growth_mb']:.1f} MB")

        return results

    def _test_integration_performance(self) -> dict[str, Any]:
        """测试集成性能"""
        logger.info("测试集成性能...")

        results = {
            'end_to_end_latency': [],
            'avg_latency': 0,
            'throughput': 0,
            'error_rate': 0,
            'errors': []
        }

        try:
            # 创建所有必要组件（使用管理器实现智能复用）
            components = {
                'gpu_detector': GPUDetector(),
                'vad': VadManager.get_detector(self.config),
                'output_handler': OutputHandler(self.config)
            }

            # 如果模型文件存在，添加转录引擎（使用 TranscriptionEngineManager 实现智能复用）
            if os.path.exists(self.config.model_path):
                components['transcription_engine'] = TranscriptionEngineManager.get_engine(self.config)

            # 生成测试音频数据
            sample_rate = 16000
            chunk_duration = 1.0  # 1秒块
            samples_per_chunk = int(sample_rate * chunk_duration)

            # 模拟端到端处理流程
            test_chunks = 10
            successful_processes = 0

            for i in range(test_chunks):
                try:
                    start_time = time.perf_counter()

                    # 1. 生成音频数据
                    audio_data = np.sin(2 * np.pi * 440 * np.linspace(0, chunk_duration, samples_per_chunk)).astype(np.float32)
                    audio_chunk = AudioChunk(
                        data=audio_data,
                        sample_rate=sample_rate,
                        channels=1,
                        timestamp=time.time(),
                        duration_ms=chunk_duration * 1000
                    )

                    # 2. VAD检测
                    vad_result = components['vad'].detect_voice_activity(audio_chunk)

                    # 3. 如果检测到语音且有转录引擎，进行转录
                    if vad_result.voice_detected and 'transcription_engine' in components:
                        transcription_result = components['transcription_engine'].transcribe(audio_chunk)

                        # 4. 输出处理
                        components['output_handler'].handle_result(transcription_result, vad_result)

                    # 计算端到端延迟
                    end_time = time.perf_counter()
                    latency = end_time - start_time
                    results['end_to_end_latency'].append(latency)
                    successful_processes += 1

                except Exception as e:
                    results['errors'].append(f"Chunk {i}: {str(e)}")
                    logger.warning(f"集成测试块 {i} 失败: {e}")

            # 计算统计指标
            if results['end_to_end_latency']:
                results['avg_latency'] = np.mean(results['end_to_end_latency'])
                results['min_latency'] = np.min(results['end_to_end_latency'])
                results['max_latency'] = np.max(results['end_to_end_latency'])
                results['std_latency'] = np.std(results['end_to_end_latency'])

                # 吞吐量（每秒处理的音频块数）
                results['throughput'] = 1.0 / results['avg_latency']

                # 实时性能因子
                results['real_time_factor'] = chunk_duration / results['avg_latency']
                results['meets_realtime'] = results['real_time_factor'] > 1.0

            # 错误率
            results['error_rate'] = (test_chunks - successful_processes) / test_chunks
            results['success_rate'] = successful_processes / test_chunks

            logger.info(f"集成测试平均延迟: {results.get('avg_latency', 0):.4f}秒")
            logger.info(f"集成测试成功率: {results['success_rate']:.2%}")

        except Exception as e:
            results['error'] = str(e)
            logger.error(f"集成性能测试失败: {e}")

        return results

    def _generate_performance_report(self):
        """生成性能报告"""
        logger.info("生成性能报告...")

        # 创建报告目录
        reports_dir = project_root / "reports"
        reports_dir.mkdir(exist_ok=True)

        # 生成JSON报告
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        json_report_path = reports_dir / f"performance_report_{timestamp}.json"

        with open(json_report_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False, default=str)

        # 生成文本报告
        text_report_path = reports_dir / f"performance_report_{timestamp}.txt"
        with open(text_report_path, 'w', encoding='utf-8') as f:
            f.write("实时语音转录系统性能测试报告\n")
            f.write("=" * 50 + "\n\n")

            # 系统信息
            f.write("系统信息:\n")
            f.write("-" * 20 + "\n")
            system_info = self.results['system_info']
            f.write(f"CPU核心数: {system_info['cpu']['cpu_count']}\n")
            f.write(f"CPU逻辑核心数: {system_info['cpu']['cpu_count_logical']}\n")
            f.write(f"内存总量: {system_info['memory']['total_gb']} GB\n")
            f.write(f"GPU信息: {len(system_info['gpu'].get('gpus', []))} 个GPU\n\n")

            # GPU性能
            gpu_results = self.results['gpu_detection']
            f.write("GPU检测性能:\n")
            f.write("-" * 20 + "\n")
            f.write(f"CUDA可用: {gpu_results['cuda_available']}\n")
            f.write(f"平均检测时间: {gpu_results['avg_detection_time']:.4f}秒\n\n")

            # VAD性能
            vad_results = self.results['vad_performance']
            if 'error' not in vad_results:
                f.write("VAD检测性能:\n")
                f.write("-" * 20 + "\n")
                f.write(f"初始化时间: {vad_results['initialization_time']:.4f}秒\n")
                f.write(f"平均检测时间: {vad_results['avg_detection_time']:.4f}秒\n")
                f.write(f"吞吐量: {vad_results['throughput_samples_per_second']:.0f} 样本/秒\n\n")

            # 转录性能
            trans_results = self.results['transcription_performance']
            if 'error' not in trans_results and trans_results['transcription_tests']:
                f.write("转录引擎性能:\n")
                f.write("-" * 20 + "\n")
                f.write(f"初始化时间: {trans_results['initialization_time']:.4f}秒\n")
                for test in trans_results['transcription_tests']:
                    f.write(f"音频长度 {test['duration']}s: "
                           f"处理时间 {test['avg_time']:.4f}s, "
                           f"实时因子 {test['real_time_factor']:.2f}\n")
                f.write("\n")

            # 内存使用
            memory_results = self.results['memory_usage']
            f.write("内存使用情况:\n")
            f.write("-" * 20 + "\n")
            f.write(f"基线内存: {memory_results['baseline_memory']['rss_mb']:.1f} MB\n")
            f.write(f"峰值内存: {memory_results['peak_memory']['rss_mb']:.1f} MB\n")
            f.write(f"总增长: {memory_results['peak_memory']['total_growth_mb']:.1f} MB\n\n")

            # 集成测试
            integration_results = self.results['integration_test']
            if 'error' not in integration_results and integration_results['end_to_end_latency']:
                f.write("集成测试性能:\n")
                f.write("-" * 20 + "\n")
                f.write(f"平均延迟: {integration_results['avg_latency']:.4f}秒\n")
                f.write(f"吞吐量: {integration_results['throughput']:.2f} 块/秒\n")
                f.write(f"实时因子: {integration_results['real_time_factor']:.2f}\n")
                f.write(f"满足实时要求: {integration_results['meets_realtime']}\n")
                f.write(f"成功率: {integration_results['success_rate']:.2%}\n")

        logger.info("性能报告已生成:")
        logger.info(f"  JSON: {json_report_path}")
        logger.info(f"  文本: {text_report_path}")


def main():
    """主函数"""
    print("实时语音转录系统性能测试")
    print("=" * 50)

    # 创建测试配置
    config = Config(
        model_path="models/sense-voice.onnx",  # 模型文件路径
        input_source="microphone",
        vad_threshold=0.5,
        use_gpu=True
    )

    # 运行性能测试
    test_suite = PerformanceTestSuite(config)
    results = test_suite.run_all_tests()

    # 输出简要结果
    print("\n性能测试结果摘要:")
    print("-" * 30)

    # GPU性能
    gpu_results = results['gpu_detection']
    print(f"GPU检测: {gpu_results['avg_detection_time']:.4f}s")

    # VAD性能
    vad_results = results['vad_performance']
    if 'error' not in vad_results:
        print(f"VAD检测: {vad_results['avg_detection_time']:.4f}s")

    # 内存使用
    memory_results = results['memory_usage']
    print(f"峰值内存: {memory_results['peak_memory']['rss_mb']:.1f} MB")

    # 集成测试
    integration_results = results['integration_test']
    if 'error' not in integration_results and integration_results['end_to_end_latency']:
        print(f"端到端延迟: {integration_results['avg_latency']:.4f}s")
        print(f"实时性能: {'满足' if integration_results['meets_realtime'] else '不满足'}")

    print("\n详细报告已保存到 reports/ 目录")


if __name__ == "__main__":
    main()
