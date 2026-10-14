# Studio 测试套件

**语言：简体中文** · [English](testing.md)

说明 `openreltime_studio/tests/` 各自覆盖什么、在一台没有 GUI 绑定的机器上
能跑到多少，以及哪些数字可以对外引用。本页所有数字都是**实测**得到的，不是
推断出来的；命令见 §5。

套件共 **144 个测试**。它不是「144 个适配器测试」：真正的适配器测试只有
`test_adapter.py` 的 19 个，其余覆盖打包、随包资源、文档、双语目录、界面背后
的逻辑，以及界面本身。

## 1. 文件 → 测试数 → 类别

| 文件 | 测试数 | 类别 | 覆盖内容 |
| --- | --- | --- | --- |
| `test_adapter.py` | 19 | adapter（适配层） | 把引擎 Result 对象转成界面模型的隔离层：格式识别、读树、等效 CLI 命令串生成、`Calibration` 构造、结果摘要、ddBD 节点密度数组。需要引擎，完全不碰 Qt。 |
| `test_bundled_example.py` | 25 | packaging（打包与随包资源） | 内置示例是否**真的随包发行**（示例树、校正表、README 免责声明）、能否整条流水线跑通，以及两套图标变体是否都在包内、是否按尺寸正确挑选。其中 8 个既不依赖 Qt 也不依赖引擎，3 个只调引擎，14 个要构造 Qt 对象（这 14 个里有 4 个还同时需要引擎，因为主窗口会导入适配层）。 |
| `test_docs_hygiene.py` | 6 | docs-hygiene（文档卫生） | 全仓库 Markdown/Python 规则：不得出现越出仓库的路径、引擎只能以已安装的发行版或仓库 URL 提及、本地链接必须指向真实文件、README 必须写明两个发行版的 Release 资产、不得写裸索引安装命令、发布内容不得带内部改版标记。 |
| `test_i18n_catalogs.py` | 9 | i18n（双语目录静态检查） | 直接从源码读出的目录规则：目录之外不许残留中文字符串字面量、主题与图标模块之外不许硬编码十六进制颜色、源码引用的每个键在**两种语言**里都存在、两种语言键集合一致、`{placeholder}` 集合一致、不留无人引用的键。 |
| `test_regressions_studio.py` | 55 | studio-logic（界面逻辑与契约回归） | 三类手段并行：真跑适配层与引擎命令行（`openreltime.cli`）的选项契约；用 `ast` 回读 Qt 源码，静态证明某种写法已经消失；对只能在真实部件上验证的行为给出**显式 skip**，并指向手工冒烟脚本里对应的检查。 |
| `test_tree_orientation.py` | 15 | tree-layout（树形几何与朝向） | 每个尖都有一条落在自己那一行的末端分支、连接线落在父节点分歧时刻、非根节点恰好贡献两条线段、四个朝向都能画、选择经 `QSettings` 持久化、尖标签贴在靠尖那一侧坐标轴上。 |
| `test_ui_localization.py` | 15 | live-UI（实时界面切换） | 真的构造主窗口，**不重启进程**切换语言与主题，验证分组框标题、标签页、状态栏、菜单动作与样式表当场改变，偏好往返 `QSettings`，四种「语言 × 主题」组合下窗口都能建起来。 |
| **合计** | **144** | | |

有两个依赖会门控这些文件，而且门控的对象并不相同：

| 依赖 | 需要它的测试数 | 原因 |
| --- | --- | --- |
| `openreltime`（引擎） | 104 | 适配层是 Studio 唯一的计算入口，而 `MainWindow` 会导入适配层。 |
| `PySide6`（Qt 绑定） | 46 | 只有真的构造 `QWidget`、`QPixmap`、`QSettings`，或在 Qt 后端上创建 matplotlib 画布的用例才需要。 |
| 两者都不需要 | 26 | 打包与随包资源检查、文档卫生、双语目录静态检查，以及混合文件里只读常量的那几个用例。 |

## 2. 收集是如何门控的

