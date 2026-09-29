# Bundled example / 内置示例

**Language:** English · [中文](#中文)

## English

The two files in this directory ship with the application. They are exactly
what **File ▸ Open Bundled Example…** (Ctrl+I) and the **Bundled example…**
button on the import panel load — both an installed copy and the frozen `.app`
read them from inside the package, so nothing depends on a repository path.

| File | Contents |
| --- | --- |
| `example_tree.nwk` | A 24-tip timetree of marsupials and monotremes, with branch lengths |
| `example_calibrations.tsv` | Three calibration points, in the engine's calibration-file format |

Use it to walk the whole workflow without hunting for data first: load → RRF →
calibrate → confidence intervals → CorrTest / ddBD → export, and watch how the
equivalent command line is generated alongside.

> **The calibration bounds are illustrative hypothetical constraints.** They
> exist only to show how `min_bound` / `max_bound` are written and take effect.
> They are **not** published dating conclusions — do not use them for analysis
> or citation.

All three calibrations are given as a `taxon_set` (two tip labels forming a
complete monophyletic group), so they stay valid even if the tree's node
numbering changes. Running the `bounds` method with them yields a root age of
roughly 126 Mya.

## 中文

这里的两个文件随软件一起发行，是 **文件 ▸ 打开内置示例…**（Ctrl+I）和导入面板上
**内置示例…** 按钮实际读取的文件——安装版与冻结打包的 `.app` 都从包内取用，
不依赖仓库里的任何路径。

| 文件 | 内容 |
| --- | --- |
| `example_tree.nwk` | 24 尖的有袋类 + 单孔类年代树（带分支长度） |
| `example_calibrations.tsv` | 3 条校正点，格式与引擎的校正文件规范一致 |

用途：不找数据就能立刻走完全流程——载入 → RRF → 校正 → 置信区间 →
CorrTest / ddBD → 导出，并观察「等效命令行」如何随之生成。

> **校正边界是演示用的假想约束**，只为展示 `min_bound` / `max_bound` 的写法与
> 生效方式，**不是**已发表的定年结论，请勿用于任何分析或引用。

三条校正都写成 `taxon_set`（两个尖标签构成的完整单系群），因此即使树的节点
编号变化也仍然有效。用它们跑 `bounds` 方法可得到约 126 Mya 的根龄。
