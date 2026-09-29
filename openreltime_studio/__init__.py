"""OpenRelTime Studio — 原生桌面 GUI（PySide6，不依赖浏览器）。

面向不写代码的研究者，把 openreltime 公共 API 包成独立桌面软件。
所有计算经由适配层 ``adapters`` 调用 ``openreltime``，GUI 不重写任何算法。
"""

from __future__ import annotations

__all__ = ["__version__", "main"]

#: 与 pyproject.toml 中的 project.version 保持一致。
__version__ = "0.1.0"


def main():
    """Studio 入口（等价于 ``python openreltime_studio/main.py``）。"""
    from openreltime_studio.main import main as _main
    return _main()