门控粒度是**单个测试**，不是目录。仓库根的 `conftest.py` 不再因为缺 GUI
extra 就把整个测试目录丢掉；它只在任何东西导入 Qt 之前导出
`QT_QPA_PLATFORM=offscreen`。两个标记注册在 `pyproject.toml`
（`[tool.pytest.ini_options] markers`），并由
`openreltime_studio/tests/conftest.py` 负责执行：

| 标记 | 加在谁身上 | 缺依赖时的行为 |
| --- | --- | --- |
| `pytest.mark.requires_qt` | 构造 Qt 对象的用例，以及整个 `test_tree_orientation.py` | 该用例被**显式跳过**，跳过理由里给出失败的那条 import 与安装命令 |
| `pytest.mark.requires_engine` | 调用适配层（含经由 `MainWindow` 间接调用）或直接调用引擎的用例 | 该用例被**显式跳过**，理由里给出失败的那条 import 与两条修复路径 |

在模块顶部就导入适配层的文件（`test_adapter.py`、`test_regressions_studio.py`、
`test_tree_orientation.py`）改在模块顶部调用 `_availability.require_engine()`，
于是报出的是「一条模块级跳过」而不是每条测试各报一次；不这样做的话，光是那行
导入就会抛异常，整场 run 以收集错误收场。理由里点名的成因与修复完全相同。

`require_qt()` 则**刻意不**这样用。PySide6 可能「能导入但用不了」——没有窗口
会话，或同一进程里加载了两套 Qt 构建——此时若做模块级跳过，整个文件会被折叠成
一行，头条测试数就会随机器而变。所以 Qt 一律经 `requires_qt` 标记按条跳过，
这正是 `test_tree_orientation.py` 报出十五条跳过而非一条的原因。

**于是「收集到多少」取决于引擎，而不是 GUI 绑定。** 只要 `openreltime` 能被
导入，任何机器上都会收集满 **144** 个，装不装 PySide6、装了但用不用得上都一样。
引擎导不出来时，同一条命令收集到 **55** 个用例加 3 条模块级跳过，既不会归零，
也不会因为缺依赖而变成收集错误：

| 引擎可导入 | 收集 | 组成 |
| --- | --- | --- |
| 是 | **144** | 144 个用例，无模块级跳过 |
| 否 | **58** | 55 个用例 + 3 条模块级跳过（`test_adapter.py`、`test_regressions_studio.py`、`test_tree_orientation.py`） |

GUI 绑定改变的是 144 个里**有多少真的运行**。`_availability.py` 里的探测不止
`import PySide6`：它另起一个子进程真的去构造 `QApplication`，因为 Qt 在没有可用
会话时是直接 abort 整个进程而不抛异常的。所以「Qt 可用」的意思是「这台机器跑得
起窗口会话」，跑不起时那 46 个标了 `requires_qt` 的用例逐个显式跳过，理由里点名
失败的那条 import 或 abort 的插件。

跳过绝不静默。`pytest_report_header` 会打印两个探测结果（`-v` 下可见），
`pytest_terminal_summary` 在 run 结尾再喊一次（默认的 `-q` 会省掉头部）：

```
gating: qt: PySide6: ABSENT -> 'requires_qt' SKIP; fix: python -m pip install "PySide6>=6.5"
gating: engine: openreltime: NOT importable -> 'requires_engine' SKIP(...); fix: ...
gating: 32 skipped because a capability is missing (run with -rs for the per-test reason; failures=0)
```

`addopts` 里还带 `--strict-markers`：门控标记写错字时整个 run 直接失败，而不是
退化成「被收集但永远不会跳过」。

只要 Qt 绑定能导入，会话级 `QApplication`（Fusion 风格）就会自动建好——没有
它就构造 `QWidget`，进程会直接 abort。真的需要它的用例显式请求 `qapp` 夹具；
Qt 缺席时该夹具带着上面的理由跳过。

## 3. 运行

```bash
python -m pip install -e ".[dev]"                 # pytest、ruff、mypy、覆盖率
python -m pip install "openreltime[plot] @ git+https://github.com/ZengZichao/OpenRelTime.git@v0.1.0"
QT_QPA_PLATFORM=offscreen python -m pytest -q     # 全部
python -m pytest -q -rs                           # 再加每条跳过的具体原因
python -m pytest -q -m "not requires_qt"          # 只跑不需要 GUI 绑定的
python -m pytest --pyargs openreltime_studio.tests   # 针对已安装的发行版
```

