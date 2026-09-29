# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for OpenRelTime Studio (macOS .app).

Build a standalone desktop application (no browser, no Python install required)::

    pip install OpenRelTime-Studio pyinstaller
    pyinstaller openreltime_studio/resources/OpenRelTimeStudio.spec

Produces ``dist/OpenRelTimeStudio.app`` on macOS.
"""

import os

# SPECPATH is the directory containing this .spec file (openreltime_studio/resources/).
# The project root is two levels up.
_PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))

block_cipher = None

# ── Data files ──────────────────────────────────────────────────────────
# The message catalogs and the SVG icons are package resources read at runtime
# (i18n / appicon locate them through ``Path(__file__).parent``), so they must
# be copied into the frozen .app unchanged.
_STUDIO_PKG = os.path.join(_PROJECT_ROOT, "openreltime_studio")
datas = [
    (os.path.join(_STUDIO_PKG, "locales"), "openreltime_studio/locales"),
    (os.path.join(_STUDIO_PKG, "resources", "icons"), "openreltime_studio/resources/icons"),
    # Bundled example: the UI reaches it through openreltime_studio.examples,
    # so the whole directory ships as well and must stay inside the package.
    (os.path.join(_STUDIO_PKG, "examples"), "openreltime_studio/examples"),
]

# ── App icon (generated: openreltime_studio/resources/icon.icns) ────────────────────
_ICON = os.path.join(_PROJECT_ROOT, "openreltime_studio", "resources", "icon.icns")

# ── Hidden imports (ensure all openreltime submodules are bundled) ──────

hiddenimports = [
    # openreltime core
    "openreltime",
    "openreltime._constants",
    "openreltime._external",
    "openreltime.bootstrap",
    "openreltime.calibrate",
    "openreltime.ci",
    "openreltime.cli",
    "openreltime.corrtest",
    "openreltime.ddbd",
    "openreltime.megacc",
    "openreltime.rates",
    "openreltime.report",
    "openreltime.rrf",
    "openreltime.table",
    "openreltime.taxonomy",
    "openreltime.times",
    "openreltime.tree",
    "openreltime.treeio",
    "openreltime.viz",
    # studio
    "openreltime_studio",
    "openreltime_studio.main",
    "openreltime_studio.i18n",
    "openreltime_studio.themes",
    "openreltime_studio.appicon",
    "openreltime_studio.adapters",
    "openreltime_studio.adapters.openreltime_adapter",
    "openreltime_studio.workers",
    "openreltime_studio.workers.analysis_workers",
    "openreltime_studio.widgets",
    "openreltime_studio.widgets.tree_canvas",
    "openreltime_studio.widgets.node_table",
    "openreltime_studio.widgets.param_panels",
    "openreltime_studio.widgets.calibration_editor",
    "openreltime_studio.windows",
    "openreltime_studio.windows.main_window",
    # GUI / plotting
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSvg",
    "shiboken6",
    "matplotlib",
    "matplotlib.backends",
    "matplotlib.backends.backend_qtagg",
    # scipy/numpy helpers that PyInstaller may miss
    "scipy.stats",
    "scipy.optimize",
    "scipy.special",
]

# ── Analysis ────────────────────────────────────────────────────────────

a = Analysis(
    [os.path.join(_PROJECT_ROOT, "openreltime_studio", "main.py")],
    pathex=[_PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PyQt5", "PyQt6", "IPython", "notebook", "jupyter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── Executable ──────────────────────────────────────────────────────────

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OpenRelTimeStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # --windowed
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# ── macOS .app bundle ───────────────────────────────────────────────────

app = BUNDLE(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="OpenRelTimeStudio.app",
    icon=_ICON if os.path.exists(_ICON) else None,
    bundle_identifier="org.openreltime.studio",
    info_plist={
        "CFBundleDisplayName": "OpenRelTime Studio",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "1",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
    },
)
