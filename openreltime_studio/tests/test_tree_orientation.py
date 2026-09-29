"""树形几何与根节点朝向的回归测试。

背景：旧实现把每条分支的水平段画在**父节点**的叶序行上、把连接线画在
**子节点**的时刻上，于是尖自己那一行只剩一条竖线，内部节点那一行叠满别人的
分支；同时树只能以「根在右」显示。这里同时锁住两件事：几何正确、四个朝向可切
换且会持久化。
"""

from __future__ import annotations

import math

import pytest

from openreltime_studio import i18n, themes
from openreltime_studio.adapters import openreltime_adapter as adapter
from openreltime_studio.widgets.tree_canvas import (
    DEFAULT_ORIENTATION,
    ORIENTATIONS,
    TreeCanvas,
    configured_orientation,
)

SMALL_NEWHICK = (
    "(((taxonA:0.10,taxonB:0.12)AB:0.03,(taxonC:0.20,taxonD:0.22)CD:0.05)"
    "ABCD:0.03,(taxonE:0.30,taxonF:0.33)EF:0.07)root;"
)


@pytest.fixture
def small_result(tmp_path):
    tree_path = tmp_path / "small.nwk"
    tree_path.write_text(SMALL_NEWHICK + "\n", encoding="utf-8")
    tree = adapter.read_tree(tree_path)
    return adapter.run_rrf_rates_times(tree)


@pytest.fixture
def canvas(qapp, small_result):
    canvas = TreeCanvas()
    canvas.set_orientation(DEFAULT_ORIENTATION, persist=False)
    canvas.plot_timetree(small_result, use_rates=True)
    yield canvas
    canvas.set_orientation(DEFAULT_ORIENTATION, persist=False)


def segments(canvas):
    """画布上所有线段的端点（绘图坐标）。"""
    return [line.get_xydata() for line in canvas.ax.lines if len(line.get_xydata()) == 2]


def tip_rows(canvas):
    """每个尖的叶序（y 或 x，取决于朝向）。"""
    tree = canvas._result.tree
    orders = {}
    tips = tree.tips()
    for i, tip in enumerate(tips):
        orders[tip.node_id] = float(i)
    return orders


# ---- 几何 ---------------------------------------------------------------


def test_every_tip_has_a_terminal_branch_on_its_own_row(canvas, small_result) -> None:
    """每个尖都必须有一条落在自己那一行、从父节点时刻延伸到自身时刻的分支。"""
    tree = small_result.tree
    times = small_result.times
    orders = tip_rows(canvas)
    segs = segments(canvas)
    horizontal = canvas._is_horizontal()

    for tip in tree.tips():
        row = orders[tip.node_id]
        parent_time = times[tip.parent.node_id]
        tip_time = times[tip.node_id]
        found = False
        for pts in segs:
            (x0, y0), (x1, y1) = pts
            if horizontal:
                same_row = math.isclose(y0, row) and math.isclose(y1, row)
                span = sorted((x0, x1))
                covers = math.isclose(span[0], parent_time) and math.isclose(
                    span[1], tip_time
                ) or math.isclose(span[0], tip_time) and math.isclose(
                    span[1], parent_time
                )
            else:
                same_row = math.isclose(x0, row) and math.isclose(x1, row)
                span = sorted((y0, y1))
                covers = math.isclose(span[0], parent_time) and math.isclose(
                    span[1], tip_time
                ) or math.isclose(span[0], tip_time) and math.isclose(
                    span[1], parent_time
                )
            if same_row and covers:
                found = True
                break
        assert found, f"尖 {tip.label} 那一行没有属于自己的末端分支"


def test_branch_count_is_two_per_non_root_node(canvas, small_result) -> None:
    """每个非根节点恰好贡献「连接线 + 自身分支」两条线段。"""
    tree = small_result.tree
    expected = 2 * (len(list(tree.walk())) - 1)
    assert len(segments(canvas)) == expected


def test_connector_sits_at_parent_divergence_time(canvas, small_result) -> None:
    """连接线必须落在父节点的分歧时刻上（旧实现错在子节点时刻）。"""
    tree = small_result.tree
    times = small_result.times
    orders = tip_rows(canvas)
    segs = segments(canvas)
    for tip in tree.tips():
        parent_time = times[tip.parent.node_id]
        row = orders[tip.node_id]
        parent_row = orders[tip.parent.node_id] if tip.parent.node_id in orders else None
        if parent_row is None:
            continue
        # 父节点行 → 子节点行的竖（或横）线段，其时间坐标应为父节点时刻
        connector = [
            pts
            for pts in segs
            for (a, b) in [pts]
            if (
                math.isclose(a[0], b[0]) and {round(a[1], 6), round(b[1], 6)} ==
                {round(parent_row, 6), round(row, 6)}
                and math.isclose(a[0], parent_time)
            )
            or (
                math.isclose(a[1], b[1]) and {round(a[0], 6), round(b[0], 6)} ==
                {round(parent_row, 6), round(row, 6)}
                and math.isclose(a[1], parent_time)
            )
        ]
        assert connector, f"节点 {tip.node_id} 的连接线不在父节点时刻 {parent_time:g} 上"


