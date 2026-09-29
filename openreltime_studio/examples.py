"""内置示例文件（bundled example）。

软件随包发行一棵小示例树和一份配套的校正点表，用户不必先去找数据就能立刻
跑完整流程：载入 → RRF → 校正 → CI → CorrTest / ddBD → 导出。

文件位于包内的 ``examples/`` 目录，因此安装版与冻结打包（.app）都能取到；
路径一律由本模块暴露，界面代码不拼接相对路径。

.. note::
   示例里的校正边界只是**演示用的假想约束**，用来展示 min/max 的写法与生效
   方式，不代表任何已发表的定年结论。
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "EXAMPLE_CALIBRATIONS_FILENAME",
    "EXAMPLE_TREE_FILENAME",
    "example_calibrations_path",
    "example_files",
    "example_tree_path",
    "examples_dir",
]

EXAMPLE_TREE_FILENAME = "example_tree.nwk"
EXAMPLE_CALIBRATIONS_FILENAME = "example_calibrations.tsv"

_EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"


def examples_dir() -> Path:
    """内置示例所在目录。"""
    return _EXAMPLES_DIR


def example_tree_path() -> Path:
    """内置示例树（Newick）的路径。"""
    return _EXAMPLES_DIR / EXAMPLE_TREE_FILENAME


def example_calibrations_path() -> Path:
    """内置示例校正点表（TSV）的路径。"""
    return _EXAMPLES_DIR / EXAMPLE_CALIBRATIONS_FILENAME


def example_files() -> dict[str, Path]:
    """全部内置示例文件，缺失时抛 ``FileNotFoundError``。"""
    files = {"tree": example_tree_path(), "calibrations": example_calibrations_path()}
    missing = [str(path) for path in files.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"bundled example files missing: {missing}")
    return files
