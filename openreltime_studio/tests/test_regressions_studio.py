"""逻辑级回归测试：覆盖 ``openreltime_studio/`` 中不依赖 Qt 的部分。

这里检查的是若干条必须一直成立的界面契约。三类验证手段各有分工：

1. **真跑**：适配层的纯逻辑（校正目标解析、边界校验、branch-var 解析、
   CLI 字符串生成、日志收集器）与 :mod:`openreltime.cli` 的选项契约；
2. **静态断言**：用 :mod:`ast` 回读 Qt 源文件，确认某类写法已经不再出现在
   可执行代码里（只能证明写法，不能证明运行时行为，标注为 static）；
3. **显式 skip**：必须在真实 Qt 部件上才能验证的行为，指向
   ``openreltime_studio/tests/smoke_gui.py`` 里对应的检查。

运行::

    python3 -m pytest openreltime_studio/tests/test_regressions_studio.py -q
"""

from __future__ import annotations

import ast
import inspect
import logging
import shlex
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import openreltime as ort  # noqa: E402
from openreltime.cli import cli as ort_cli  # noqa: E402
from openreltime_studio import i18n
from openreltime_studio.adapters import openreltime_adapter as adapter  # noqa: E402

STUDIO = ROOT / "openreltime_studio"
EXAMPLE_TREE = ROOT / "data" / "examples" / "example.nwk"
EXAMPLE_CALS = ROOT / "data" / "examples" / "example_calibrations.tsv"

try:  # pragma: no cover - environment dependent
    import PySide6  # noqa: F401

    HAVE_QT = True
except ImportError:
    HAVE_QT = False

needs_qt = pytest.mark.skipif(
    not HAVE_QT,
    reason="需要 PySide6：本环境未安装 GUI extra，"
    "该行为只在 openreltime_studio/tests/smoke_gui.py 里做离屏验证",
)


# ── 静态回读工具 ────────────────────────────────────────────────────────

def _source(rel: str) -> str:
    return (STUDIO / rel).read_text(encoding="utf-8")


def _function_source(rel: str, name: str, *, code_only: bool = False) -> str:
    """Return the source of a function (nested methods included) for static assertions.

    ``code_only=True`` strips the leading docstring: a docstring may quote the
    very construct an assertion is checking for, so any "this construct is gone"
    assertion has to look at executable code only.
    """
    source = _source(rel)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            if not code_only:
                segment = ast.get_source_segment(source, node)
                assert segment
                return segment
            body = node.body
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                body = body[1:]
            return "\n".join(
                ast.get_source_segment(source, stmt) or "" for stmt in body
            )
    raise AssertionError(f"{rel}: 找不到函数 {name}（可能被改名即等于回归）")


def _class_source(rel: str, name: str) -> str:
    """返回某个类的源码片段（用于同名方法分散在多个 Worker 的情形）。"""
    source = _source(rel)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            segment = ast.get_source_segment(source, node)
            assert segment
            return segment
    raise AssertionError(f"{rel}: 找不到类 {name}")


@pytest.fixture(scope="module")
def example_tree():
    if not EXAMPLE_TREE.exists():
        pytest.skip("data/examples/example.nwk 不存在")
    return adapter.read_tree(str(EXAMPLE_TREE))


# ── Calibration targets: a taxon_set-only calibration is valid input ──────