`-m "not requires_qt"` 是按标记筛除。注意上面那三个整模块门控的文件仍然会被
导入，所以它们需要引擎；两者都缺的机器上请用
`-m "not requires_qt and not requires_engine"`，或者直接点名目录检查与文档
检查那两个文件。

CI 工作流会装齐两个依赖，因此 CI 跑满 144 个——但引擎是从**开发分支**装的，
不是从冻结的发布标签：`.github/workflows/ci.yml` 里 `ENGINE_REF: main`，
安装的是 `openreltime[plot] @
git+https://github.com/ZengZichao/OpenRelTime.git@main`，所以引擎里改动适配层的
提交当天就会在 Studio 的 CI 上失败，而不是等到下一个引擎版本发布。
`.github/workflows/release.yml` 则刻意保留标签固定值，因为对外发布的 bundle 必须
内嵌一个可存档的确定引擎版本。矩阵是 `ubuntu-latest` × 3.10–3.13、
`macos-latest` × 3.10–3.13 与 `windows-latest` × 3.13，全部设
`QT_QPA_PLATFORM=offscreen`。

有一个 job 刻意在缺两个依赖的环境里跑，这正是检验门控是否诚实的地方：
`i18n-symmetry` **只**装 `pytest`——不装 PySide6、不装引擎、不装 `dev`
extra——执行 `python -m pytest openreltime_studio/tests/test_i18n_catalogs.py -q`。
用完全相同的命令实测，它收集并通过的就是那 **9** 个目录测试，别无其他。

## 4. `smoke_gui.py`：手工脚本，不是测试

`openreltime_studio/tests/smoke_gui.py` 在离屏环境下驱动**真正的**主窗口走完
每个阶段（载入 → RRF → 校正 → ddBD → CI），逐阶段截图到 `.smoke_out/`，并对
自动化套件只能静态断言的行为做硬检查：校正点标记在交互增删后必须留在画布上、
点过「取消」的校正结果不得被应用、格式下拉框的取值必须真的决定读树方式。

手工运行（在项目根目录）：

```bash
QT_QPA_PLATFORM=offscreen python openreltime_studio/tests/smoke_gui.py
```

全部检查通过时打印 `SMOKE OK` 并以 0 退出；任何一条失败都会打印并以非 0 退出。
它**永远不参与收集**，两道防线：

1. `openreltime_studio/tests/conftest.py` 里的 `collect_ignore`；
2. 脚本自身顶部的导入守卫——一旦它作为非 `__main__` 的模块被导入就抛
   `RuntimeError`，并把上面那条正确用法写进报错里。因此即便有人显式执行
   `python -m pytest openreltime_studio/tests/smoke_gui.py`，也会响亮地失败，
   而不是「收集到 0 个用例」看起来一片绿。

## 5. 五种环境下的实测数字

以下均在仓库根目录、`PYTHONDONTWRITEBYTECODE=1`、`-p no:cacheprovider` 下实测：
(a)–(d) 用 `pytest --junitxml`，(a2) 用终端摘要加上表后给出的按标记筛选计数。
「依赖缺失」没有通过卸载任何东西来模拟：

* **缺 PySide6**：在 `PYTHONPATH` 最前面放一个桩包
  `/tmp/qtblock/PySide6/__init__.py`（以及 `shiboken6`），它抛
  `ModuleNotFoundError`，从而遮蔽已安装的绑定。同时加 `-p no:pytest-qt`，
  因为 `pytest-qt`（本项目的**声明依赖里没有它**）在任何绑定都导不出来时拒绝
  启动。
* **缺引擎**：`openreltime` 不在 `PYTHONPATH` 上——这与任何没装引擎发行版的
  机器状态完全一致。

