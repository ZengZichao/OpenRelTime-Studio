"""离屏 GUI 冒烟测试：加载示例树 → RRF → 校正 → ddBD → CI，逐阶段截图。

用法（需安装 gui 依赖）::

    QT_QPA_PLATFORM=offscreen python openreltime_studio/tests/smoke_gui.py

截图输出到项目根目录 ``.smoke_out/``，用于人工检查界面细节与响应式状态。

除了截图，脚本还对每个阶段做硬断言，其中刻意覆盖容易被"异步路径"掩盖
的界面缺陷：校正点标记在**交互增删**后必须留在画布上、
点过"取消"的校正结果不得被应用、格式下拉框的取值必须真正
决定读树方式。
"""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")

from matplotlib.colors import to_rgba  # noqa: E402
from PySide6.QtCore import QThread  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from openreltime_studio.adapters import openreltime_adapter as adapter  # noqa: E402
from openreltime_studio import themes  # noqa: E402
from openreltime_studio.windows.main_window import MainWindow  # noqa: E402

WARNINGS: list[str] = []

_MARK_FILL_RGB = to_rgba("#f5c518")


def drawn_marks(win) -> int:
    """画布上实际画出的校正点散点数（不是内部集合的大小）。"""
    return sum(
        1
        for line in win.canvas.ax.get_lines()
        if line.get_marker() == "o"
        and to_rgba(line.get_mfc()) == _MARK_FILL_RGB
    )



def _patch_dialogs():
    """离屏环境下模态对话框无法交互：替换为记录型桩。"""
    def _ok(*args, **kwargs):
        return QMessageBox.StandardButton.Ok

    def _warn(*args, **kwargs):
        WARNINGS.append(str(kwargs.get("text", args[2] if len(args) > 2 else "")))
        return QMessageBox.StandardButton.Ok

    QMessageBox.information = staticmethod(_ok)
    QMessageBox.critical = staticmethod(_ok)
    QMessageBox.about = staticmethod(lambda *a, **k: None)
    QMessageBox.warning = staticmethod(_warn)
    QMessageBox.question = staticmethod(_ok)


def wait_for(cond, timeout_ms: int = 30000) -> bool:
    app = QApplication.instance()
    waited = 0
    while waited < timeout_ms:
        app.processEvents()
        if cond():
            return True
        QThread.msleep(20)
        waited += 20
    return False


def idle(win):
    return win.tree is not None and not win._active_workers


def check(label: str, cond: bool):
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
    if not cond:
        raise AssertionError(label)