class TestCalibrationTargetValidation:
    def test_taxon_set_only_calibration_is_valid(self, example_tree):
        cal = adapter.make_calibration(
            taxon_set={"Homo_sapiens", "Pan_troglodytes"}, min_bound=6.0, max_bound=8.5
        )
        assert cal.node_id is None
        assert adapter.calibration_target_problem(example_tree, cal) is None
        kept, problems = adapter.validate_calibrations(example_tree, [cal])
        assert kept == [cal] and problems == []

    def test_taxon_set_resolves_to_internal_node(self, example_tree):
        cal = adapter.make_calibration(
            taxon_set={"Homo_sapiens", "Pan_troglodytes"}, min_bound=6.0
        )
        node = adapter.resolve_calibration_target(example_tree, cal)
        assert node is not None
        assert not node.is_tip()
        assert node.node_id in {n.node_id for n in example_tree.walk()}

    def test_group_name_tokens_are_accepted(self, example_tree):
        """群名（自动从尖标签前缀检测）与引擎一样可以当 taxon_set 用。"""
        cal = adapter.make_calibration(taxon_set={"Homo", "Pan"}, min_bound=1.0)
        assert adapter.calibration_target_problem(example_tree, cal) is None

    def test_tip_node_id_is_rejected_with_reason(self, example_tree):
        tip_id = example_tree.tips()[0].node_id
        cal = adapter.make_calibration(node_id=tip_id, min_bound=1.0)
        for lang, needle in (("en", "tip"), ("zh", "尖")):
            i18n.set_language(lang, persist=False)
            problem = adapter.calibration_target_problem(example_tree, cal)
            assert problem is not None and needle in problem

    def test_unknown_node_id_is_rejected_without_minus_one(self, example_tree):
        """旧实现在这里报 id ``-1``；现在必须给出可读原因。"""
        cal = adapter.make_calibration(node_id=999_999, min_bound=1.0)
        _kept, problems = adapter.validate_calibrations(example_tree, [cal])
        assert len(problems) == 1
        assert "999999" in problems[0]
        assert "-1" not in problems[0]

    def test_targetless_calibration_is_rejected(self, example_tree):
        cal = adapter.make_calibration(min_bound=1.0)
        problem = adapter.calibration_target_problem(example_tree, cal)
        assert problem is not None and "node_id" in problem

    def test_unknown_taxon_names_are_rejected(self, example_tree):
        cal = adapter.make_calibration(taxon_set={"Not_a_taxon_xyz"}, min_bound=1.0)
        problem = adapter.calibration_target_problem(example_tree, cal)
        assert problem is not None and "Not_a_taxon_xyz" in problem

    def test_single_tip_taxon_set_is_rejected(self, example_tree):
        cal = adapter.make_calibration(taxon_set={"Homo_sapiens"}, min_bound=1.0)
        problem = adapter.calibration_target_problem(example_tree, cal)
        assert problem is not None

    @pytest.mark.skipif(not EXAMPLE_CALS.exists(), reason="示例校正文件不存在")
    def test_example_calibration_file_keeps_every_row(self, example_tree):
        """示例文件三行全是 taxon_set 型：GUI 载入时一行都不该被删。"""
        calibrations = adapter.load_calibrations(str(EXAMPLE_CALS))
        assert len(calibrations) == 3
        kept, problems = adapter.validate_calibrations(example_tree, calibrations)
        assert problems == []
        assert len(kept) == 3

    def test_main_window_uses_the_shared_validator(self):
        """静态：载入时不再用 ``node_id is None`` 判非法。"""
        body = _function_source(
            "windows/main_window.py", "load_calibrations_file", code_only=True
        )
        assert "adapter.validate_calibrations" in body
        assert "else -1" not in body
        assert "find_node_by_id" not in body
        marks = _function_source("windows/main_window.py", "_on_calibrations_changed")
        assert "resolve_calibration_target" in marks


# ── Calibration bounds: 0.0 is a value, only None means "not set" ─────────

