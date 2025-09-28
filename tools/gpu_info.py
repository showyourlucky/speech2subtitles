#!/usr/bin/env python3
"""
GPU Information Tool

Display comprehensive GPU and system information
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from hardware import gpu_detector


def main():
    """Main function"""
    print("=" * 60)
    print("GPU Information Tool")
    print("=" * 60)

    detector = gpu_detector

    # Print system information
    detector.print_system_info()

    print("\n" + "=" * 60)
    print("GPU Capability Analysis")
    print("=" * 60)

    # Check different memory requirements
    memory_requirements = [512, 1024, 2048, 4096, 8192]

    for req_mb in memory_requirements:
        has_memory = detector.check_memory(req_mb)
        status = "[+]" if has_memory else "[-]"
        print(f"{status} {req_mb}MB memory requirement: {'Available' if has_memory else 'Not available'}")

    print("\n" + "=" * 60)
    print("Provider Recommendations")
    print("=" * 60)

    # Provider recommendations
    gpu_provider = detector.get_recommended_provider(prefer_gpu=True)
    cpu_provider = detector.get_recommended_provider(prefer_gpu=False)

    print(f"Best available provider: {gpu_provider}")
    print(f"CPU fallback provider: {cpu_provider}")

    # Show provider options
    if gpu_provider == "CUDAExecutionProvider":
        options = detector.get_provider_options(gpu_provider)
        print(f"GPU provider options:")
        for key, value in options.items():
            print(f"  {key}: {value}")

    print("\n" + "=" * 60)
    print("Dependencies Check")
    print("=" * 60)

    # Check dependencies
    dependencies = {
        "torch": "PyTorch for CUDA detection",
        "onnxruntime": "ONNX Runtime for inference",
        "pynvml": "NVIDIA Management Library (optional)"
    }

    for package, description in dependencies.items():
        try:
            __import__(package)
            status = "[+] Installed"
        except ImportError:
            status = "[-] Not installed"

        print(f"{status:15} {package:12} - {description}")


if __name__ == "__main__":
    main()