def main() -> int:
    _patch_dialogs()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(themes.stylesheet())

    win = MainWindow()
    win.resize(1280, 800)
    win.show()

    out = ROOT / ".smoke_out"
    out.mkdir(exist_ok=True)

    def grab(name: str):
        app.processEvents()
        win.grab().save(str(out / name))
        print(f"  screenshot: {name}")

    example = ROOT / "data" / "examples" / "example.nwk"

    print("== 1. 初始状态 ==")
    grab("01_initial.png")
    check("运行按钮初始禁用", not win.btn_run_rrf.isEnabled())
    check("导出按钮初始禁用", not win.btn_export.isEnabled())
    check("打开按钮初始可用", win.btn_open.isEnabled())

    print("== 2. 加载示例树 ==")
    win.tree_path = str(example)
    win.path_edit.setText(str(example))
    win._read_tree_file(str(example))
    check("树读取完成", wait_for(lambda: not win._active_workers))
    grab("02_tree_loaded.png")
    check("RRF 按钮已启用", win.btn_run_rrf.isEnabled())
    check("校正按钮仍禁用（需先 RRF）", not win.btn_run_calibrate.isEnabled())
    check("导出仍禁用（无结果）", not win.btn_export.isEnabled())

    print("== 3. 运行 RRF ==")
    win.run_rrf()
    check("RRF 完成", wait_for(lambda: win.rrf_result is not None))
    check("运行结束恢复空闲", wait_for(lambda: not win._active_workers))
    grab("03_rrf_done.png")
    check("校正按钮已启用", win.btn_run_calibrate.isEnabled())
    check("导出已启用", win.btn_export.isEnabled())
    check("表格有数据", win.node_table.rowCount() > 0)
    check("CLI 已更新", not win.cli_text.toPlainText().startswith("#"))

    print("== 4. 添加校正点并校正 ==")
    node_id = sorted(win.canvas._node_coords)[0]
    win._on_node_clicked(node_id)
    check("点击节点切换到校正 Tab", win.analysis_tabs.currentWidget() is win._cal_tab)
    win.calibration_editor.min_check.setChecked(True)
    win.calibration_editor.max_check.setChecked(True)
    win.calibration_editor.min_spin.setValue(0.5)
    win.calibration_editor.max_spin.setValue(2.0)
    win.calibration_editor.btn_add.click()
    check("校正点已添加", len(win.calibration_editor.calibrations) == 1)

    # 同节点重复添加应替换而非重复
    win._on_node_clicked(node_id)
    win.calibration_editor.min_check.setChecked(True)
    win.calibration_editor.max_check.setChecked(True)
    win.calibration_editor.min_spin.setValue(0.8)
    win.calibration_editor.max_spin.setValue(2.5)
    win.calibration_editor.btn_add.click()
    check("同节点重复添加被替换", len(win.calibration_editor.calibrations) == 1)

    # min > max 应被拦截
    win._on_node_clicked(node_id)
    win.calibration_editor.min_check.setChecked(True)
    win.calibration_editor.max_check.setChecked(True)
    win.calibration_editor.min_spin.setValue(5.0)
    win.calibration_editor.max_spin.setValue(1.0)
    win.calibration_editor.btn_add.click()
    check("min>max 被校验拦截", len(win.calibration_editor.calibrations) == 1)
    check("出现告警弹窗", len(WARNINGS) >= 1)

    # Canvas hit-testing: querying a node's own data coordinates must resolve
    # back to that same node.
    hit_id, hit_d = win.canvas._nearest_node_px(
        *win.canvas._node_coords[node_id]
    )
    check("像素命中判定可命中节点", hit_id == node_id and hit_d <= 10.0)

    win.run_calibrate()
    check("校正完成", wait_for(lambda: win.calibrated_result is not None))
    grab("04_calibrated.png")
    n_cals = len(win.calibrated_result.calibrations)
    check("画布上有校正标记", len(win.canvas.calibration_marks) >= 1)
    check("标记集合与结果一致",
          win.canvas.calibration_marks
          == {c.node_id for c in win.calibrated_result.calibrations})
    check("标记确实画在图上", drawn_marks(win) == n_cals)
    check("CI 按钮已启用", win.btn_run_ci.isEnabled())

    print("== 4b. 交互增删校正点：标记必须同步 ==")
    other = next(i for i in sorted(win.canvas._node_coords) if i != node_id)
    win._on_node_clicked(other)
    win.calibration_editor.min_check.setChecked(True)
    win.calibration_editor.max_check.setChecked(True)
    win.calibration_editor.min_spin.setValue(0.4)
    win.calibration_editor.max_spin.setValue(0.7)
    win.calibration_editor.btn_add.click()
    check("已添加第二个校正点", len(win.calibration_editor.calibrations) == 2)
    check("标记集合同步新增", win.canvas.calibration_marks == {node_id, other})
    check("画布画出两个标记", drawn_marks(win) == 2)

    win.calibration_editor.remove_calibration(0)
    check("标记集合同步删除", win.canvas.calibration_marks == {other})
    check("画布标记数随删除更新", drawn_marks(win) == 1)
    check("标记属性与画布一致",
          win.canvas.calibration_marks == {other})

    # 重新加回第一个校正点，后续 CI 步骤沿用两个校正
    win._on_node_clicked(node_id)
    win.calibration_editor.min_check.setChecked(True)
    win.calibration_editor.max_check.setChecked(True)
    win.calibration_editor.min_spin.setValue(0.8)
    win.calibration_editor.max_spin.setValue(2.5)
    win.calibration_editor.btn_add.click()
    check("恢复两个校正点", len(win.calibration_editor.calibrations) == 2)
    check("标记集合恢复", win.canvas.calibration_marks == {node_id, other})

    print("== 4c. 取消：结果不得被应用 ==")
    # 前面几步已经成功校正过：先清空，才能证明“被取消的这一次”没有落结果
    win.calibrated_result = None
    win.run_calibrate()
    worker = win._cal_worker
    check("取消旗标初始未置位", worker is not None and not worker.cancel_requested)
    # 不跑事件循环，因此 done 信号仍在队列里：等价于用户在对话框点「取消」
    worker.cancel()
    check("取消旗标已置位", worker.cancel_requested)
    check("bounds 计算自行结束", wait_for(lambda: not win._active_workers))
    check("取消后校正结果被丢弃", win.calibrated_result is None)
    win.run_calibrate()
    check("重新校正完成", wait_for(lambda: win.calibrated_result is not None))
    check("重跑后标记仍在", drawn_marks(win) == len(win.calibrated_result.calibrations))

    print("== 5. ddBD（已有 RRF 结果）==")
    win.run_ddbd()
    check("ddBD 完成", wait_for(lambda: win.ddbd_result is not None))
    grab("05_ddbd.png")

    print("== 6. CI（含 vS 回退提示） ==")
    check("未勾选时 n_sites 为空", win.ci_params.n_sites is None)
    check(
        "未勾选时显示回退提示",
        not win.ci_params.fallback_note.isHidden()
        and win.ci_params.fallback_note.text().count("vS(b)=0") == 1,
    )
    win.run_ci()
    check("CI 完成", wait_for(lambda: win.ci_result is not None))
    check("零方差来源被写明", "rate-heterogeneity" in win.table_summary.text())
    grab("06_ci.png")
    check("CI 表格有数据", win.node_table.rowCount() > 0)

    win.ci_params.n_sites_check.setChecked(True)
    check("勾选后位点数下界为正", win.ci_params.n_sites_spin.minimum() >= 1)
    win.ci_params.n_sites_spin.setValue(1200)
    check("勾选后位点数生效", win.ci_params.n_sites == 1200)
    check("勾选后回退提示消失", win.ci_params.fallback_note.isHidden())
    win.run_ci()
    check("指定位点数后 CI 完成", wait_for(lambda: "L=1200" in win.table_summary.text()))
    check(
        "CLI 带上位点数",
        "--n-sites 1200" in win.cli_text.toPlainText(),
    )

    print("== 7. 忙碌状态（CorrTest 运行中）==")
    win.run_corrtest()
    check("CorrTest 完成", wait_for(lambda: win.corrtest_result is not None))
    check("忙碌结束后按钮恢复", win.btn_open.isEnabled() and win.btn_run_rrf.isEnabled())

    print("== 8. 小窗口（响应式布局）==")
    win.resize(940, 620)
    grab("07_small_window.png")

    print("== 9. 等效 CLI 面板：整条流水线可重放 ==")
    lines = [ln for ln in win.cli_text.toPlainText().splitlines() if ln.strip()]
    stages = [shlex.split(ln)[1] for ln in lines]
    check("面板按流水线顺序列出全部已运行阶段",
          stages == ["rates-times", "calibrate", "ci", "corrtest", "ddbd"])
    steps = {stage: shlex.split(ln) for stage, ln in zip(stages, lines, strict=True)}

    def flag(argv: list[str], name: str) -> str | None:
        return argv[argv.index(name) + 1] if name in argv else None

    check("calibrate 与 ci 用同一输出前缀",
          flag(steps["calibrate"], "-o") == flag(steps["ci"], "-c")
          == flag(steps["ci"], "-o"))
    check("输出前缀即导出前缀", flag(steps["calibrate"], "-o") == "openreltime_result")
    check("calibrate 在校前一步于 ci", stages.index("calibrate") < stages.index("ci"))
    check("校正文件走导出目录里的相对名",
          flag(steps["calibrate"], "-c") == "calibrations.tsv")
    check("树路径为绝对路径",
          Path(flag(steps["calibrate"], "-i")).is_absolute()
          and Path(flag(steps["calibrate"], "-i")).exists())
    for stage in ("rates-times", "calibrate", "corrtest", "ddbd"):
        check(f"{stage} 带上读树设置",
              flag(steps[stage], "--fmt") == win.input_fmt
              and flag(steps[stage], "--resolve") == win.resolve_polytomy
              and flag(steps[stage], "--outgroup-check") == win.outgroup_check)

    print("== 10. 格式下拉框真正生效 ==")
    nexus_txt = out / "tree_noext.txt"
    nexus_txt.write_text(
        "#NEXUS\nbegin trees;\n  tree t1 = " + example.read_text().strip() + "\nend;\n"
    )
    win.tree = None
    win.tree_path = str(nexus_txt)
    win.path_edit.setText(str(nexus_txt))
    check("检测到的格式只有 .nex/.nexus 才认 nexus",
          adapter.detect_format(nexus_txt) == "newick")
    win._read_tree_file(str(nexus_txt))
    check("首次读取结束", wait_for(lambda: not win._active_workers))
    check("按 newick 读无后缀 NEXUS 失败", win.tree is None)
    win.fmt_combo.setCurrentText("nexus")
    check("手动改格式后不再被扩展名覆盖", win.input_fmt == "nexus")
    check("改格式触发按新格式重读", wait_for(lambda: win.tree is not None))
    check("重读已结束", wait_for(lambda: not win._active_workers))
    check("新树已载入", win.tree.n_tips() == 274)
    grab("09_nexus_noext.png")

    print("== 11. 重新加载同一树（结果应失效）==")
    win.tree = None
    win.path_edit.setText(str(example))
    # choose_file 会按扩展名重新检测格式（成功读取后 _fmt_manual 已复位）；
    # 这里绕过了文件对话框，故手动改回且不触发重读
    win.fmt_combo.blockSignals(True)
    win.fmt_combo.setCurrentText(adapter.detect_format(example))
    win.fmt_combo.blockSignals(False)
    win._read_tree_file(str(example))
    check("树重新读取完成", wait_for(lambda: win.tree is not None))
    check("RRF 结果已被清空", win.rrf_result is None)
    check("校正结果已被清空", win.calibrated_result is None)
    check("CI 结果已被清空", win.ci_result is None)
    check("CorrTest 结果已被清空", win.corrtest_result is None)
    check("ddBD 结果已被清空", win.ddbd_result is None)
    # Calibration points and their marks are bound to the topology of the tree
    # they were placed on, so swapping in a different tree has to invalidate
    # both along with the results.
    check("校正点已被清空", len(win.calibration_editor.calibrations) == 0)
    check("画布校正标记已被清空", len(win.canvas.calibration_marks) == 0)
    check("等效 CLI 已被清空", win.cli_text.toPlainText().startswith("#"))
    check("导出按钮重新禁用", not win.btn_export.isEnabled())
    check("校正按钮重新禁用", not win.btn_run_calibrate.isEnabled())
    grab("08_reloaded_tree.png")

    win.close()
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