class TestBoundDisplayAndValidation:
    def test_zero_bound_is_displayed_as_zero(self):
        assert adapter.format_bound(0.0) == "0.0"
        assert adapter.format_bound(0) == "0"
        assert adapter.format_bound(None) == "-"
        assert adapter.format_bound(1.5) == "1.5"

    def test_max_bound_zero_is_rejected(self):
        """max=0 会让求解器把全树年龄乘成 0（实测 f=0.0）。"""
        problem = adapter.bound_error(None, 0.0)
        assert problem is not None and "0" in problem

    def test_min_bound_zero_is_allowed(self):
        assert adapter.bound_error(0.0, 5.0) is None
        assert adapter.bound_error(0.0, None) is None

    def test_both_bounds_zero_is_rejected(self):
        assert adapter.bound_error(0.0, 0.0) is not None

    def test_empty_and_reversed_bounds(self):
        assert adapter.bound_error(None, None) is not None
        assert adapter.bound_error(5.0, 1.0) is not None
        assert adapter.bound_error(1.0, 5.0) is None

    def test_density_only_calibration_needs_effective_method(self):
        assert adapter.bound_error(None, None, "uniform", method="bounds") is not None
        assert adapter.bound_error(None, None, "uniform", method="effective") is None

    def test_non_finite_and_negative_bounds(self):
        assert adapter.bound_error(float("nan"), None) is not None
        assert adapter.bound_error(float("inf"), None) is not None
        assert adapter.bound_error(-1.0, None) is not None

    @pytest.mark.skipif(not HAVE_QT, reason="需要 PySide6 才能构造 QDoubleSpinBox")
    def test_editor_spin_minimum_is_positive(self):  # pragma: no cover - 需 Qt
        from openreltime_studio.widgets.calibration_editor import CalibrationEditor

        editor = CalibrationEditor()
        assert editor.min_spin.minimum() > 0
        assert editor.max_spin.minimum() > 0

    def test_editor_no_longer_uses_truthiness_for_bounds(self):
        """静态：表格显示改用 ``is None``，旋转框下界改为正常量。"""
        body = _function_source(
            "widgets/calibration_editor.py", "_refresh_table", code_only=True
        )
        assert "adapter.format_bound" in body
        assert "if cal.min_bound else" not in body
        assert "if cal.max_bound else" not in body
        source = _source("widgets/calibration_editor.py")
        assert "setRange(_MIN_BOUND" in source
        assert "if self.min_check.isChecked() else None" in source
        add = _function_source("widgets/calibration_editor.py", "_on_add_calibration")
        assert "adapter.bound_error" in add
        run = _function_source("windows/main_window.py", "run_calibrate")
        assert "adapter.bound_error" in run


# ── Equivalent CLI script: one shared prefix, a replayable pipeline ───────

def _flags(argv: list[str], name: str) -> list[str]:
    return [argv[i + 1] for i, tok in enumerate(argv) if tok == name]