# ---- 朝向 ---------------------------------------------------------------


@pytest.mark.parametrize("name", ORIENTATIONS)
def test_all_orientations_render(qapp, small_result, name) -> None:
    canvas = TreeCanvas()
    canvas.set_orientation(name, persist=False)
    canvas.plot_timetree(small_result, use_rates=True)
    ax = canvas.ax
    assert len(segments(canvas)) == 2 * (len(list(small_result.tree.walk())) - 1)
    if name in ("left", "right"):
        assert ax.get_xlabel() == i18n.t("canvas.axis_relative")
        assert ax.get_ylabel() == ""
        assert len(ax.get_yticklabels()) == len(small_result.tree.tips())
    else:
        assert ax.get_ylabel() == i18n.t("canvas.axis_relative")
        assert len(ax.get_xticklabels()) == len(small_result.tree.tips())
    # 根（最大时刻）落在用户选的那一侧
    root_time = small_result.times[small_result.tree.node_id]
    max_tip = max(small_result.times.values())
    assert math.isclose(root_time, max_tip)
    if name == "left":
        assert ax.get_xlim()[0] > ax.get_xlim()[1]
    if name == "right":
        assert ax.get_xlim()[0] < ax.get_xlim()[1]
    if name == "top":
        assert ax.get_ylim()[0] < ax.get_ylim()[1]
    if name == "bottom":
        assert ax.get_ylim()[0] > ax.get_ylim()[1]


def test_orientation_defaults_to_root_on_left(qapp) -> None:
    from PySide6.QtCore import QSettings

    assert DEFAULT_ORIENTATION == "left"
    QSettings("OpenRelTime", "Studio").remove("ui/root_position")
    assert configured_orientation() == "left"
    assert TreeCanvas().orientation == "left"


def test_orientation_is_persisted_and_restored(qapp) -> None:
    from PySide6.QtCore import QSettings

    canvas = TreeCanvas()
    canvas.set_orientation("top")
    settings = QSettings("OpenRelTime", "Studio")
    assert settings.value("ui/root_position") == "top"
    assert configured_orientation() == "top"

    settings.remove("ui/root_position")
    assert configured_orientation() == DEFAULT_ORIENTATION


def test_invalid_orientation_is_rejected(qapp) -> None:
    canvas = TreeCanvas()
    with pytest.raises(ValueError):
        canvas.set_orientation("sideways", persist=False)


def test_orientation_survives_language_and_theme_switches(qapp, small_result) -> None:
    canvas = TreeCanvas()
    canvas.set_orientation("bottom", persist=False)
    canvas.plot_timetree(small_result, use_rates=True)
    before = len(segments(canvas))

    i18n.set_language("zh", persist=False)
    themes.set_theme("dark", persist=False)
    assert canvas.orientation == "bottom"
    assert len(segments(canvas)) == before
    assert canvas.ax.get_ylabel() == i18n.t("canvas.axis_relative")

    themes.set_theme("light", persist=False)
    i18n.set_language("en", persist=False)


@pytest.mark.parametrize(
    "name,axis,side",
    [
        ("left", "y", 2),    # 尖在右 → 标签在右轴
        ("right", "y", 1),   # 尖在左 → 标签在左轴
        ("top", "x", 1),     # 尖在下 → 标签在底轴
        ("bottom", "x", 2),  # 尖在上 → 标签在顶轴
    ],
)
def test_tip_labels_sit_on_the_axis_nearest_the_tips(
    qapp, small_result, name, axis, side
) -> None:
    """尖标签必须贴着尖那一侧，否则读者要横跨整幅图找对应关系。"""
    canvas = TreeCanvas()
    canvas.set_orientation(name, persist=False)
    canvas.plot_timetree(small_result, use_rates=True)
    ax = canvas.ax
    ticks = (ax.yaxis if axis == "y" else ax.xaxis).get_major_ticks()
    assert ticks, "没有刻度"
    near = getattr(ticks[0], f"label{side}")
    far = getattr(ticks[0], f"label{3 - side}")
    assert near.get_visible(), f"{name}: 尖标签没有落在靠尖的 {axis} 轴 {side} 侧"
    assert not far.get_visible(), f"{name}: 远离尖的一侧仍在显示尖标签"
