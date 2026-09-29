"""可交互树画布 — 用 FigureCanvasQTAgg 嵌入 Qt 窗口。

支持：
- 绘制时间树（着色分支按相对速率）；
- 绘制置信区间误差棒；
- 鼠标点击选中节点（用于交互式校正点设置）；
- 鼠标悬停显示节点信息。

文案全部走 ``i18n``（图内文字在重绘时取当前语言），配色全部走 ``themes``
（绘制当下取令牌），因此语言与主题可即时切换：主题管理器经 ``themes.watch()``
回调 ``retheme()``，语言管理器经 ``on_language_change()`` 回调
``_retranslate()``，两者都按当前视图原样重画，不丢失已加载的结果。

计算用 Agg 后端，显示用 Qt 后端，二者分离避免冲突。
"""

from __future__ import annotations

from typing import Any, Optional

# 必须在 import pyplot 之前设置 Agg 后端，以避免 GUI 后端冲突
import matplotlib
import numpy as np

matplotlib.use("Agg")

# 画布含中文文案（空态提示、轴标题）：配置系统 CJK 字体回退链，
# 否则默认 DejaVu Sans 缺中文字形，文字会渲染为方框
matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["font.sans-serif"] = [
    "PingFang SC",          # macOS
    "Hiragino Sans GB",     # macOS
    "Microsoft YaHei",      # Windows
    "Noto Sans CJK SC",     # Linux
    "Source Han Sans SC",
    "DejaVu Sans",
]
matplotlib.rcParams["axes.unicode_minus"] = False

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from PySide6.QtCore import Signal

from openreltime import CalibratedResult, PhyloNode, TimeResult
from openreltime_studio import i18n, themes
from openreltime_studio.adapters import openreltime_adapter as adapter

# ── 配色 ─────────────────────────────────────────────────────────────────

#: 速率分档数：由当前主题的 ``rate_low`` → ``rate_high`` 两端构造分段色带
_RATE_STEPS = 10

# ── 朝向（根节点位置）────────────────────────────────────────────────────

#: 根节点可摆放的四个方向；``left`` 是系统发育树的常规朝向（根在左、尖在右）。
ORIENTATIONS = ("left", "right", "top", "bottom")
DEFAULT_ORIENTATION = "left"
ORIENTATION_SETTINGS_KEY = "ui/root_position"


def configured_orientation() -> str:
    """启动时应使用的朝向：上次保存的偏好优先，否则 ``left``。"""
    stored = _read_orientation_setting()
    if isinstance(stored, str) and stored in ORIENTATIONS:
        return stored
    return DEFAULT_ORIENTATION