class TestCliScriptContract:
    def test_single_output_prefix_constant_is_the_default(self):
        for builder, args in [
            (adapter.build_cli_rates_times, ("tree.nwk", None, "geometric", False)),
            (adapter.build_cli_calibrate, ("tree.nwk", "c.tsv", None, "bounds", 1, None)),
            (adapter.build_cli_ci, (adapter.OUTPUT_PREFIX, 0.95, None)),
            (adapter.build_cli_corrtest, ("tree.nwk", None, 0, None, None, 0.0)),
            (adapter.build_cli_ddbd, ("tree.nwk", None, None, 1.0, "SSE")),
        ]:
            command = builder(*args)
            assert f"-o {adapter.OUTPUT_PREFIX}" in command, builder.__name__
        assert adapter.OUTPUT_PREFIX == "openreltime_result"

    def test_ci_reads_the_prefix_the_calibrate_step_writes(self):
        calibrate = adapter.build_cli_calibrate(
            "/abs/tree.nwk", "calibrations.tsv", None, "bounds", 10000, None
        )
        ci = adapter.build_cli_ci(adapter.OUTPUT_PREFIX, 0.95, None)
        written = _flags(shlex.split(calibrate), "-o")
        read = _flags(shlex.split(ci), "-c")
        assert written == read == [adapter.OUTPUT_PREFIX]

    def test_input_settings_are_forwarded_to_the_reader(self):
        calibrate = adapter.build_cli_calibrate(
            "/abs/tree.nwk",
            "calibrations.tsv",
            "Out1,Out2",
            "effective",
            5000,
            42,
            input_fmt="nexus",
            resolve_polytomy="random",
            outgroup_check="warn",
        )
        argv = shlex.split(calibrate)
        assert _flags(argv, "--fmt") == ["nexus"]
        assert _flags(argv, "--resolve") == ["random"]
        assert _flags(argv, "--outgroup-check") == ["warn"]
        assert _flags(argv, "--outgroup") == ["Out1,Out2"]
        assert _flags(argv, "--n-effective") == ["5000"]
        assert _flags(argv, "--seed") == ["42"]

    def test_ci_forwards_site_count_and_branch_var(self):
        argv = shlex.split(
            adapter.build_cli_ci(
                adapter.OUTPUT_PREFIX, 0.99, 1200, branch_var="/abs/var.tsv"
            )
        )
        assert _flags(argv, "--n-sites") == ["1200"]
        assert _flags(argv, "--branch-var") == ["/abs/var.tsv"]
        assert _flags(argv, "--level") == ["0.99"]
        argv = shlex.split(adapter.build_cli_ci(adapter.OUTPUT_PREFIX, 0.95, None))
        assert "--n-sites" not in argv
        assert "--branch-var" not in argv

    def test_ddbd_forwards_sampling_fraction(self):
        argv = shlex.split(
            adapter.build_cli_ddbd(
                "/abs/tree.nwk", None, None, 1.0, "KL", sampling_frac=0.5
            )
        )
        assert _flags(argv, "--sampling-frac") == ["0.5"]
        assert _flags(argv, "--measure") == ["KL"]

    def test_pipeline_order_puts_calibrate_before_ci(self):
        commands = {
            "ci": adapter.build_cli_ci(adapter.OUTPUT_PREFIX, 0.95, None),
            "corrtest": adapter.build_cli_corrtest("t.nwk", None, 0, None, None, 0.0),
            "rates-times": adapter.build_cli_rates_times("t.nwk", None, "geometric", False),
            "ddbd": adapter.build_cli_ddbd("t.nwk", None, None, 1.0, "SSE"),
            "calibrate": adapter.build_cli_calibrate(
                "t.nwk", "calibrations.tsv", None, "bounds", 1, None
            ),
        }
        pipeline = adapter.cli_pipeline(commands)
        stages = [shlex.split(cmd)[1] for cmd in pipeline]
        assert stages == list(adapter.CLI_STAGES)
        assert stages.index("calibrate") < stages.index("ci")

    def test_script_is_self_locating_and_fails_fast(self):
        script = adapter.build_cli_script(
            [
                adapter.build_cli_calibrate(
                    "/abs/tree.nwk", "calibrations.tsv", None, "bounds", 1, None
                ),
                adapter.build_cli_ci(adapter.OUTPUT_PREFIX, 0.95, None),
            ]
        )
        lines = script.splitlines()
        assert lines[0] == "#!/usr/bin/env bash"
        assert "set -euo pipefail" in script
        assert 'cd "$(dirname "$0")"' in script
        assert 'openreltime ci -c openreltime_result' in script
        # 前一步 calibrate 的 -o 必须就是 ci 的 -c，否则重放必失败
        steps = [shlex.split(ln) for ln in lines if ln.startswith("openreltime")]
        assert _flags(steps[0], "-o") == _flags(steps[1], "-c")

    @pytest.mark.parametrize(
        "builder,args",
        [
            (
                adapter.build_cli_rates_times,
                (
                    "/abs/tree.nwk", "Out1", "arithmetic", True,
                ),
            ),
            (
                adapter.build_cli_calibrate,
                ("/abs/tree.nwk", "calibrations.tsv", "Out1", "effective", 3, 7),
            ),
            (adapter.build_cli_ci, (adapter.OUTPUT_PREFIX, 0.9, 1000)),
            (
                adapter.build_cli_corrtest,
                ("/abs/tree.nwk", "Out1", 100, 7, 12, 1.85),
            ),
            (adapter.build_cli_ddbd, ("/abs/tree.nwk", "Out1", 12, 1.85, "SSE")),
        ],
    )
    def test_generated_command_matches_the_cli_contract(self, builder, args):
        """每个选项都得是 CLI 真认识的选项，Choice 值必须合法。"""
        extras = {
            "input_fmt": "nexus",
            "resolve_polytomy": "random",
            "outgroup_check": "warn",
            "branch_var": "/abs/var.tsv",
            "sampling_frac": 0.5,
        }
        if builder is adapter.build_cli_ci:
            command = builder(*args)  # ci 不读树，无输入侧选项
        else:
            accepted = set(inspect.signature(builder).parameters)
            command = builder(
                *args, **{k: v for k, v in extras.items() if k in accepted}
            )
        argv = shlex.split(command)
        assert argv[0] == "openreltime"
        sub = argv[1]
        assert sub in ort_cli.commands, f"未知子命令 {sub}"
        params = ort_cli.commands[sub].params
        known: set[str] = set()
        choices: dict[str, set[str]] = {}
        for param in params:
            for opt in param.opts:
                known.add(opt)
                typer = getattr(param, "type", None)
                if hasattr(typer, "choices"):
                    choices[opt] = set(typer.choices)
        required = [
            p for p in params if getattr(p, "required", False)
        ]
        for param in required:
            assert any(opt in argv for opt in param.opts), (
                f"{sub} 缺少必需选项 {param.opts}"
            )
        for i, token in enumerate(argv):
            if not token.startswith("-"):
                continue
            assert token in known, f"{sub} 不认识选项 {token}"
            if token in choices and i + 1 < len(argv):
                assert argv[i + 1] in choices[token], (
                    f"{sub} {token} 的取值 {argv[i + 1]!r} 不在 "
                    f"{sorted(choices[token])}"
                )

    def test_main_window_no_longer_hardcodes_two_different_prefixes(self):
        """静态：导出与 CLI 面板都只能引用共享常量。"""
        source = _source("windows/main_window.py")
        assert "out_dir / adapter.OUTPUT_PREFIX" in source
        assert 'out_dir / "openreltime_result"' not in source
        for name in ("_update_cli_calibrate", "_update_cli_ci"):
            assert "adapter.OUTPUT_PREFIX" in _function_source(
                "windows/main_window.py", name
            )
        assert "adapter.CALIBRATIONS_FILENAME" in _function_source(
            "windows/main_window.py", "_update_cli_calibrate"
        )
        run = _function_source("windows/main_window.py", "run_calibrate")
        assert "provenance=self._calibrate_provenance()" in run
        prov = _function_source("windows/main_window.py", "_calibrate_provenance")
        for key in ("tree_file", "calibrations_file", "outgroup", "input_fmt",
                    "resolve_polytomy", "outgroup_check"):
            assert f'"{key}"' in prov, f"provenance 未记录 {key}"
        script = _function_source("windows/main_window.py", "export_results")
        assert "adapter.build_cli_script" in script
        worker = _source("workers/analysis_workers.py")
        assert "provenance=self.provenance" in worker


