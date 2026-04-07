"""
soundcard 兼容性工具模块

用于修复 soundcard 在新版 numpy 下调用 `numpy.fromstring(binary_data, ...)`
导致异常或潜在内存引用问题的兼容性问题。
"""

from __future__ import annotations

import logging

import numpy as np


logger = logging.getLogger(__name__)

# 兼容补丁标记，避免重复打补丁
_PATCH_FLAG_ATTR = "_speech2subtitles_soundcard_numpy_compat"


def apply_soundcard_numpy_compat() -> bool:
    """
    应用 soundcard 与 numpy 的兼容补丁。

    设计目标：
    1. 仅在检测到 binary fromstring 失效时启用；
    2. 保持旧版 fromstring(binary) 的“拷贝语义”，避免引用已释放缓冲区；
    3. 可重复调用且幂等。

    Returns:
        bool: True 表示已应用补丁；False 表示无需补丁或应用失败。
    """
    try:
        current_fromstring = np.fromstring

        # 已应用过补丁，直接返回
        if getattr(current_fromstring, _PATCH_FLAG_ATTR, False):
            return True

        # 探测当前 numpy 是否还支持二进制 fromstring
        try:
            current_fromstring(b"\x00\x00\x80?", dtype=np.float32)
            return False
        except ValueError as exc:
            if "binary mode of fromstring is removed" not in str(exc):
                # 其它 ValueError 不处理，避免误伤
                return False

        original_fromstring = current_fromstring

        def _fromstring_compat(string, dtype=float, count=-1, sep="", **kwargs):
            """
            兼容实现：
            - sep=="" 时走 frombuffer + copy，兼容 binary 模式并复制数据
            - 其它场景回退原生 fromstring
            """
            if sep == "":
                like = kwargs.get("like", None)
                if like is None:
                    return np.frombuffer(string, dtype=dtype, count=count).copy()
                try:
                    return np.frombuffer(
                        string,
                        dtype=dtype,
                        count=count,
                        like=like,
                    ).copy()
                except TypeError:
                    # 旧 numpy 可能不支持 like 参数
                    return np.frombuffer(string, dtype=dtype, count=count).copy()

            return original_fromstring(
                string,
                dtype=dtype,
                count=count,
                sep=sep,
                **kwargs,
            )

        # 打标记，确保补丁可识别
        setattr(_fromstring_compat, _PATCH_FLAG_ATTR, True)
        setattr(_fromstring_compat, "__wrapped__", original_fromstring)
        np.fromstring = _fromstring_compat

        logger.info("已应用 soundcard/numpy 兼容补丁（fromstring -> frombuffer.copy）")
        return True
    except Exception as exc:
        logger.warning(f"应用 soundcard/numpy 兼容补丁失败: {exc}")
        return False
