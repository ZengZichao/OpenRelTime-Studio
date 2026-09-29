"""从包内 SVG 栅格化 ``icon.png`` / ``icon.icns``。

SVG（``icons/OpenRelTime-Studio.svg``）是图标的唯一权威来源；位图与 macOS
图标包只是派生物，供打包器与安装器使用。改了 SVG 之后重跑本脚本即可：

    python openreltime_studio/resources/make_icon.py

``icon.icns`` 只在 macOS 上生成（依赖系统自带的 ``sips`` / ``iconutil``）。
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent  # openreltime_studio/resources/
sys.path.insert(1, str(ROOT.parent.parent))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from openreltime_studio.appicon import pixmap_from_svg  # noqa: E402

PNG = ROOT / "icon.png"
ICNS = ROOT / "icon.icns"
ICNS_SIZE = 1024


def build_png(app: QApplication) -> Path:
    pm = pixmap_from_svg(512)
    if pm is None:
        raise SystemExit("PySide6.QtSvg 不可用，无法从 SVG 渲染图标")
    pm.save(str(PNG))
    print("icon.png written:", PNG)
    return PNG


def build_icns(app: QApplication) -> Path | None:
    if sys.platform != "darwin":
        print("icon.icns 仅在 macOS 生成，已跳过")
        return None
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "AppIcon.iconset"
        iconset.mkdir()
        for size in (16, 32, 64, 128, 256, 512, 1024):
            pm = pixmap_from_svg(size)
            if pm is None:
                return None
            pm.save(str(iconset / f"icon_{size}x{size}.png"))
            if size <= 512:
                pm2 = pixmap_from_svg(size * 2)
                if pm2 is not None:
                    pm2.save(str(iconset / f"icon_{size}x{size}@2x.png"))
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset), "-o", str(ICNS)],
            check=True,
        )
    print("icon.icns written:", ICNS, f"(from {ICNS_SIZE}px master)")
    return ICNS


def main() -> None:
    app = QApplication.instance() or QApplication([])
    build_png(app)
    build_icns(app)


if __name__ == "__main__":
    main()