# ── Cancellation: a cancelled calibration must never be applied ───────────

class TestCancellationIsHonoured:
    def test_worker_exposes_the_flag_set_by_cancel(self):
        """静态：``cancel()`` 置旗标，并把旗标暴露给 GUI 层。"""
        source = _source("workers/analysis_workers.py")
        body = _function_source("workers/analysis_workers.py", "cancel")
        assert "self._cancelled = True" in body
        assert "def cancel_requested" in source
        assert "return self._cancelled" in source
        assert "provenance: Optional[dict] = None" in source

    def test_finished_handler_discards_cancelled_result(self):
        body = _function_source("windows/main_window.py", "_on_calibrate_finished")
        assert "cancel_requested" in body
        assert "self.calibrated_result = result" in body
        # 取消判断必须在赋值之前 return
        assert body.index("return") < body.index("self.calibrated_result = result")

    @pytest.mark.skipif(not HAVE_QT, reason="需要 PySide6 才能起 QThread 跑取消流程")
    def test_cancel_during_bounds_run_is_dropped(self):  # pragma: no cover - 需 Qt
        pytest.skip("见 smoke_gui.py 的「4c. 取消：结果不得被应用」")


# ── Tree format: the combo value decides how the tree is parsed ───────────

class TestFormatComboBoxIsWired:
    def test_read_tree_forwards_fmt(self, tmp_path):
        """真跑：nexus 内容的文件在无后缀路径下也只有 fmt=nexus 才读得进。"""
        body = EXAMPLE_TREE if EXAMPLE_TREE.exists() else None
        if body is None:  # pragma: no cover - 仓库自带示例
            pytest.skip("data/examples/example.nwk 不存在")
        target = tmp_path / "tree_noext.txt"
        target.write_text(
            "#NEXUS\nbegin trees;\n  tree t1 = "
            + Path(body).read_text(encoding="utf-8").strip()
            + "\nend;\n",
            encoding="utf-8",
        )
        assert adapter.detect_format(target) == "newick"
        with pytest.raises(Exception):
            adapter.read_tree(str(target), fmt="newick")
        tree = adapter.read_tree(str(target), fmt="nexus")
        assert tree.n_tips() > 0

    def test_reader_accepts_outgroup_check(self):
        source = _source("adapters/openreltime_adapter.py")
        assert "outgroup_check=outgroup_check" in source
        worker = _source("workers/analysis_workers.py")
        assert "outgroup_check=self.outgroup_check" in worker

    def test_window_reads_the_combo_instead_of_only_writing_it(self):
        """静态：`setCurrentText` 之后必须真的有人读取该控件，否则它是死控件。"""
        assert "return self.fmt_combo.currentText()" in _source(
            "windows/main_window.py"
        )
        read = _function_source("windows/main_window.py", "_read_tree_file")
        assert "fmt=self.input_fmt" in read
        assert "outgroup_check=self.outgroup_check" in read
        assert "resolve_polytomy=self.resolve_polytomy" in read
        changed = _function_source("windows/main_window.py", "_on_format_changed")
        assert "_read_tree_file" in changed
        assert 'self.fmt_combo.currentTextChanged.connect(self._on_format_changed)' in (
            _source("windows/main_window.py")
        )


