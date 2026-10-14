"""仓库根级 pytest 配置。

这里**不再**做任何「没装 PySide6 就跳过整个测试目录」的门控。旧实现在
``import PySide6`` 失败时设 ``collect_ignore_glob=["openreltime_studio/tests"]``，
于是打包自检、内置示例资源、文档卫生、i18n 目录静态检查这些根本不碰 Qt 的
用例也一起消失（实测 ``no tests collected``、退出码 5），与本仓库
``openreltime_studio/tests/test_i18n_catalogs.py`` 开头「不依赖 Qt，没装
PySide6 也能跑」的注释互相矛盾。

门控现在按**单个用例**粒度放在 ``openreltime_studio/tests/conftest.py``：
需要 Qt 绑定的标 ``pytest.mark.requires_qt``，需要引擎 ``openreltime`` 的标
``pytest.mark.requires_engine``，缺哪个跳哪个，理由里点名成因与修复命令。
夹具也在同一个文件里（随包发行，安装后可用
``python -m pytest --pyargs openreltime_studio.tests`` 单独运行）。

根级只保留一件与收集无关的事：GUI 用例在无显示器的机器上以 offscreen
平台插件运行，环境变量必须在任何 Qt 导入之前设好。
"""

from __future__ import annotations

import os
import sys

try:  # pragma: no cover - 环境相关
    import PySide6  # noqa: F401

    _HAVE_QT = True
except ImportError:  # pragma: no cover - 无 GUI extra：只跑非 Qt 用例
    _HAVE_QT = False

if _HAVE_QT:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#: 源码检出下让 ``import openreltime_studio`` 直接可用（测试从包内路径运行）。
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
