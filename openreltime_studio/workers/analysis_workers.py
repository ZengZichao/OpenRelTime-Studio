"""Background workers — run the openreltime calls in a QThread so the UI stays responsive.

Each worker corresponds to one analysis task and reports its result or failure
back through signals.  Every call that would ``import openreltime`` goes
through the :mod:`openreltime_studio.adapters` layer instead.

Error-handling contract: a worker must catch every exception so a failing
analysis can never take the QThread down, and it logs the full traceback via
:func:`_format_error` (the GUI shows that log).  The user-facing text is then
localized per exception class, because presenting a configuration or
environment problem as an ordinary business failure would send the user looking
in the wrong place.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QThread, Signal

from openreltime import (
    CalibratedResult,
    Calibration,
    PhyloNode,
    TimeResult,
)
from openreltime.calibrate import CalibrationCancelled

from openreltime_studio import i18n
from openreltime_studio.adapters import openreltime_adapter as adapter

logger = logging.getLogger("openreltime")

#: CalibrateWorker 错误通道中的取消哨兵（配合 CalibrationCancelled 使用）
CANCELLED_FLAG = "__cancelled__"


def _format_error(exc: BaseException) -> str:
    """记录完整 traceback 并返回面向用户的错误文本。"""
    logger.error(i18n.t("worker.analysis_failed"), exc, exc_info=exc)
    if isinstance(exc, (FileNotFoundError, NotADirectoryError, IsADirectoryError)):
        return i18n.t("worker.file_not_readable", error=str(exc))
    if isinstance(exc, KeyError):
        return i18n.t("worker.node_or_taxon_missing", error=str(exc))
    if isinstance(exc, (ValueError, TypeError)):
        return i18n.t("worker.invalid_input", error=str(exc))
    return f"{type(exc).__name__}: {exc}"


class TreeReadWorker(QThread):
    """读取树文件的 Worker。"""

    done = Signal(object, str)

    def __init__(
        self,
        path: str,
        outgroup: Optional[list[str]] = None,
        fmt: str = "newick",
        resolve_polytomy: str = "error",
        seed: Optional[int] = None,
        outgroup_check: str = "error",
    ):
        super().__init__()
        self.path = path
        self.outgroup = outgroup
        self.fmt = fmt
        self.resolve_polytomy = resolve_polytomy
        self.seed = seed
        self.outgroup_check = outgroup_check

    def run(self):
        try:
            tree = adapter.read_tree(
                self.path,
                outgroup=self.outgroup,
                fmt=self.fmt,
                resolve_polytomy=self.resolve_polytomy,
                seed=self.seed,
                outgroup_check=self.outgroup_check,
            )
            self.done.emit(tree, "")
        except Exception as exc:  # noqa: BLE001 - worker 边界，见 _format_error
            self.done.emit(None, _format_error(exc))


class RRFWorker(QThread):
    """RRF 速率+时间分析 Worker。"""

    done = Signal(object, str)  # (TimeResult | None, error_msg)

    def __init__(
        self,
        tree: PhyloNode,
        mean: str = "geometric",
        normalize: bool = False,
        rate_ratio_threshold: Optional[float] = 20.0,
    ):
        super().__init__()
        self.tree = tree
        self.mean = mean
        self.normalize = normalize
        self.rate_ratio_threshold = rate_ratio_threshold

    def run(self):
        try:
            result = adapter.run_rrf_rates_times(
                self.tree,
                mean=self.mean,
                normalize=self.normalize,
                rate_ratio_threshold=self.rate_ratio_threshold,
            )
            self.done.emit(result, "")
        except Exception as exc:  # noqa: BLE001
            self.done.emit(None, _format_error(exc))


class TimesOnlyWorker(QThread):
    """仅时间分析 Worker。"""

    done = Signal(object, str)

    def __init__(
        self,
        tree: PhyloNode,
        mean: str = "geometric",
        normalize: bool = False,
    ):
        super().__init__()
        self.tree = tree
        self.mean = mean
        self.normalize = normalize

    def run(self):
        try:
            result = adapter.run_rrf_times(
                self.tree, mean=self.mean, normalize=self.normalize
            )
            self.done.emit(result, "")
        except Exception as exc:  # noqa: BLE001
            self.done.emit(None, _format_error(exc))


class CalibrateWorker(QThread):
    """校正分析 Worker（支持进度回报与取消）。"""

    done = Signal(object, str)  # (CalibratedResult | None, error_msg)
    progress = Signal(int, int)  # (done, total)，仅 effective 方法发出

    def __init__(
        self,
        times: TimeResult,
        calibrations: list[Calibration],
        method: str = "bounds",
        n_effective: int = 10000,
        seed: Optional[int] = None,
        provenance: Optional[dict] = None,
    ):
        super().__init__()
        self.times = times
        self.calibrations = calibrations
        self.method = method
        self.n_effective = n_effective
        self.seed = seed
        #: 写进结果报告的输入信息（tree_file / calibrations_file / …）
        self.provenance = provenance or {}
        self._cancelled = False

    def cancel(self) -> None:
        """请求取消（线程安全：仅置一个布尔旗标）。"""
        self._cancelled = True

    @property
    def cancel_requested(self) -> bool:
        """Whether the user pressed "Cancel".

        The engine only polls the progress callback inside the ``effective``
        repetition loop, so a ``bounds`` run finishing normally never raises
        :class:`CalibrationCancelled`; callers check this flag and discard the
        result themselves.
        """
        return self._cancelled

    def run(self):
        try:
            def on_progress(done: int, total: int) -> bool:
                self.progress.emit(done, total)
                return not self._cancelled

            result = adapter.run_calibrate(
                self.times,
                self.calibrations,
                method=self.method,
                n_effective=self.n_effective,
                seed=self.seed,
                progress=on_progress,
                provenance=self.provenance,
            )
            self.done.emit(result, "")
        except CalibrationCancelled:
            self.done.emit(None, CANCELLED_FLAG)
        except Exception as exc:  # noqa: BLE001
            self.done.emit(None, _format_error(exc))


class CIWorker(QThread):
    """置信区间分析 Worker。

    ``n_sites`` 与 ``seq_length`` 都是 Poisson 近似 ``vS(b) = b / L`` 里的
    序列长度，引擎优先取 ``seq_length``；界面统一走 ``n_sites``（与 CLI 的
    ``--n-sites`` 同名同义），``seq_length`` 保留给直接调用 API 的场景。
    """

    done = Signal(object, str)  # (CIResult | None, error_msg)

    def __init__(
        self,
        calibrated: CalibratedResult,
        level: float = 0.95,
        n_sites: Optional[int] = None,
        seq_length: Optional[int] = None,
        branch_var: Optional[dict[int, float]] = None,
    ):
        super().__init__()
        self.calibrated = calibrated
        self.level = level
        self.n_sites = n_sites
        self.seq_length = seq_length
        self.branch_var = branch_var

    def run(self):
        try:
            result = adapter.run_confidence_interval(
                self.calibrated,
                level=self.level,
                n_sites=self.n_sites,
                seq_length=self.seq_length,
                branch_var=self.branch_var,
            )
            self.done.emit(result, "")
        except Exception as exc:  # noqa: BLE001
            self.done.emit(None, _format_error(exc))


class CorrTestWorker(QThread):
    """CorrTest 速率自相关检验 Worker。"""

    done = Signal(object, str)  # (CorrTestResult | None, error_msg)

    def __init__(
        self,
        tree: PhyloNode,
        sister_resample: int = 0,
        seed: Optional[int] = None,
        anchor_node: Optional[int] = None,
        anchor_time: float = 0.0,
    ):
        super().__init__()
        self.tree = tree
        self.sister_resample = sister_resample
        self.seed = seed
        self.anchor_node = anchor_node
        self.anchor_time = anchor_time

    def run(self):
        try:
            result = adapter.run_corrtest(
                self.tree,
                sister_resample=self.sister_resample,
                seed=self.seed,
                anchor_node=self.anchor_node,
                anchor_time=self.anchor_time,
            )
            self.done.emit(result, "")
        except Exception as exc:  # noqa: BLE001
            self.done.emit(None, _format_error(exc))


class DDBDWorker(QThread):
    """ddBD 分化树先验 Worker。"""

    done = Signal(object, str)  # (DDBDResult | None, error_msg)

    def __init__(
        self,
        tree: PhyloNode,
        sampling_frac: Optional[float] = None,
        anchor_node: Optional[int] = None,
        anchor_time: float = 1.0,
        measure: str = "SSE",
    ):
        super().__init__()
        self.tree = tree
        self.sampling_frac = sampling_frac
        self.anchor_node = anchor_node
        self.anchor_time = anchor_time
        self.measure = measure

    def run(self):
        try:
            result = adapter.run_ddbd(
                self.tree,
                sampling_frac=self.sampling_frac,
                anchor_node=self.anchor_node,
                anchor_time=self.anchor_time,
                measure=self.measure,
            )
            self.done.emit(result, "")
        except Exception as exc:  # noqa: BLE001
            self.done.emit(None, _format_error(exc))