# ── CI variance inputs: forwarded end to end, never silently degraded ─────

class TestCIVarianceWiring:
    def test_branch_var_table_is_parsed(self, tmp_path):
        path = tmp_path / "var.tsv"
        path.write_text("node_id\tvar\n9\t0.004\n10\t0.02\n", encoding="utf-8")
        assert adapter.load_branch_variances(path) == {9: 0.004, 10: 0.02}

    def test_branch_var_table_without_header_is_reported(self, tmp_path):
        path = tmp_path / "bad.tsv"
        path.write_text("9\t0.004\n", encoding="utf-8")
        with pytest.raises(ValueError) as exc:
            adapter.load_branch_variances(path)
        assert "node_id" in str(exc.value)

    def test_worker_forwards_every_variance_input(self):
        worker = _class_source("workers/analysis_workers.py", "CIWorker")
        assert "branch_var=self.branch_var" in worker
        assert "seq_length=self.seq_length" in worker
        assert "branch_var: Optional[dict[int, float]] = None" in worker
        ci = _function_source("windows/main_window.py", "run_ci")
        assert "branch_var=branch_var" in ci
        assert "adapter.load_branch_variances" in ci
        assert "n_sites=self.ci_params.n_sites" in ci

    @pytest.mark.skipif(not HAVE_QT, reason="需要 PySide6 才能读 QSpinBox/QLabel 状态")
    def test_panel_fallback_note_and_positive_minimum(self):  # pragma: no cover - 需 Qt
        from openreltime_studio.widgets.param_panels import CIParamsWidget

        panel = CIParamsWidget()
        assert panel.n_sites is None
        assert panel.fallback_note.isVisibleTo(panel)
        assert panel.n_sites_spin.minimum() >= 1
        panel.n_sites_check.setChecked(True)
        assert panel.n_sites == panel.n_sites_spin.value()
        assert panel.n_sites > 0
        assert not panel.fallback_note.isVisibleTo(panel)


# ── Calibration marks: they must survive a canvas redraw ──────────────────

class TestCalibrationMarksSurviveRedraw:
    def test_plot_timetree_no_longer_clears_marks(self):
        body = _function_source(
            "widgets/tree_canvas.py", "plot_timetree", code_only=True
        )
        assert "_calibration_marks.clear()" not in body
        assert "self._draw_marks()" in body

    def test_set_marks_no_longer_replots_before_assigning(self):
        body = _function_source(
            "widgets/tree_canvas.py", "set_calibration_marks", code_only=True
        )
        assert "self._calibration_marks =" in body
        assert "plot_timetree" not in body
        assert "_replot_current" not in body
        assert "_redraw_marks" in body

    def test_marks_are_drawn_idempotently(self):
        """静态：重画前先摘掉旧 Artist，避免重复添加堆叠。"""
        body = _function_source("widgets/tree_canvas.py", "_draw_marks")
        assert "self._mark_artists" in body
        assert "remove()" in body

    @pytest.mark.skipif(not HAVE_QT, reason="需要 PySide6 + matplotlib Qt 画布")
    def test_marks_visible_after_interactive_edit(self):  # pragma: no cover - 需 Qt
        pytest.skip("见 smoke_gui.py 的「4b. 交互增删校正点：标记必须同步」")


