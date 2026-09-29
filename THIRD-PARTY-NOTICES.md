# Third-party notices

**Language: English** · [简体中文](THIRD-PARTY-NOTICES-zh.md)

OpenRelTime Studio is GPL-3.0-or-later, but it links against libraries under
other licenses. Their terms are summarised here; the authoritative text ships
with each distribution.

| Component | License | Role |
| --- | --- | --- |
| [OpenRelTime](https://github.com/ZengZichao/OpenRelTime) | GPL-3.0-or-later | the computation engine; every analysis result comes from it |
| [Qt 6](https://www.qt.io/qt-licensing) | LGPLv3 (with commercial option) | toolkit behind PySide6 |
| [PySide6](https://pypi.org/project/PySide6/) | LGPL-3.0 | Python bindings for Qt (QtWidgets, QtGui, QtCore, QtSvg) |
| [matplotlib](https://matplotlib.org) | BSD-style (PSF-based) | tree canvas and exported figures |
| [NumPy](https://numpy.org) | BSD-3-Clause | array computation |
| [SciPy](https://scipy.org) | BSD-3-Clause | statistics and optimisation used by the engine |
| [pandas](https://pandas.pydata.org) | BSD-3-Clause | result tables |
| [Click](https://click.palletsprojects.com) | BSD-3-Clause | the engine's command line (not the GUI) |

## Application icon

`openreltime_studio/resources/icons/OpenRelTime-Studio.svg` is original work of
the OpenRelTime project, released under GPL-3.0-or-later together with the rest
of the source. `icon.png` and `icon.icns` are rasterisations of that SVG,
regenerated with `openreltime_studio/resources/make_icon.py`.

## Fonts

The interface uses the platform's default UI font; the equivalent-CLI panel
requests a monospace family (`SF Mono`, `Menlo`, `Consolas`) and falls back to
whatever the system provides. No font files are redistributed.

## Trademarks

Qt is a trademark of The Qt Company Ltd. Python is a trademark of the Python
Software Foundation.