| 环境 | 依赖 | 收集 | 通过 | 跳过 | 退出码 |
| --- | --- | --- | --- | --- | --- |
| (a) | PySide6 + 引擎，且 Qt 会话可用 | **144** | 141 | 3 | 0 |
| (a2) | PySide6 + 引擎，**但没有可用的 Qt 会话** | **144** | **98** | **46** | 0 |
| (b) | 只有引擎（无 PySide6） | 130 条（129 个用例 + 1 条模块级跳过） | **98** | 32 | 0 |
| (c) | 只有 PySide6（无引擎） | 58 条（55 个用例 + 3 条模块级跳过） | **40** | 18 | 0 |
| (d) | 两者都缺 | 58 条（55 个用例 + 3 条模块级跳过） | **26** | 32 | 0 |

(a) 里的 3 个跳过是 `test_regressions_studio.py` 中刻意留下的占位用例，它们把
行为交给手工冒烟脚本（`test_marks_visible_after_interactive_edit`、
`test_cancel_during_bounds_run_is_dropped`、`test_gui_has_no_rate_worker`）。

(b) 的分文件结果：`test_adapter.py` 19/19、`test_docs_hygiene.py` 6/6、
`test_i18n_catalogs.py` 9/9、`test_regressions_studio.py` 50/55、
`test_bundled_example.py` 11/25、`test_ui_localization.py` 3/15、
`test_tree_orientation.py` 0/15（一条模块级跳过）。(c) 的分文件结果：
`test_docs_hygiene.py` 6/6、`test_i18n_catalogs.py` 9/9、
`test_bundled_example.py` 18/25、`test_ui_localization.py` 7/15，另有
`test_adapter.py`、`test_regressions_studio.py`、`test_tree_orientation.py` 各
一条模块级跳过。

(a2) 就是「无显示器、且 Python 前缀里装着两套 Qt」的机器实际落在的环境，也是
对本仓库之外引用这些数字时所用的环境：PySide6 能导入，但 `_availability` 的子进程
探测构造不出 `QApplication`，于是 46 个 `requires_qt` 用例逐个跳过、其余照跑——
收集 144、通过 98、跳过 46、退出码 0，且 144 − 46 = 98。写下本节这台机器
（Python 3.11，PySide6 6.11.2 可导入但构造 `QApplication` 时 abort，引擎由
`PYTHONPATH` 提供）重新实测的结果是：

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest --collect-only -p no:cacheprovider -o addopts="--strict-markers"
# 144 tests collected in 0.45s
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -o addopts="--strict-markers"
# 98 passed, 46 skipped in 4.10s
PYTHONDONTWRITEBYTECODE=1 python -m pytest -m requires_qt --collect-only -p no:cacheprovider -o addopts="--strict-markers"
# 46/144 tests collected (98 deselected)          <- 按标记数出的跳过条数
PYTHONDONTWRITEBYTECODE=1 python -m pytest -m requires_engine --collect-only -p no:cacheprovider -o addopts="--strict-markers"
# 104/144 tests collected (40 deselected)
```

有两行带着这次复测暴露出的注意事项，之所以保留在表里而不是删掉，是因为它们记录的是
套件设计上的目标行为：

* **(a)** 需要一台 `QApplication` 真能构造起来的机器——只装一套 Qt，或者按下面
  那几行 `QT_PLUGIN_PATH` 导出设置。在上面这台机器上，(a) 会退化成 (a2)。
* **(b)** 当初实测是干净的 130/98/32。用同一个 `/tmp/qtblock` 桩包在这里复现时，
  结尾却是**收集错误**：`test_tree_orientation.py` 要导入
  `openreltime_studio.widgets.tree_canvas`，而该模块顶部的
  `from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg` 在任何绑定都
  导不出来时会抛 `ImportError: Failed to import any of the following Qt binding
  modules`，这一步发生在任何标记来得及跳过之前（收集到 129 个用例，run 中断，
  退出码 2）。所以 (b) 的分文件数字只有在那次导入还能撑住的机器上才拿得到；
  本机对同一环境的诚实表述是「收集 129，另有 1 条收集错误」。该问题要改的是测试
  文件而不是文档，这里刻意不动，因为它会改变本节另一处在守护的收集语义。

有一条本地环境注意事项值得记下来，因为它花掉一轮调试：如果某个 Python 前缀里
同时装着**两套** Qt——conda 的 `qt-main` 包与 pip 装的 `PySide6` 并存——
`QApplication` 会在构造时 abort，报
`Could not load the Qt platform plugin "offscreen"`，原因是插件目录被解析到了
另一套 Qt 的副本，同一个进程里出现两个 `QtCore`。这是环境问题而不是测试问题
（改动前的仓库在同样条件下 abort 得一模一样），上面的几次运行靠把 Qt 指向绑定
自带的插件目录绕开：

```bash
QT_PLUGINS="$(python -c 'import PySide6, os; print(os.path.join(os.path.dirname(PySide6.__file__), "Qt", "plugins"))')"
export QT_PLUGIN_PATH="$QT_PLUGINS"
export QT_QPA_PLATFORM_PLUGIN_PATH="$QT_PLUGINS/platforms"
```

CI 只从 wheel 安装 `PySide6`，不会遇到这个问题；这几行不属于测试套件，因此
刻意没有写进 `conftest.py`。

复现命令：

```bash
# (a) 完整套件，与 CI 完全一致
QT_QPA_PLATFORM=offscreen PYTHONPATH="<引擎源码检出根目录>" \
  python -m pytest -q --junitxml=report-a.xml