# ── Export: RateResult must be imported, not referenced from thin air ─────

class TestExportHandlesRateResult:
    def test_rate_result_is_imported_in_the_adapter(self):
        source = _source("adapters/openreltime_adapter.py")
        tree = ast.parse(source)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        assert "RateResult" in imported
        assert adapter.RateResult is ort.RateResult

    @pytest.mark.skipif(not HAVE_QT, reason="需要 PySide6 才能走 GUI 导出入口")
    def test_gui_has_no_rate_worker(self):  # pragma: no cover - 需 Qt
        pytest.skip("GUI 目前没有 rrf_rates Worker；此处只覆盖适配层分支")

    def test_export_result_writes_a_rate_result(self, example_tree, tmp_path):
        """真跑：这条 isinstance 分支曾经因 NameError 走不到。"""
        result = ort.rrf_rates(example_tree)
        assert isinstance(result, ort.RateResult)
        written = adapter.export_result(result, tmp_path / "prefixed")
        assert written
        assert all(path.exists() for path in written)
        assert any(path.name == "prefixed_rates.csv" for path in written)

    def test_export_result_still_rejects_unknown_types(self):
        with pytest.raises(TypeError):
            adapter.export_result(object(), "whatever")


# ── Log collector: concurrent emit and read must not corrupt state ────────

class TestLogCollectorIsThreadSafe:
    def _emit(self, collector, n: int, tag: str) -> None:
        for i in range(n):
            collector.emit(logging.LogRecord(
                "openreltime", logging.WARNING, "f.py", 1,
                f"{tag}-{i}", None, None,
            ))

    def test_records_is_a_snapshot_not_the_live_list(self):
        from openreltime_studio.main import _LogCollector

        collector = _LogCollector()
        self._emit(collector, 2, "x")
        snapshot = collector.records
        snapshot.append("bogus")
        assert collector.count() == 2
        assert "bogus" not in collector.records

    def test_capacity_trims_oldest(self):
        from openreltime_studio.main import _LogCollector

        collector = _LogCollector(capacity=50)
        self._emit(collector, 120, "y")
        assert collector.count() == 50
        assert collector.records[0].endswith("y-70")

    def test_concurrent_emit_and_read_does_not_lose_or_crash(self):
        from openreltime_studio.main import _LogCollector

        collector = _LogCollector(capacity=10_000)
        errors: list[BaseException] = []
        stop = threading.Event()

        def reader() -> None:
            try:
                while not stop.is_set():
                    joined = "\n".join(collector.records)
                    assert "\x00" not in joined
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        readers = [threading.Thread(target=reader) for _ in range(4)]
        for thread in readers:
            thread.start()
        writers = [
            threading.Thread(target=self._emit, args=(collector, 250, f"w{k}"))
            for k in range(8)
        ]
        for thread in writers:
            thread.start()
        for thread in writers:
            thread.join()
        stop.set()
        for thread in readers:
            thread.join()
        assert errors == []
        assert collector.count() == 8 * 250

    def test_clear_works(self):
        from openreltime_studio.main import _LogCollector

        collector = _LogCollector()
        self._emit(collector, 3, "z")
        collector.clear()
        assert collector.records == []


# ── Unwired leftovers: dead helpers must not come back ────────────────────

def test_no_dead_calibration_mark_helper_left():
    """Static: the canvas keeps no whole-tree replot fallback for its marks.

    A mark refresh must go through ``_redraw_marks`` alone; a whole-tree replot
    helper such as ``_replot_current`` / ``_last_use_rates`` must not come back.
    """
    source = _source("widgets/tree_canvas.py")
    assert "_replot_current" not in source
    assert "_last_use_rates" not in source
