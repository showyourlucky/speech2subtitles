"""
GPU detection module tests

Test GPUDetector and related classes
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# 使用绝对导入而不是相对导入
from src.hardware.gpu_detector import gpu_detector
from src.hardware.models import GPUInfo, SystemInfo



if __name__ == "__main__":
    # Run simple tests
    gpu_detector.print_system_info()