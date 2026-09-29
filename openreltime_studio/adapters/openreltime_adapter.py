"""适配层 — 唯一调用 ``openreltime`` 公共 API 的隔离层。

职责：
1. 调用 ``openreltime`` 公共 API（read_tree / rrf_rates_times / calibrate /
   confidence_interval / corrtest / ddbd）；
2. 把 Result 对象转换为 UI 可用的模型（DataFrame、Figure、CLI 字符串）；
3. 集中生成等效 CLI 命令字符串。

核心 API 签名变动只需在此层一处修改，不影响 UI 层。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np
import pandas as pd

import openreltime as ort
from openreltime import (
    CalibratedResult,
    Calibration,
    CIResult,
    CorrTestResult,
    DDBDResult,
    PhyloNode,
    RateResult,
    TimeResult,
)
from openreltime.calibrate import parse_calibrations
from openreltime.taxonomy import resolve_taxa_tokens

from openreltime_studio import i18n

#: Single output prefix shared by the exported results and the equivalent CLI
#: script.  ``export_results`` writes ``<out_dir>/openreltime_result*``, so the
#: ``calibrate -o`` / ``ci -c`` / ``ci -o`` arguments in the script have to
#: point at the same prefix; otherwise replaying the script leaves ``ci``
#: without the report produced by the preceding ``calibrate`` step.
OUTPUT_PREFIX = "openreltime_result"

#: GUI 导出的校正点文件名（脚本里的 ``-c`` 参数，相对脚本所在目录）
CALIBRATIONS_FILENAME = "calibrations.tsv"

# ── 树 I/O ──────────────────────────────────────────────────────────────

def read_tree(
    path: str | Path,
    outgroup: Optional[list[str]] = None,
    fmt: str = "newick",
    resolve_polytomy: str = "error",
    seed: Optional[int] = None,
    outgroup_check: str = "error",
) -> PhyloNode:
    """读取并验证系统树，可选 outgroup 置根。"""
    return ort.read_tree(
        str(path),
        fmt=fmt,
        outgroup=outgroup,
        resolve_polytomy=resolve_polytomy,
        seed=seed,
        outgroup_check=outgroup_check,
    )


def detect_format(path: str | Path) -> str:
    """根据文件扩展名自动检测树文件格式。"""
    suffix = Path(path).suffix.lower()
    if suffix in (".nex", ".nexus"):
        return "nexus"
    return "newick"


def find_node_by_id(tree: PhyloNode, node_id: int) -> Optional[PhyloNode]:
    """根据 node_id 查找节点。"""
    for n in tree.walk():
        if n.node_id == node_id:
            return n
    return None


# ── RRF 分析 ────────────────────────────────────────────────────────────

def run_rrf_rates_times(
    tree: PhyloNode,
    mean: str = "geometric",
    normalize: bool = False,
    rate_ratio_threshold: Optional[float] = 20.0,
) -> TimeResult:
    """运行 RRF 速率 + 时间分析。"""
    return ort.rrf_rates_times(
        tree,
        mean=mean,
        normalize=normalize,
        rate_ratio_threshold=rate_ratio_threshold,
    )


def run_rrf_times(
    tree: PhyloNode,
    mean: str = "geometric",
    normalize: bool = False,
) -> TimeResult:
    """仅运行 RRF 时间分析。"""
    return ort.rrf_times(tree, mean=mean, normalize=normalize)


# ── 校正 ────────────────────────────────────────────────────────────────

def load_calibrations(path: str | Path) -> list[Calibration]:
    """从 TSV 文件加载校正点。"""
    return parse_calibrations(path)


def calibrations_to_tsv(calibrations: list[Calibration]) -> str:
    """把校正点列表序列化为 calibrations.tsv 内容（供导出复现）。"""
    lines = ["node_id\ttaxon_set\tmin_bound\tmax_bound\tdensity\tdensity_params"]
    for cal in calibrations:
        node_id = str(cal.node_id) if cal.node_id is not None else ""
        taxon_set = "|".join(sorted(cal.taxon_set)) if cal.taxon_set else "."
        min_b = repr(cal.min_bound) if cal.min_bound is not None else "."
        max_b = repr(cal.max_bound) if cal.max_bound is not None else "."
        density = cal.density or "."
        params = ";".join(f"{k}={v}" for k, v in cal.density_params.items()) or "."
        lines.append(f"{node_id}\t{taxon_set}\t{min_b}\t{max_b}\t{density}\t{params}")
    return "\n".join(lines) + "\n"


def run_calibrate(
    times: TimeResult,
    calibrations: list[Calibration],
    *,
    method: str = "bounds",
    n_effective: int = 10000,
    seed: Optional[int] = None,
    progress: Optional[Any] = None,
    provenance: Optional[dict[str, Any]] = None,
) -> CalibratedResult:
    """Run calibration, converting relative times into absolute times.

    ``progress(done, total) -> bool`` is called after every repetition of the
    ``effective`` method; returning ``False`` cancels the run (the engine then
    raises ``CalibrationCancelled``).

    Keys passed in ``provenance`` (``tree_file`` / ``calibrations_file`` /
    ``outgroup`` / ``input_fmt`` / ``resolve_polytomy`` / ``outgroup_check``)
    are written verbatim into the result's ``params`` and into
    ``_report.json``.  ``openreltime ci`` needs ``tree_file`` there to locate
    the original tree again when the exported script is replayed.
    """
    return ort.calibrate(
        times,
        calibrations,
        method=method,
        n_effective=n_effective,
        seed=seed,
        progress=progress,
        **(provenance or {}),
    )


def make_calibration(
    *,
    node_id: Optional[int] = None,
    taxon_set: Optional[set[str]] = None,
    min_bound: Optional[float] = None,
    max_bound: Optional[float] = None,
    density: Optional[str] = None,
    density_params: Optional[dict[str, float]] = None,
) -> Calibration:
    """构造一个 Calibration 对象。"""
    return Calibration(
        taxon_set=frozenset(taxon_set) if taxon_set else None,
        node_id=node_id,
        min_bound=min_bound,
        max_bound=max_bound,
        density=density,
        density_params=density_params or {},
    )


def format_bound(value: Optional[float]) -> str:
    """Render one calibration bound for the table.

    Emptiness has to be tested with ``is None``: ``0.0`` is a perfectly legal
    bound, and a truthiness test would render it as the ``-`` "no bound"
    placeholder.
    """
    return "-" if value is None else str(value)


def bound_error(
    min_bound: Optional[float],
    max_bound: Optional[float],
    density: Optional[str] = None,
    *,
    method: Optional[str] = None,
) -> Optional[str]:
    """Describe the first problem found in a calibration's bounds.

    Returns ``None`` when the bounds are usable.  A density-only calibration
    has no numeric bound at all, which under ``method="bounds"`` leaves the
    engine to solve the global time factor as ``inf``; rejecting that pairing
    here is the GUI-side guard against it.
    """
    if min_bound is None and max_bound is None and not density:
        return i18n.t("adapter.bound_need_one_field")
    if min_bound is None and max_bound is None and density and method == "bounds":
        return i18n.t("adapter.bounds_needs_numeric_bound")
    for name, value in (("Min", min_bound), ("Max", max_bound)):
        if value is None:
            continue
        if not math.isfinite(value):
            return i18n.t("adapter.bound_must_be_finite", name=name)
        if value < 0:
            return i18n.t("adapter.bound_cannot_be_negative", name=name)
    if max_bound == 0.0:
        return i18n.t("adapter.max_bound_zero_scales_tree")
    if min_bound is not None and max_bound is not None and min_bound > max_bound:
        return i18n.t("adapter.min_bound_exceeds_max_bound")
    return None


def describe_calibration_target(cal: Calibration) -> str:
    """校正点的可读标识（node_id 或 taxon_set）。"""
    if cal.node_id is not None:
        return f"node_id {cal.node_id}"
    if cal.taxon_set:
        return "taxon_set " + "|".join(sorted(cal.taxon_set))
    return i18n.t("adapter.no_target")


def _calibration_target(
    tree: PhyloNode,
    cal: Calibration,
    *,
    taxon_table: Optional[dict[str, list[str]]] = None,
) -> tuple[Optional[PhyloNode], Optional[str]]:
    """``(命中的内部节点, 未命中的原因)``，两者最多一个非空。

    判定与引擎 :func:`openreltime.calibrate` 的目标解析一致：``node_id``
    直接查表，只给 ``taxon_set`` 的校正按尖标签或群名求 MRCA。
    """
    if cal.node_id is not None:
        node = find_node_by_id(tree, cal.node_id)
        if node is None:
            return None, i18n.t("adapter.node_id_not_in_tree", node_id=cal.node_id)
        if node.is_tip():
            return None, i18n.t("adapter.node_id_is_tip", node_id=cal.node_id)
        return node, None

    tokens = sorted(cal.taxon_set or ())
    if not tokens:
        return None, i18n.t("adapter.calibration_has_no_target")
    labels = set(tree.tip_labels())
    if not set(tokens) <= labels:
        try:
            tokens = resolve_taxa_tokens(
                tree, tokens, taxon_table=taxon_table, context="calibration"
            )
        except Exception as exc:  # noqa: BLE001 - 校验器不得抛出
            return None, i18n.t(
                "adapter.taxon_set_unresolved",
                taxa="|".join(tokens),
                error=str(exc),
            )
        unknown = sorted(t for t in tokens if t not in labels)
        if unknown:
            return None, i18n.t("adapter.taxon_set_unknown_names", names=unknown)
    if not tokens:
        return None, i18n.t("adapter.taxon_set_empty_after_resolution")
    node = tree.mrca(tokens)
    if node is None or node.is_tip():
        return None, i18n.t(
            "adapter.taxon_set_single_tip",
            taxa="|".join(sorted(cal.taxon_set or ())),
        )
    return node, None


def resolve_calibration_target(
    tree: PhyloNode,
    cal: Calibration,
    *,
    taxon_table: Optional[dict[str, list[str]]] = None,
) -> Optional[PhyloNode]:
    """校正点在当前树中命中的内部节点；命不中时返回 ``None``。"""
    node, _ = _calibration_target(tree, cal, taxon_table=taxon_table)
    return node


def calibration_target_problem(
    tree: PhyloNode,
    cal: Calibration,
    *,
    taxon_table: Optional[dict[str, list[str]]] = None,
) -> Optional[str]:
    """校正点无法命中当前树内部节点时的可读原因；合法时返回 ``None``。"""
    return _calibration_target(tree, cal, taxon_table=taxon_table)[1]


def validate_calibrations(
    tree: PhyloNode,
    calibrations: Sequence[Calibration],
    *,
    taxon_table: Optional[dict[str, list[str]]] = None,
) -> tuple[list[Calibration], list[str]]:
    """Validate the calibrations against the current tree.

    Returns ``(kept, reasons_for_dropped)``.  A ``taxon_set`` calibration is
    legitimate without a ``node_id``: the engine resolves it to the MRCA of its
    taxa, and the CLI accepts it as-is, so loading it in the GUI must not drop
    it silently as if it were malformed.
    """
    kept: list[Calibration] = []
    problems: list[str] = []
    for cal in calibrations:
        problem = calibration_target_problem(
            tree, cal, taxon_table=taxon_table
        )
        if problem is None:
            kept.append(cal)
        else:
            problems.append(problem)
    return kept, problems


def load_branch_variances(path: str | Path) -> dict[int, float]:
    """读取 ``node_id<TAB>var`` 的 TSV（与 CLI ``--branch-var`` 同格式）。"""
    frame = pd.read_csv(str(path), sep="\t")
    missing = {"node_id", "var"} - set(frame.columns)
    if missing:
        raise ValueError(
            i18n.t(
                "adapter.branch_var_missing_columns",
                path=path,
                columns=sorted(missing),
            )
        )
    return {int(r["node_id"]): float(r["var"]) for _, r in frame.iterrows()}


# ── 置信区间 ────────────────────────────────────────────────────────────

def run_confidence_interval(
    calibrated: CalibratedResult,
    *,
    level: float = 0.95,
    n_sites: Optional[int] = None,
    seq_length: Optional[int] = None,
    branch_var: Optional[dict[int, float]] = None,
) -> CIResult:
    """运行置信区间分析。"""
    return ort.confidence_interval(
        calibrated,
        level=level,
        n_sites=n_sites,
        seq_length=seq_length,
        branch_var=branch_var,
    )


# ── CorrTest ───────────────────────────────────────────────────────────

def run_corrtest(
    tree: PhyloNode,
    *,
    sister_resample: int = 0,
    seed: Optional[int] = None,
    anchor_node: Optional[int] = None,
    anchor_time: float = 0.0,
) -> CorrTestResult:
    """运行速率自相关检验。"""
    return ort.corrtest(
        tree,
        sister_resample=sister_resample,
        seed=seed,
        anchor_node=anchor_node,
        anchor_time=anchor_time,
    )


# ── ddBD ───────────────────────────────────────────────────────────────

def run_ddbd(
    tree: PhyloNode,
    *,
    sampling_frac: Optional[float] = None,
    anchor_node: Optional[int] = None,
    anchor_time: float = 1.0,
    measure: str = "SSE",
) -> DDBDResult:
    """运行出生-死亡分化树先验分析。"""
    return ort.ddbd(
        tree,
        sampling_frac=sampling_frac,
        anchor_node=anchor_node,
        anchor_time=anchor_time,
        measure=measure,
    )


# ── ddBD 绘图数据（隔离 openreltime 私有 API，画布层只做展示）──────────

def ddbd_node_density(
    ddbd_result: DDBDResult, times_result: TimeResult
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """返回 (节点相对时间×scale_factor, 密度网格, 拟合密度曲线)。"""
    from openreltime.ddbd import _bd_density, _r_density

    internal = np.array(
        [times_result.times[n.node_id]
         for n in times_result.tree.walk() if not n.is_tip()],
        dtype=float,
    )
    if internal.size == 0:
        raise ValueError(i18n.t("adapter.ddbd_no_internal_nodes"))
    rel = np.clip(internal / internal.max(), 0, None)
    sf = ddbd_result.scale_factor
    grid, _ = _r_density(rel * sf)
    fitted = _bd_density(
        grid / sf,
        ddbd_result.birth_rate * sf,
        ddbd_result.death_rate * sf,
        ddbd_result.sampling_frac,
        root_age=1.0,
    )
    return rel * sf, grid, fitted


# ── Result → UI 模型转换 ────────────────────────────────────────────────

def result_to_dataframe(result: Any, with_rate: bool = True) -> "Any":
    """把 Result 对象转换为 pandas DataFrame（供 QTableWidget 使用）。"""
    if hasattr(result, "to_pandas"):
        try:
            return result.to_pandas(with_rate=with_rate)
        except TypeError:
            return result.to_pandas()
    raise TypeError(
        i18n.t("adapter.unsupported_result_type", name=type(result).__name__)
    )


# ── 等效 CLI 字符串生成 ──────────────────────────────────────────────────

def _tree_input_args(
    outgroup: Optional[str],
    input_fmt: Optional[str] = None,
    resolve_polytomy: Optional[str] = None,
    outgroup_check: Optional[str] = None,
) -> str:
    """Tree-reading settings, emitted as ``--outgroup/--fmt/--resolve/--outgroup-check``.

    Every one of these values is written out explicitly, even when it already
    equals the CLI default, so that replaying the exported script reads back
    exactly the tree the GUI worked with.
    """
    args = f' --outgroup "{outgroup}"' if outgroup else ""
    if input_fmt:
        args += f" --fmt {input_fmt}"
    if resolve_polytomy:
        args += f" --resolve {resolve_polytomy}"
    if outgroup_check:
        args += f" --outgroup-check {outgroup_check}"
    return args


def build_cli_rates_times(
    tree_path: str,
    outgroup: Optional[str],
    mean: str,
    normalize: bool,
    output: str = OUTPUT_PREFIX,
    *,
    input_fmt: Optional[str] = None,
    resolve_polytomy: Optional[str] = None,
    outgroup_check: Optional[str] = None,
) -> str:
    """生成 rates-times 子命令的等效 CLI 字符串。"""
    norm = " --normalize" if normalize else ""
    return (
        f'openreltime rates-times -i "{tree_path}"'
        f'{_tree_input_args(outgroup, input_fmt, resolve_polytomy, outgroup_check)} '
        f"--mean {mean}{norm} -o {output}"
    )


def build_cli_calibrate(
    tree_path: str,
    calibrations_path: str,
    outgroup: Optional[str],
    method: str,
    n_effective: int,
    seed: Optional[int],
    output: str = OUTPUT_PREFIX,
    *,
    input_fmt: Optional[str] = None,
    resolve_polytomy: Optional[str] = None,
    outgroup_check: Optional[str] = None,
) -> str:
    """生成 calibrate 子命令的等效 CLI 字符串。"""
    seed_arg = f" --seed {seed}" if seed is not None else ""
    neff_arg = f" --n-effective {n_effective}" if method == "effective" else ""
    return (
        f'openreltime calibrate -i "{tree_path}" '
        f'-c "{calibrations_path}"'
        f'{_tree_input_args(outgroup, input_fmt, resolve_polytomy, outgroup_check)} '
        f"--method {method}{neff_arg}{seed_arg} -o {output}"
    )


def build_cli_ci(
    calibrated_prefix: str,
    level: float,
    n_sites: Optional[int],
    output: str = OUTPUT_PREFIX,
    *,
    branch_var: Optional[str] = None,
) -> str:
    """生成 ci 子命令的等效 CLI 字符串。

    ``calibrated_prefix`` 必须是上一步 calibrate 的 ``-o`` 前缀（同一
    ``OUTPUT_PREFIX``），否则 ``ci`` 读不到 ``_report.json``。
    """
    nsites_arg = f" --n-sites {n_sites}" if n_sites is not None else ""
    bvar_arg = f' --branch-var "{branch_var}"' if branch_var else ""
    return (
        f"openreltime ci -c {calibrated_prefix} "
        f"--level {level}{nsites_arg}{bvar_arg} -o {output}"
    )


def build_cli_corrtest(
    tree_path: str,
    outgroup: Optional[str],
    sister_resample: int,
    seed: Optional[int],
    anchor_node: Optional[int],
    anchor_time: float,
    output: str = OUTPUT_PREFIX,
    *,
    input_fmt: Optional[str] = None,
    resolve_polytomy: Optional[str] = None,
    outgroup_check: Optional[str] = None,
) -> str:
    """生成 corrtest 子命令的等效 CLI 字符串。"""
    sr_arg = f" --sister-resample {sister_resample}" if sister_resample else ""
    seed_arg = f" --seed {seed}" if seed is not None else ""
    an_arg = f" --anchor-node {anchor_node}" if anchor_node is not None else ""
    at_arg = f" --anchor-time {anchor_time}" if anchor_node is not None else ""
    return (
        f'openreltime corrtest -i "{tree_path}"'
        f"{_tree_input_args(outgroup, input_fmt, resolve_polytomy, outgroup_check)}"
        f"{sr_arg}{seed_arg}{an_arg}{at_arg} -o {output}"
    )


def build_cli_ddbd(
    tree_path: str,
    outgroup: Optional[str],
    anchor_node: Optional[int],
    anchor_time: float,
    measure: str,
    output: str = OUTPUT_PREFIX,
    *,
    input_fmt: Optional[str] = None,
    resolve_polytomy: Optional[str] = None,
    outgroup_check: Optional[str] = None,
    sampling_frac: Optional[float] = None,
) -> str:
    """生成 ddbd 子命令的等效 CLI 字符串。"""
    an_arg = f" --anchor-node {anchor_node}" if anchor_node is not None else ""
    at_arg = f" --anchor-time {anchor_time}" if anchor_node is not None else ""
    sf_arg = (
        f" --sampling-frac {sampling_frac}" if sampling_frac is not None else ""
    )
    return (
        f'openreltime ddbd -i "{tree_path}"'
        f"{_tree_input_args(outgroup, input_fmt, resolve_polytomy, outgroup_check)}"
        f"{an_arg}{at_arg}{sf_arg} --measure {measure} -o {output}"
    )

#: Pipeline order of the equivalent CLI script.  Replaying in this order is
#: what lets ``ci`` read the ``<prefix>_report.json`` written by the
#: ``calibrate`` step immediately before it.
CLI_STAGES = ("rates-times", "calibrate", "ci", "corrtest", "ddbd")


def cli_pipeline(commands: dict[str, str]) -> list[str]:
    """按流水线顺序返回已登记的命令。"""
    return [commands[stage] for stage in CLI_STAGES if stage in commands]


def build_cli_script(commands: Sequence[str]) -> str:
    """把等效 CLI 命令拼成可重放的 bash 脚本。

    脚本先 ``cd`` 到自身所在目录：GUI 导出的 ``calibrations.tsv`` 与
    ``-o openreltime_result`` 前缀都是相对该目录写出的，换目录重放会指向
    错误路径。
    """
    body = "\n".join(cmd for cmd in commands if cmd)
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'cd "$(dirname "$0")"\n'
        f"{body}\n"
    )


# ── 导出 ────────────────────────────────────────────────────────────────

def export_result(
    result: Any,
    prefix: str | Path,
    *,
    nexus: bool = True,
    with_rate: bool = True,
) -> list[Path]:
    """通用导出：调用 Result.write() 写出 CSV/NEXUS/JSON。"""
    if isinstance(result, TimeResult):
        return result.write(prefix, with_rate=with_rate, nexus=nexus)
    if isinstance(result, CalibratedResult):
        return result.write(prefix, nexus=nexus)
    if isinstance(result, CIResult):
        return result.write(prefix)
    if isinstance(result, CorrTestResult):
        return result.write(prefix)
    if isinstance(result, DDBDResult):
        return result.write(prefix)
    if isinstance(result, RateResult):
        return result.write(prefix)
    raise TypeError(
        i18n.t("adapter.unsupported_result_type", name=type(result).__name__)
    )


# ── 树信息摘要（供 UI 状态栏使用）────────────────────────────────────

def tree_summary(tree: PhyloNode) -> dict[str, Any]:
    """返回树的基本信息摘要。"""
    tips = tree.tips()
    internal = [n for n in tree.walk() if not n.is_tip()]
    return {
        "n_tips": len(tips),
        "n_internal": len(internal),
        "n_nodes": len(tips) + len(internal),
        "is_binary": tree.is_binary(),
        "tip_labels_sample": [t.label for t in tips[:5]],
    }


def result_summary(result: Any) -> dict[str, Any]:
    """返回分析结果的基本信息摘要。"""
    info: dict[str, Any] = {}
    if isinstance(result, TimeResult):
        info["analysis"] = "rrf_rates_times"
        info["n_nodes"] = len(result.times)
        info["n_rate_guarded"] = result.n_rate_guarded
        info["mean"] = result.params.get("mean", "geometric")
        info["normalize"] = result.params.get("normalize", False)
        if result.times:
            root_id = result.tree.node_id
            info["root_time"] = result.times.get(root_id, 0.0)
    elif isinstance(result, CalibratedResult):
        info["analysis"] = "calibrate"
        info["n_nodes"] = len(result.times)
        info["time_factor"] = result.time_factor
        info["n_calibrations"] = len(result.calibrations)
        info["method"] = result.params.get("method", "bounds")
        if result.warnings:
            info["warnings"] = result.warnings
    elif isinstance(result, CIResult):
        info["analysis"] = "confidence_interval"
        info["n_nodes"] = len(result.table)
        info["level"] = result.level
        # vS(b) 来源决定区间含义（位点数缺失时只剩速率异质性分量）
        info["v_s_source"] = result.params.get("v_s_source", "unknown")
    elif isinstance(result, CorrTestResult):
        info["analysis"] = "corrtest"
        info["score"] = result.score
        info["p_band"] = result.p_band
    elif isinstance(result, DDBDResult):
        info["analysis"] = "ddbd"
        info["birth_rate"] = result.birth_rate
        info["death_rate"] = result.death_rate
        info["sampling_frac"] = result.sampling_frac
    return info
