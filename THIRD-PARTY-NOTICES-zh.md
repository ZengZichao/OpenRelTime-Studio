# 第三方声明

**语言：中文** · [English](THIRD-PARTY-NOTICES.md)

OpenRelTime Studio 以 GPL-3.0-or-later 发布，但它链接了采用其他许可的库。
这些库的条款在此概述；具有权威效力的条款原文随各自的发行版一同分发。

| 组件 | 许可 | 作用 |
| --- | --- | --- |
| [OpenRelTime](https://github.com/ZengZichao/OpenRelTime) | GPL-3.0-or-later | 计算引擎；所有分析结果都由它产生 |
| [Qt 6](https://www.qt.io/qt-licensing) | LGPLv3（另提供商业许可选项） | PySide6 背后的工具包 |
| [PySide6](https://pypi.org/project/PySide6/) | LGPL-3.0 | Qt 的 Python 绑定（QtWidgets、QtGui、QtCore、QtSvg） |
| [matplotlib](https://matplotlib.org) | BSD 风格（基于 PSF） | 树画布与导出的图形 |
| [NumPy](https://numpy.org) | BSD-3-Clause | 数组计算 |
| [SciPy](https://scipy.org) | BSD-3-Clause | 引擎使用的统计与最优化 |
| [pandas](https://pandas.pydata.org) | BSD-3-Clause | 结果表格 |
| [Click](https://click.palletsprojects.com) | BSD-3-Clause | 引擎的命令行（不是 GUI） |

## 应用图标

`openreltime_studio/resources/icons/OpenRelTime-Studio.svg` 是 OpenRelTime
项目的原创成果，与其余源码一并以 GPL-3.0-or-later 发布。`icon.png` 与
`icon.icns` 都由该 SVG 栅格化而来，使用
`openreltime_studio/resources/make_icon.py` 重新生成。

## 字体

界面使用平台的默认 UI 字体；等效命令行面板请求等宽字体族
（`SF Mono`、`Menlo`、`Consolas`），系统没有时回退到平台提供的任意等宽字体。
本项目不再分发任何字体文件。

## 商标

Qt 是 The Qt Company Ltd. 的商标。Python 是 Python Software Foundation 的商标。