class TreeCanvas(FigureCanvas):
    """可交互的时间树 matplotlib 画布，嵌入 Qt 窗口。

    信号：
        node_clicked(int) — 鼠标点击命中内部节点时发出（node_id）。
        node_hovered(str) — 鼠标悬停在节点上时发出（信息文本）。
    """

    node_clicked = Signal(int)
    node_hovered = Signal(str)

    def __init__(self, parent=None, width: float = 8, height: float = 6, dpi: int = 100):
        # 直接构造 Figure，避免注册进 pyplot 的全局图表管理器
        self.fig: Figure = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)
        self.ax = self.fig.add_subplot(111)

        # 节点坐标缓存（用于鼠标命中判定）
        self._node_coords: dict[int, tuple[float, float]] = {}
        self._node_labels: dict[int, str] = {}
        self._result: Optional[Any] = None
        self._hit_radius_px: float = 10.0  # 命中半径（设备像素，量纲一致）
        self._calibration_marks: set[int] = set()  # 已标记校正点
        self._mark_artists: list = []  # 校正点标记的 Artist（重绘时移除）
        # 根节点朝向：left / right / top / bottom
        self._orientation = configured_orientation()
        # 当前视图（类型 + 入参）：主题/语言切换时据此重画，不丢已加载结果
        self._view: dict[str, Any] = {"kind": "empty"}

        self.reset()

        # 连接鼠标事件
        self.mpl_connect("button_press_event", self._on_click)
        self.mpl_connect("motion_notify_event", self._on_motion)

        # 主题与语言即时切换
        themes.watch(self)
        self._language_hook = i18n.on_language_change(self._retranslate)

    # ---- 绘制 ----------------------------------------------------------

    def reset(self):
        """清空画布与全部内部状态，回到空态提示。

        加载新树或希望丢弃旧结果时必须调用：否则坐标缓存会残留，
        点击空白画布仍会命中旧节点。
        """
        self._node_coords = {}
        self._node_labels = {}
        self._result = None
        self._calibration_marks = set()
        self._mark_artists = []
        self._view = {"kind": "empty"}
        self._draw_empty()
        self.draw_idle()

    def retheme(self):
        """主题切换回调：重新取色并重画当前视图。"""
        self._render_view()

    def _retranslate(self, _lang: str = ""):
        """语言切换回调：图内文字随重绘重新取文案。"""
        self._render_view()

    def _render_view(self):
        """按 ``_view`` 重画当前内容（未加载任何结果时画空态）。"""
        kind = self._view.get("kind", "empty")
        if kind == "timetree":
            self.plot_timetree(
                self._view["result"], use_rates=self._view["use_rates"]
            )
        elif kind == "ci":
            self.plot_ci(self._view["result"], max_nodes=self._view["max_nodes"])
        elif kind == "ddbd":
            self.plot_ddbd(self._view["result"], self._view["times_result"])
        else:
            self._draw_empty()
            self.draw_idle()

    # ---- 朝向（根节点位置）------------------------------------------------

    @property
    def orientation(self) -> str:
        """当前根节点朝向。"""
        return self._orientation

    def set_orientation(self, name: str, *, persist: bool = True) -> str:
        """切换根节点朝向，并按当前视图原样重画。"""
        if name not in ORIENTATIONS:
            raise ValueError(f"unsupported orientation: {name!r}")
        changed = name != self._orientation
        self._orientation = name
        if persist:
            _persist_orientation(name)
        if changed:
            self._render_view()
        return name

    def _is_horizontal(self) -> bool:
        """树是否沿水平方向展开（根在左或右）。"""
        return self._orientation in ("left", "right")

    def _plot_xy(self, time_value: float, order: float) -> tuple[float, float]:
        """规范坐标 ``(时间, 叶序)`` → 当前朝向下的绘图坐标。"""
        if self._is_horizontal():
            return time_value, order
        return order, time_value

    def _apply_orientation(self) -> None:
        """按朝向翻转坐标轴。

        ``times`` 是「距今天数」（尖 = 0，根最大），因此根要摆在左侧或下侧
        就得翻转时间轴；叶序轴一律翻转成「尖 0 在上/在左」，与节点表的顺序
        一致。
        """
        if self._orientation == "left":
            self.ax.invert_xaxis()
            self.ax.invert_yaxis()
        elif self._orientation == "right":
            self.ax.invert_yaxis()
        elif self._orientation == "bottom":
            self.ax.invert_yaxis()

    def _place_tip_labels(self) -> None:
        """把尖标签挪到离尖最近的那条轴上。

        根在左时尖排在右边、根在下时尖排在上面；标签若仍留在左轴或底轴，
        读者就得横跨整幅图去找对应关系。
        """
        if self._orientation == "left":
            self.ax.tick_params(
                axis="y", left=False, labelleft=False, right=True, labelright=True
            )
        elif self._orientation == "right":
            self.ax.tick_params(
                axis="y", left=True, labelleft=True, right=False, labelright=False
            )
        elif self._orientation == "bottom":
            self.ax.tick_params(
                axis="x", bottom=False, labelbottom=False, top=True, labeltop=True
            )
        else:  # top
            self.ax.tick_params(
                axis="x", bottom=True, labelbottom=True, top=False, labeltop=False
            )

    def _apply_theme(self):
        """把当前主题写进 figure/axes（画布只构造一次，之后须显式刷新）。

        ``ax.clear()`` 会按全局 rcParams 复位底色与文字色，因此每次重绘之
        后都要重新套用一次，否则暗色下会出现白底黑字方块。
        """
        tk = themes.tokens()
        rc = themes.mpl_rc_params()
        self.fig.set_facecolor(rc["figure.facecolor"])
        self.fig.set_edgecolor(tk.canvas_edge)
        self.ax.set_facecolor(rc["axes.facecolor"])
        for spine in self.ax.spines.values():
            spine.set_color(rc["axes.edgecolor"])
        self.ax.tick_params(
            which="both", colors=rc["xtick.color"], labelcolor=rc["xtick.color"]
        )
        self.ax.xaxis.label.set_color(rc["axes.labelcolor"])
        self.ax.yaxis.label.set_color(rc["axes.labelcolor"])
        self.ax.title.set_color(rc["axes.titlecolor"])
        legend = self.ax.get_legend()
        if legend is not None:
            frame = legend.get_frame()
            frame.set_facecolor(rc["legend.framebackground"])
            frame.set_edgecolor(tk.border)
            frame.set_alpha(rc["legend.framealpha"])
            for item in legend.get_texts():
                item.set_color(rc["text.color"])

    def _draw_empty(self):
        """画空态提示（底色、文字色与文案都取自当前主题/语言）。"""
        self.ax.clear()
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for spine in self.ax.spines.values():
            spine.set_visible(False)
        self._apply_theme()
        self.ax.text(
            0.5, 0.5, i18n.t("canvas.empty_hint"),
            transform=self.ax.transAxes,
            ha="center", va="center", fontsize=11, color=themes.tokens().text_muted,
        )

    def plot_timetree(
        self,
        result: TimeResult | CalibratedResult,
        *,
        use_rates: bool = True,
    ):
        """Draw the coloured time tree.

        Calibration marks belong to the calibration list, not to one particular
        drawing pass, so this must not clear them: it redraws the current set
        after the coordinate cache has been rebuilt.  Clearing the set here
        would make every mark the user added interactively vanish the moment
        the tree was replotted.
        """
        self._result = result
        self._view = {"kind": "timetree", "result": result, "use_rates": use_rates}
        tk = themes.tokens()
        self.ax.clear()

        tree: PhyloNode = result.tree
        times = result.times

        # 计算 y 坐标（叶子按顺序排列，内部节点取子节点平均）
        tips = tree.tips()
        y_of: dict[int, float] = {}
        for i, tip in enumerate(tips):
            y_of[tip.node_id] = float(i)
        for node in tree.iter_postorder():
            if node.is_tip():
                continue
            kids = [y_of[c.node_id] for c in node.children]
            y_of[node.node_id] = (kids[0] + kids[-1]) / 2

        # 速率配色：色带两端随主题取，暗色下得到暗色友好的端点
        rates = getattr(result, "rates", {})
        rvals = np.array([r for r in rates.values() if r > 0], dtype=float)
        rmin, rmax = (rvals.min(), rvals.max()) if rvals.size else (0.0, 1.0)
        rate_cmap = LinearSegmentedColormap.from_list(
            "openreltime_rate", [tk.rate_low, tk.rate_high], _RATE_STEPS
        )

        def rate_color(node: PhyloNode):
            if not use_rates or node.node_id not in rates or rmax <= rmin:
                return tk.tree_base
            frac = (rates[node.node_id] - rmin) / (rmax - rmin)
            return rate_cmap(min(int(frac * _RATE_STEPS), _RATE_STEPS - 1))

        # 绘制分支：每条分支画在自己的叶序行上，连接线画在父节点的分歧时刻。
        # 旧实现把水平段画在父节点的行、把连接线画在子节点的时刻上，于是
        # 内部节点那一行叠满别人的分支，而尖自己那一行只剩一条竖线。
        for node in tree.walk():
            if node.is_root():
                continue
            parent = node.parent
            assert parent is not None
            parent_xy = self._plot_xy(times[parent.node_id], y_of[parent.node_id])
            elbow_xy = self._plot_xy(times[parent.node_id], y_of[node.node_id])
            node_xy = self._plot_xy(times[node.node_id], y_of[node.node_id])
            color = rate_color(node)
            self.ax.plot(
                [parent_xy[0], elbow_xy[0]], [parent_xy[1], elbow_xy[1]],
                color=color, lw=1.2,
            )
            self.ax.plot(
                [elbow_xy[0], node_xy[0]], [elbow_xy[1], node_xy[1]],
                color=color, lw=1.2,
            )

        # 标签：随树的大小自适应字号，小树可读、大树不重叠
        is_calibrated = isinstance(result, CalibratedResult)
        tip_fontsize = max(4.0, min(8.0, 200.0 / max(len(tips), 1)))
        time_label = i18n.t(
            "canvas.axis_time" if is_calibrated else "canvas.axis_relative"
        )
        tip_orders = [y_of[t.node_id] for t in tips]
        tip_names = [t.label or "" for t in tips]
        if self._is_horizontal():
            self.ax.set_yticks(tip_orders)
            self.ax.set_yticklabels(tip_names, fontsize=tip_fontsize)
            self.ax.tick_params(axis="y", labelsize=tip_fontsize)
            self.ax.set_xlabel(time_label, fontsize=9)
        else:
            self.ax.set_xticks(tip_orders)
            self.ax.set_xticklabels(
                tip_names, fontsize=tip_fontsize, rotation=90, ha="center"
            )
            self.ax.tick_params(axis="x", labelsize=tip_fontsize)
            self.ax.set_ylabel(time_label, fontsize=9)
        self._apply_orientation()
        self._place_tip_labels()
        self.ax.spines["top"].set_visible(False)
        self.ax.spines["right"].set_visible(False)
        self._apply_theme()

        # 缓存节点坐标
        self._node_coords = {}
        self._node_labels = {}
        for node in tree.walk():
            if node.is_tip():
                continue
            nid = node.node_id
            self._node_coords[nid] = self._plot_xy(times[nid], y_of[nid])
            desc = []
            for t in node.tips()[:3]:
                desc.append(t.label or "")
            label = i18n.t("canvas.node_label", node_id=nid)
            if desc:
                shown = ", ".join(desc) + ("..." if len(node.tips()) > 3 else "")
                label = i18n.t(
                    "canvas.node_label_with_tips", node_id=nid, tips=shown
                )
            self._node_labels[nid] = label

        self.fig.tight_layout()
        self._draw_marks()
        self.draw_idle()

    def plot_ci(self, ci_result, *, max_nodes: int = 60):
        """绘制置信区间误差棒图。"""
        self._result = None
        self._view = {"kind": "ci", "result": ci_result, "max_nodes": max_nodes}
        self._node_coords = {}
        self._node_labels = {}
        self._mark_artists = []
        tk = themes.tokens()
        self.ax.clear()
        frame = ci_result.table.sort_values("time", ascending=False).head(max_nodes)
        y = np.arange(len(frame))[::-1]

        self.ax.errorbar(
            frame["time"], y,
            xerr=[frame["time"] - frame["lower"], frame["upper"] - frame["time"]],
            fmt="o", ms=3, lw=1, color=tk.ci_color, ecolor=tk.ci_error,
        )
        self.ax.set_yticks(y)
        n_labels = max(len(frame), 1)
        # label 为空时回退为节点编号，避免 y 轴只剩 "-"
        tick_labels = []
        for row in frame.itertuples():
            label = getattr(row, "label", None)
            if label is None or str(label).strip() in ("", "-", "nan"):
                label = i18n.t(
                    "canvas.node_label", node_id=int(getattr(row, "node_id", 0))
                )
            tick_labels.append(str(label))
        self.ax.set_yticklabels(
            tick_labels, fontsize=max(4.0, min(7.0, 160.0 / n_labels))
        )
        self.ax.set_xlabel(i18n.t("canvas.divergence_time_axis"), fontsize=9)
        self.ax.spines["top"].set_visible(False)
        self.ax.spines["right"].set_visible(False)
        self._apply_theme()
        self.fig.tight_layout()
        self.draw_idle()

    def plot_ddbd(self, ddbd_result, times_result: TimeResult):
        """绘制 ddBD 密度图。"""
        self._result = None
        self._view = {
            "kind": "ddbd",
            "result": ddbd_result,
            "times_result": times_result,
        }
        self._node_coords = {}
        self._node_labels = {}
        self._mark_artists = []
        node_times, grid, fitted = adapter.ddbd_node_density(
            ddbd_result, times_result
        )
        tk = themes.tokens()
        self.ax.clear()
        self.ax.hist(
            node_times, bins=30, density=True,
            color=tk.border, edgecolor=tk.canvas_face,
        )
        self.ax.plot(grid, fitted, color=tk.fitted_line, lw=2)
        self.ax.set_xlabel(i18n.t("canvas.node_time_axis"), fontsize=9)
        self.ax.set_ylabel(i18n.t("canvas.density_axis"), fontsize=9)
        self.ax.spines["top"].set_visible(False)
        self.ax.spines["right"].set_visible(False)
        self._apply_theme()
        self.fig.tight_layout()
        self.draw_idle()

    # ---- 校正点标记 -----------------------------------------------------

    def mark_calibration_node(self, node_id: int):
        """在图上标记一个校正点。"""
        self._calibration_marks.add(node_id)
        self._redraw_marks()

    def set_calibration_marks(self, node_ids) -> None:
        """Replace the whole set of calibration marks (called when the list changes).

        Only the mark layer is redrawn, not the tree: neither the topology nor
        the cached node coordinates have changed, so replotting would throw
        away work already done and slow the UI down for every add or remove.
        """
        self._calibration_marks = {int(nid) for nid in node_ids if nid is not None}
        self._redraw_marks()

    def clear_calibration_marks(self):
        """清除所有校正点标记。"""
        self._calibration_marks.clear()
        self._redraw_marks()

    def _redraw_marks(self):
        """按当前标记集合重画标记，并刷新画布。"""
        self._draw_marks()
        self.draw_idle()

    def _draw_marks(self):
        """幂等地把 ``_calibration_marks`` 画成散点（先移除旧 Artist）。"""
        for artist in self._mark_artists:
            if artist.axes is not None:
                artist.remove()
        self._mark_artists = []
        tk = themes.tokens()
        for nid in sorted(self._calibration_marks):
            if nid not in self._node_coords:
                continue  # 该 id 不属于当前绘制的树（例如换树后残留）
            x, y = self._node_coords[nid]
            (line,) = self.ax.plot(
                x, y, "o", ms=8, mfc=tk.mark_fill, mec=tk.mark_edge,
                mew=1.0, zorder=10,
            )
            self._mark_artists.append(line)

    def save_figure(self, path: str, *, dpi: int = 200):
        """保存当前图像到文件。"""
        self.fig.savefig(path, dpi=dpi, bbox_inches="tight")

    # ---- 鼠标交互 ------------------------------------------------------

    def _nearest_node_px(self, mx: float, my: float) -> tuple[Optional[int], float]:
        """在设备像素空间找最近内部节点（数据坐标 → 像素后比较）。

        返回 ``(node_id, distance_px)``；node_id 为 None 表示超出命中半径。
        之前版本直接在数据坐标系算欧氏距离，x（时间）与 y（叶序号）量纲
        不同，大树上命中容差不足 0.02 像素、物理不可点。
        """
        if not self._node_coords:
            return None, float("inf")
        px, py = self.ax.transData.transform((mx, my))
        best_id: Optional[int] = None
        best_d = float("inf")
        for nid, (nx, ny) in self._node_coords.items():
            qx, qy = self.ax.transData.transform((nx, ny))
            d = ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5
            if d < best_d:
                best_d = d
                best_id = nid
        if best_d > self._hit_radius_px:
            return None, best_d
        return best_id, best_d

    def _on_click(self, event):
        """鼠标点击：命中最近的内部节点。"""
        if event.inaxes != self.ax:
            return
        if event.xdata is None or event.ydata is None:
            return
        best_id, _ = self._nearest_node_px(event.xdata, event.ydata)
        if best_id is not None:
            self.node_clicked.emit(best_id)

    def _on_motion(self, event):
        """鼠标悬停：显示节点信息。"""
        if event.inaxes != self.ax:
            return
        if event.xdata is None or event.ydata is None:
            return
        best_id, _ = self._nearest_node_px(event.xdata, event.ydata)
        if best_id is None:
            self.node_hovered.emit("")
            return
        parts = [self._node_labels.get(
            best_id, i18n.t("canvas.node_label", node_id=best_id)
        )]
        if self._result and best_id in self._result.times:
            time_value = self._result.times[best_id]
            unit = (
                i18n.t("canvas.unit_mya")
                if isinstance(self._result, CalibratedResult)
                else ""
            )
            parts.append(
                i18n.t("canvas.hover_time", time=f"{time_value:.4g} {unit}".strip())
            )
        if self._result and hasattr(self._result, "rates"):
            r = self._result.rates.get(best_id)
            if r is not None:
                parts.append(i18n.t("canvas.hover_rate", rate=f"{r:.4g}"))
        self.node_hovered.emit("  ".join(parts))

    @property
    def calibration_marks(self) -> set[int]:
        """当前已标记的校正节点 ID 集合。"""
        return set(self._calibration_marks)


def _read_orientation_setting():
    try:
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication
    except ImportError:  # pragma: no cover - 无 Qt 时退回默认值
        return None
    if QApplication.instance() is None:
        return None
    return QSettings("OpenRelTime", "Studio").value(ORIENTATION_SETTINGS_KEY)


def _persist_orientation(name: str) -> None:
    try:
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication
    except ImportError:  # pragma: no cover - 无 Qt 时忽略持久化
        return
    if QApplication.instance() is None:
        return
    settings = QSettings("OpenRelTime", "Studio")
    settings.setValue(ORIENTATION_SETTINGS_KEY, name)
    settings.sync()
