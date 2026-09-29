# 版本记录

**语言：中文** · [English](CHANGELOG.md)

**OpenRelTime Studio** 的所有重要变更都记录在此。格式遵循
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/)，版本号遵循
[语义化版本 Semantic Versioning](https://semver.org/spec/v2.0.0.html)。

## 0.1.0 — 2026-09-29

OpenRelTime Studio 是一个用于相对速率分子测年的原生桌面应用程序（基于
PySide6，不依赖浏览器）。它不需要打开终端，自身也不携带任何算法：界面上的每
一个数字都由已安装的 `openreltime` 发行版通过其公共 Python API 产生，而这些
调用只发生在一个地方——适配层
`openreltime_studio/adapters/openreltime_adapter.py`——因此在图形界面里完成的
一次分析可以在命令行上精确复现。要求 Python ≥ 3.10；以 GPL-3.0-or-later 发布。

### 新增

- **树的读入。** 支持 Newick 与 NEXUS 年代树，在后台线程中读取，入口为
  **「文件 ▸ 打开树文件…」**（`Ctrl+O`）或 **「导入」** 分组的 **树文件**
  那一行。「导入」分组同时提供引擎会消费的读树设置：外类群（逗号分隔，可留
  空）、文件格式（`newick` / `nexus`）、多岔处理（`error` / `random`）与外群
  校验（`error` / `warn`）；格式按扩展名自动检测，也可以手动改正。

- **RRF 测年。** 在 **RRF** 标签页上计算相对进化速率与相对分歧时间，可选几何
  均值或算术均值、可选归一化，以及速率比守卫（阈值 20，可以关闭）。

- **交互式校正。** 在树上点击一个内部节点、填入以 Mya 为单位的下界和（或）上
  界即可添加校正点，还可指定密度类型（`uniform`、`exponential`、`normal`、
  `lognormal`）及其 `key=value;…` 参数；以 `taxon_set` 为目标的校正点会解析到
  该单系群的 MRCA，重复点击同一节点会替换它的校正点。校正点也可以从 TSV 文件
  载入。绝对时间由 **校正** 标签页给出，方法为 `bounds`，或重复抽样的
  `effective`（抽样次数 2–100 000，默认 10 000，可选固定随机种子）。

- **置信区间。** 在 **CI** 标签页上给出节点年龄的置信区间，以误差棒图呈现，置信
  水平可选 0.95（默认）、0.90 或 0.99，可指定逐分支方差（以 TSV 文件给出）与可选
  的位点数（默认 1 000）；未指定位点数时区间只包含速率异质性分量，CI 标签页上会
  明确写出这一点。

- **CorrTest。** 全树速率自相关检验——CorrScore、P 值区间、ρ_s 与 ρ_ad 及其衰
  减——支持姊妹群重抽样、可选固定随机种子，以及可选的锚定节点与锚定时间。

- **ddBD。** 密度依赖出生–死亡分化树先验，度量方式为 `SSE` 或 `KL`，可锚定，
  在画布上以节点时间直方图加拟合密度曲线呈现。

- **后台线程、进度与取消。** 上述每个阶段都运行在 `QThread` 中
  （`openreltime_studio/workers/analysis_workers.py`），因此界面不会卡死；校正
  阶段会回报进度、可以被取消，而**被取消的结果会被丢弃而不予应用**。引擎告警
  由 `openreltime` logger 收集，显示在窗口内的警告面板里，并带一个计数徽标。

- **可调整朝向的矩形树画布。** 一棵按时间刻度的矩形树，分支按速率着色，并画
  出校正标记与 CI 误差棒；在 **「视图 ▸ 根节点方向」** 下可把根放在左（默认）、
  右、上、下——翻转的是时间轴而刻度值仍然真实，尖标签始终贴着尖那一侧，且当前
  视图会直接重画，不需要重新分析。

- **结果视图。** 一份只读的**节点表**，逐节点列出结果并翻译表头；表格上方的
  摘要行承载最近一次完成的分析的关键数字（包括 CorrTest 与 ddBD 的结果）；
  状态栏则报告已经发生了什么、正在发生什么。

- **导出。** **「文件 ▸ 导出结果…」**（`Ctrl+E`）会把结果写进所选目录：以固定
  前缀 `openreltime_result` 写出的引擎结果集（CSV 表格、适用时的 NEXUS 树，
  以及 JSON 报告；对校正结果，JSON 报告还会记录树文件路径、校正文件、外类群
  与读树设置）、一张 200 dpi 的画布 PNG（按画布当前内容命名为 `timetree.png`、
  `ci.png`、`corrtest.png` 或 `ddbd.png`）、当被导出的流程含校正或 CI 步骤时
  的 `calibrations.tsv`，以及一个可执行的 `run_reltime.sh`。

- **等效命令行。** 一个面板，把你走过的每一步照原样写成对应的 `openreltime`
  命令，按流程顺序排列，并明确写出 `--fmt`、`--resolve`、`--outgroup-check` 与
  绝对的 `-i` 路径；一键即可复制，导出的脚本能在集群上重放整次会话。

- **内置示例。** **「文件 ▸ 打开内置示例…」**（`Ctrl+I`）从包内
  （`openreltime_studio/examples/`）载入一棵 24 尖的有袋类 + 单孔类年代树和三条
  演示校正点，因此不必自备数据就能把 RRF → 校正 → CI → CorrTest → ddBD → 导出
  的完整流程走一遍；示例中的校正边界只是演示用的假想数值，不是已发表的定年结论。

- **完整的英文 / 中文本地化。** 每一个菜单、标签、提示气泡、占位文本、表格
  标题、状态消息、进度对话框与消息框都由按命名空间划分的 JSON 目录
  （`locales/en`、`locales/zh`）解析，并可在 **「视图 ▸ 语言」** 下即时切换：动态
  文本会重新渲染，画布会重画——不必重启，也不必重新分析。

- **浅色与深色主题。** 所有颜色都是 `themes.py` 里的设计令牌（`LIGHT` /
  `DARK`），由一份共用的样式表模板与配套的 `QPalette` 消费；画布在绘制时重新
  读取自己的颜色，因此分支着色、校正标记、CI 误差棒与 ddBD 密度图在深色模式
  下依旧清晰。可在 **「视图 ▸ 主题」** 下即时切换。

- **记住的偏好。** 语言、主题与根节点方向，上次的树目录、校正目录与导出目录，
  以及窗口几何信息都存放在 `QSettings("OpenRelTime", "Studio")` 里，启动时恢复；
  首次启动为浅色 + 英文 + 根在左。

- **矢量应用图标。** `resources/icons/OpenRelTime-Studio.svg` 是唯一权威来源，
  由 `appicon.py` 经 `QtSvg` 栅格化为多尺寸 `QIcon`（16–512 px），并在
  `QtSvg` 不可用时回退到 `QPainter`；64 px 及以下会自动选用简化变体
  `OpenRelTime-Studio-symbolic.svg`，`icon.png` / `icon.icns` 由
  `resources/make_icon.py` 重新生成。

- **退出保护。** 仍有计算在跑时关闭窗口会先询问，默认答案是 **No**。

- **翻译门禁。** `tools/check_i18n.py` 与
  `openreltime_studio/tests/test_i18n_catalogs.py` 会在构建失败以下情况：控件代码
  里残留硬编码的中文字面量、`themes.py` 之外硬编码的颜色、任一语言里缺失的键、
  两种语言不匹配的 `{placeholders}`，以及目录里无人引用的键。

- **文档。** 成对发布、互为对照的英文 / 中文用户手册
  （[usage-en.md](docs/usage-en.md) ·
  [usage-zh.md](docs/usage-zh.md)）、本版本记录，以及
  [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md)，各自都有对应的中文版。

- **打包。** `openreltime-studio --self-check`：一个不开窗口的检查，确认消息目录、
  内置示例文件与两个图标变体都能在**已安装的包内**解析到；以及 PyInstaller 脚本
  `openreltime_studio/resources/OpenRelTimeStudio.spec`，它把双语消息目录、图标与
  内置示例打进包内，强制 `console=False`，并设置包标识符 `org.openreltime.studio`，
  用于构建双击即用的 macOS 应用。

- **测试套件。** 适配层、消息目录、回归测试、本地化、树形朝向、内置示例与文档
  卫生测试，可用 `QT_QPA_PLATFORM=offscreen python -m pytest` 无头运行；另有
  `openreltime_studio/tests/smoke_gui.py`，它在离屏环境下驱动真正的主窗口走完每
  个阶段。
