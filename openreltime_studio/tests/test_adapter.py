"""适配层单元测试 — mock openreltime API，验证 Result→UI 模型转换。"""

from __future__ import annotations

# 确保项目根目录在 path 中
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from openreltime_studio.adapters import openreltime_adapter as adapter

# ── 树 I/O ──────────────────────────────────────────────────────────────

class TestTreeIO:
    """测试树文件读取与信息提取。"""

    def test_detect_format_newick(self):
        assert adapter.detect_format("tree.nwk") == "newick"
        assert adapter.detect_format("tree.newick") == "newick"
        assert adapter.detect_format("tree.txt") == "newick"

    def test_detect_format_nexus(self):
        assert adapter.detect_format("tree.nex") == "nexus"
        assert adapter.detect_format("tree.nexus") == "nexus"

    def test_read_tree(self):
        """读取示例树文件。"""
        example = Path(__file__).resolve().parent.parent.parent / "data" / "examples" / "example.nwk"
        if not example.exists():
            pytest.skip("example.nwk not found")
        tree = adapter.read_tree(str(example))
        assert tree is not None
        assert tree.n_tips() > 0

    def test_tree_summary(self):
        example = Path(__file__).resolve().parent.parent.parent / "data" / "examples" / "example.nwk"
        if not example.exists():
            pytest.skip("example.nwk not found")
        tree = adapter.read_tree(str(example))
        info = adapter.tree_summary(tree)
        assert "n_tips" in info
        assert "n_internal" in info
        assert "is_binary" in info
        assert info["n_tips"] > 0


# ── CLI 字符串生成 ──────────────────────────────────────────────────────

class TestCLIBuilders:
    """测试等效 CLI 命令字符串生成。"""

    def test_build_cli_rates_times_basic(self):
        cli = adapter.build_cli_rates_times("tree.nwk", None, "geometric", False)
        assert 'openreltime rates-times' in cli
        assert '-i "tree.nwk"' in cli
        assert '--mean geometric' in cli
        assert '--normalize' not in cli
        assert '--outgroup' not in cli

    def test_build_cli_rates_times_with_options(self):
        cli = adapter.build_cli_rates_times(
            "tree.nwk", "Out1,Out2", "arithmetic", True
        )
        assert '--mean arithmetic' in cli
        assert '--normalize' in cli
        assert '--outgroup "Out1,Out2"' in cli

    def test_build_cli_calibrate(self):
        cli = adapter.build_cli_calibrate(
            "tree.nwk", "cals.tsv", "Out1", "bounds", 10000, None
        )
        assert 'openreltime calibrate' in cli
        assert '-c "cals.tsv"' in cli
        assert '--method bounds' in cli
        assert '--n-effective' not in cli  # bounds method

    def test_build_cli_calibrate_effective(self):
        cli = adapter.build_cli_calibrate(
            "tree.nwk", "cals.tsv", None, "effective", 5000, 42
        )
        assert '--method effective' in cli
        assert '--n-effective 5000' in cli
        assert '--seed 42' in cli

    def test_build_cli_ci(self):
        cli = adapter.build_cli_ci("result", 0.95, None)
        assert 'openreltime ci' in cli
        assert '--level 0.95' in cli

    def test_build_cli_ci_with_nsites(self):
        cli = adapter.build_cli_ci("result", 0.95, 1000)
        assert '--n-sites 1000' in cli

    def test_build_cli_corrtest(self):
        cli = adapter.build_cli_corrtest(
            "tree.nwk", None, 50, 42, None, 0.0
        )
        assert 'openreltime corrtest' in cli
        assert '--sister-resample 50' in cli
        assert '--seed 42' in cli

    def test_build_cli_ddbd(self):
        cli = adapter.build_cli_ddbd(
            "tree.nwk", None, 5, 1.0, "SSE"
        )
        assert 'openreltime ddbd' in cli
        assert '--anchor-node 5' in cli
        assert '--anchor-time 1.0' in cli
        assert '--measure SSE' in cli


# ── Calibration 构造 ────────────────────────────────────────────────────

class TestCalibrationFactory:
    """测试 Calibration 对象构造。"""

    def test_make_calibration_bounds_only(self):
        cal = adapter.make_calibration(
            node_id=10, min_bound=5.0, max_bound=10.0
        )
        assert cal.node_id == 10
        assert cal.min_bound == 5.0
        assert cal.max_bound == 10.0
        assert cal.density is None

    def test_make_calibration_with_density(self):
        cal = adapter.make_calibration(
            node_id=10,
            min_bound=5.0,
            max_bound=10.0,
            density="normal",
            density_params={"mean": 7.5, "sd": 1.0},
        )
        assert cal.density == "normal"
        assert cal.density_params["mean"] == 7.5

    def test_make_calibration_with_taxon_set(self):
        cal = adapter.make_calibration(
            taxon_set={"Homo_sapiens", "Pan_troglodytes"},
            min_bound=6.0,
            max_bound=8.0,
        )
        # 引擎侧 taxon_set 的具体容器（frozenset/tuple）可变，只断言集合内容
        assert set(cal.taxon_set or ()) == {"Homo_sapiens", "Pan_troglodytes"}
        assert cal.node_id is None


# ── Result 摘要 ──────────────────────────────────────────────────────────

class TestResultSummary:
    """测试 result_summary 函数（不依赖实际计算）。"""

    def test_summary_with_none(self):
        info = adapter.result_summary(None)
        assert info == {}

    def test_summary_with_mock_time_result(self):
        # 使用真实 TimeResult 对象而非 mock（因为它是 frozen dataclass）
        example = Path(__file__).resolve().parent.parent.parent / "data" / "examples" / "example.nwk"
        if not example.exists():
            pytest.skip("example.nwk not found")
        tree = adapter.read_tree(str(example))
        result = adapter.run_rrf_rates_times(tree, mean="geometric", normalize=False)
        info = adapter.result_summary(result)
        assert info["analysis"] == "rrf_rates_times"
        assert info["n_nodes"] > 0
        assert info["mean"] == "geometric"


# ── ddBD 绘图数据 ────────────────────────────────────────────────────────

class TestDDBDNodeDensity:
    """测试 ddbd_node_density（验证私有 API 隔离层）。"""

    def _load_tree_times_and_ddbd(self):
        example = Path(__file__).resolve().parent.parent.parent / "data" / "examples" / "example.nwk"
        if not example.exists():
            pytest.skip("example.nwk not found")
        tree = adapter.read_tree(str(example))
        times = adapter.run_rrf_times(tree)
        ddbd = adapter.run_ddbd(tree)
        return ddbd, times

    def test_ddbd_node_density_arrays(self):
        import numpy as np

        ddbd, times = self._load_tree_times_and_ddbd()
        node_times, grid, fitted = adapter.ddbd_node_density(ddbd, times)
        assert isinstance(node_times, np.ndarray)
        assert isinstance(grid, np.ndarray)
        assert isinstance(fitted, np.ndarray)
        assert node_times.ndim == 1 and node_times.size > 0
        assert grid.shape == fitted.shape
        assert (node_times >= 0).all()
        assert np.isfinite(fitted).all()

    def test_ddbd_node_density_empty_tree_raises(self):
        """没有内部节点时应报错，而不是静默返回空数组。"""
        from types import SimpleNamespace

        ddbd, _ = self._load_tree_times_and_ddbd()
        empty_times = SimpleNamespace(tree=SimpleNamespace(walk=lambda: []))
        with pytest.raises(ValueError):
            adapter.ddbd_node_density(ddbd, empty_times)