# (a2) 同样一条命令，只是换到一台构造不出 QApplication 的机器上——也就是同时
# 装着两套 Qt 构建的前缀默认就会落到的环境，即不套用上面 QT_PLUGIN_PATH 导出
PYTHONPATH="<引擎源码检出根目录>" python -m pytest -q

# (b) 无 GUI 绑定：用桩包遮蔽已安装的 PySide6
PYTHONPATH="/tmp/qtblock:<引擎源码检出根目录>" \
  python -m pytest -q -p no:pytest-qt --junitxml=report-b.xml

# (c) 无引擎：无需模拟，它本来就导不出来
QT_QPA_PLATFORM=offscreen python -m pytest -q --junitxml=report-c.xml

# (d) 两者都缺
PYTHONPATH="/tmp/qtblock" python -m pytest -q -p no:pytest-qt --junitxml=report-d.xml
```

## 6. 可以对外引用的表述

下面每个数字都带着它是在哪种环境下量出来的：只有「收集到多少」在装好引擎的机器
上是恒定的，「跑掉多少」始终取决于 Qt 会话。

* Studio 套件是 **144 个测试**：19 个适配层测试、25 个内置示例与图标的打包
  测试、6 个文档卫生测试、9 个双语目录测试、55 个界面逻辑回归测试、
  15 个树形几何测试、15 个实时界面测试。
* 只要引擎发行版 `openreltime` **可以被导入**，144 个就全部被收集，
  与 GUI 绑定装没装、装得上用不用得上都无关。引擎导不出来时，同一条命令
  收集到 55 个用例加 3 条显式的模块级跳过：套件既不会整体消失，也不会
  仅仅因为缺依赖就以收集错误收场。
* Qt 绑定可用且引擎已安装时 **144 个全部运行**（141 通过，3 个把行为交给手工
  离屏冒烟脚本）。
* **引擎已装但没有可用 Qt 会话时，98 个运行、46 个显式跳过**——这 46 个正是
  标了 `requires_qt` 的用例，逐个跳过、理由里点名成因与修复命令；不会折叠成
  一条模块级跳过，所以头条数字不随机器漂移。
* **两个依赖都没有时仍有 26 个运行**（收集 58：55 个用例 + 3 条模块级跳过，
  跳过 32）；其余跳过，理由里点名缺的是哪一次 import。
* 这 144 个用例管的是**前端**：适配层把引擎结果换算成界面模型、示例与图标
  随包发行、双语目录保持同步、文档遵守仓库规则、界面契约不回归、树按正确
  几何画出来。它们**不重跑任何参照比对**：本套件里没有任何用例拿界面上的数字
  去对照 R3F golden 文件或引擎的验证门（那些都在引擎仓库）。因此报告这套件的
  数字只说明前端接线、打包与翻译是对的，**不是**任何测年方法数值主张的证据。

## 7. 另见

* 使用手册 §10.3 把这些命令放回了开发流程的上下文里：本目录下的
  `usage-en.md`（中文手册是 `usage-zh.md`）。
* 项目根目录的 `CONTRIBUTING.md` 列出每次改动必须通过的检查。
