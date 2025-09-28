"""
测试包初始化

提供测试的通用工具和配置
"""

import sys
import os
from pathlib import Path

# 确保src目录在Python路径中
project_root = Path(__file__).parent.parent
src_path = project_root / "src"

if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# 测试常用导入
import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock

# 测试标记定义
pytest_plugins = []

# 测试配置
TEST_DATA_DIR = project_root / "tests" / "data"
TEST_TEMP_DIR = project_root / "tests" / "temp"

# 确保测试目录存在
TEST_DATA_DIR.mkdir(exist_ok=True)
TEST_TEMP_DIR.mkdir(exist_ok=True)

# 测试工具函数
def create_test_audio_data(duration=1.0, sample_rate=16000, channels=1):
    """创建测试音频数据"""
    samples = int(duration * sample_rate)
    if channels == 1:
        return np.random.rand(samples).astype(np.float32)
    else:
        return np.random.rand(samples, channels).astype(np.float32)


def create_temp_file(suffix=".tmp", content=None):
    """创建临时文件"""
    import tempfile
    temp_file = tempfile.NamedTemporaryFile(
        suffix=suffix,
        dir=TEST_TEMP_DIR,
        delete=False
    )

    if content is not None:
        if isinstance(content, str):
            temp_file.write(content.encode('utf-8'))
        else:
            temp_file.write(content)

    temp_file.close()
    return Path(temp_file.name)


def cleanup_temp_files():
    """清理临时文件"""
    if TEST_TEMP_DIR.exists():
        for file in TEST_TEMP_DIR.iterdir():
            if file.is_file():
                file.unlink()


# pytest fixtures
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """设置测试环境"""
    # 测试开始前的设置
    print("\n设置测试环境...")

    # 确保测试目录存在
    TEST_DATA_DIR.mkdir(exist_ok=True)
    TEST_TEMP_DIR.mkdir(exist_ok=True)

    yield

    # 测试结束后的清理
    print("\n清理测试环境...")
    cleanup_temp_files()


@pytest.fixture
def test_audio_data():
    """提供测试音频数据"""
    return create_test_audio_data(duration=1.0)


@pytest.fixture
def temp_model_file():
    """提供临时模型文件"""
    temp_file = create_temp_file(suffix=".onnx", content=b"fake model content")
    yield temp_file
    temp_file.unlink(missing_ok=True)


@pytest.fixture
def mock_logger():
    """提供模拟日志器"""
    return Mock()


# 测试标记工具
def requires_gpu(func):
    """标记需要GPU的测试"""
    return pytest.mark.gpu(func)


def requires_audio_device(func):
    """标记需要音频设备的测试"""
    return pytest.mark.audio(func)


def requires_model_file(func):
    """标记需要模型文件的测试"""
    return pytest.mark.model(func)


def slow_test(func):
    """标记运行较慢的测试"""
    return pytest.mark.slow(func)


# 跳过条件
skip_if_no_gpu = pytest.mark.skipif(
    not os.environ.get("CUDA_VISIBLE_DEVICES", "").strip(),
    reason="没有可用的GPU"
)

skip_if_no_audio = pytest.mark.skipif(
    os.environ.get("CI", "").lower() == "true",
    reason="CI环境中无音频设备"
)

skip_if_no_network = pytest.mark.skipif(
    os.environ.get("OFFLINE", "").lower() == "true",
    reason="离线环境，跳过需要网络的测试"
)

# 导出常用工具
__all__ = [
    "create_test_audio_data",
    "create_temp_file",
    "cleanup_temp_files",
    "TEST_DATA_DIR",
    "TEST_TEMP_DIR",
    "requires_gpu",
    "requires_audio_device",
    "requires_model_file",
    "slow_test",
    "skip_if_no_gpu",
    "skip_if_no_audio",
    "skip_if_no_network"
]