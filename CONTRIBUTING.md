# Contributing to OpenRelTime Studio

**Language: English** · [简体中文](#简体中文)

Thanks for considering a contribution! This document covers the local setup,
the checks every change must pass, and how releases are cut.

## Development setup

```bash
git clone https://github.com/ZengZichao/OpenRelTime-Studio.git
cd OpenRelTime-Studio

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
# The engine ships from its own repository; see
# https://github.com/ZengZichao/OpenRelTime/releases for the current tag.
# CI does not use this line: it installs the engine's `main` branch (see below),
# so pinning the tag here only makes your local pair reproducible.
python -m pip install "openreltime[plot] @ git+https://github.com/ZengZichao/OpenRelTime.git@v0.1.0"
python -m pip install -e ".[dev]"
```

Studio is a PySide6 desktop app. The tests run headless: on Linux install
`libegl1 libgl1 libxkbcommon0`, and export `QT_QPA_PLATFORM=offscreen`
(the CI workflow already does both).

## What CI runs, and against which engine

**Studio's CI runs the suite against the engine's development branch, not against
a frozen release tag.** `.github/workflows/ci.yml` sets `ENGINE_REF: main` and
installs `openreltime[plot] @ git+https://github.com/ZengZichao/OpenRelTime.git@main`.
That is deliberate: every number in the interface comes out of the engine, so the
144 Studio tests are the front end's early warning that an engine commit broke the
adapter — and with a tag pin that warning could only ever arrive after the engine
had already been released. Expect a red Studio build on an engine commit that
legitimately changes the public API; fix the adapter in the same window, and say so
in the engine's changelog.

`.github/workflows/release.yml` keeps `ENGINE_REF` on a tag, on purpose: a published
bundle must embed one specific, archivable engine version, so bump it by hand at
release time (checklist below).

The test matrix is `ubuntu-latest` × Python 3.10–3.13, `macos-latest` × 3.10–3.13
and `windows-latest` × 3.13. The Windows row exists because the manuscript says
Windows execution has not been automatically tested: the engine and Studio are pure
Python, PySide6 publishes Windows wheels, no step uses a command interpreter, and
every path is built with `pathlib`. It has **not been executed yet** — nothing here
can run a Windows job — so the next push is the verification. Two things it must
confirm: that Qt's `offscreen` platform plugin loads from the Windows wheel (that is
what lets the 46 `requires_qt` tests run headless), and that the locale default is
not used to read or write any packaged text; production code and tests name
`encoding="utf-8"` explicitly, which is why a new file write must too.

These 144 tests gate the front end — adapter wiring, packaging, localisation,
documentation hygiene and tree-layout geometry. They re-run no reference comparison
against the R3F golden files or the engine's validation gates, which live in the
engine repository, so a green Studio build is not evidence about the dating method.

## Checks every change must pass

All of these run in [CI](.github/workflows/ci.yml) on every push and pull
request, and the same commands work locally:

```bash
python -m ruff check . --select F,E9      # syntax and unused names
python -m mypy openreltime_studio         # static types
python tools/check_i18n.py                # bilingual catalog gate
QT_QPA_PLATFORM=offscreen python -m pytest -q --cov=openreltime_studio
python -m build && python -m twine check dist/*   # packaging
```

House rules the test suite enforces (see
`openreltime_studio/tests/test_docs_hygiene.py`):

- Documentation may not reference the engine as a local path; it is always an
  installed distribution or a URL to its repository.
- Neither distribution is on a package index, so docs must never tell users to
  `pip install` Studio by bare index name — point at the release assets or a
  source install instead.
- Shipped Markdown and Python may not contain internal revision markers.
- User-facing strings live in `openreltime_studio/locales/{en,zh}/`; the two
  catalogs must stay in lockstep (`tools/check_i18n.py`).

Test-suite rules (see [docs/testing.md](docs/testing.md) for the inventory and
the measured counts):

- Collection is never gated on an optional dependency. Mark the **test**, not
  the directory: `@pytest.mark.requires_qt` when it constructs a `QWidget`,
  `QPixmap`, `QSettings` or a Qt-backed canvas, `@pytest.mark.requires_engine`
  when it reaches `openreltime` — directly, through the adapter, or
  transitively through `MainWindow`. Both markers are registered in
  `pyproject.toml` and enforced by `openreltime_studio/tests/conftest.py`.
- A test module that imports the adapter or a widget at module level must call
  `_availability.require_engine()` / `require_qt()` **before** that import, so a
  missing dependency produces an explicit skip naming the cause and the fix
  rather than a collection error.
- Never turn a real assertion into an unconditional `pytest.skip`. The three
  placeholders in `test_regressions_studio.py` exist only because the behaviour
  belongs to the manual `smoke_gui.py` script; they name the check they defer to.

## Submitting changes

1. Fork / branch, keep one logical change per pull request.
2. Run the checks above; add or update tests for behavior changes.
3. Update `CHANGELOG.md` **and** `CHANGELOG-zh.md` for anything user-facing.
4. Open the pull request against `main`. CI must be green; merges are
   squash-only, so no history cleanup is needed on your side.

## Release checklist (maintainer)

1. Bump `version` in `pyproject.toml`.
2. Bump `CFBundleShortVersionString` in
   `openreltime_studio/resources/OpenRelTimeStudio.spec` to match. The release
   workflow stamps it from the tag by pattern, so a missed bump no longer breaks
   the build — but `--self-check` output and a locally built `.app` would report
   the previous version until the next tag.
3. Update `CHANGELOG.md` and `CHANGELOG-zh.md` (move the "Unreleased" notes
   under the new version).
4. Sync `ENGINE_REF` in [.github/workflows/release.yml](.github/workflows/release.yml)
   to the engine tag this release must embed, once the engine has published it.
   Leave `ENGINE_REF` in [ci.yml](.github/workflows/ci.yml) on the development
   branch — that is the point of that job.
5. Tag `vX.Y.Z` on `main` and push the tag — the release workflow builds the
   sdist/wheel and the macOS `.app` bundle, then attaches them to a release
   named after the tag.
6. Spot-check the attached assets, and confirm the wheel passes
   `openreltime-studio --self-check` in a clean venv.
7. When Zenodo mints the version record for that tag, update `CITATION.cff`: set
   `doi` to the **new version record's** DOI (it currently carries the
   version-agnostic concept DOI, because 0.1.1 has no version record yet) and set
   `date-released` to that record's publication date. Neither DOI is created from
   here; the record appears once the release exists.

## 简体中文

欢迎参与贡献！本地搭建、必须通过的检查与发版流程如下。

**开发环境**：克隆本仓库后建虚拟环境，先安装引擎发行版（当前 tag 见
<https://github.com/ZengZichao/OpenRelTime/releases>），再
`python -m pip install -e ".[dev]"`。GUI 测试可无头运行：Linux 需要
`libegl1 libgl1 libxkbcommon0`，并设 `QT_QPA_PLATFORM=offscreen`。

**每次改动必须通过**（与 [CI](.github/workflows/ci.yml) 相同的命令）：
`ruff check . --select F,E9`、`python -m mypy openreltime_studio`、
`python tools/check_i18n.py`、无头 `pytest`（带覆盖率）、`python -m build`
加 `twine check`。测试套件还会守住几条"文档卫生"规则：不得把引擎写成
本地路径；两个发行版都未上包索引，文档不得写裸索引安装命令；发布内容
不得带内部改版标记；界面文案只放在 `locales/{en,zh}/` 且两份目录必须同步。

**测试相关规则**（各文件覆盖范围与实测用例数见 `docs/testing.md` /
`docs/testing-zh.md`）：收集永远不依赖可选依赖——要标的是**用例**而不是
目录：构造 `QWidget`、`QPixmap`、`QSettings` 或 Qt 后端画布的标
`pytest.mark.requires_qt`，直接或间接（经 `MainWindow`）触到
`openreltime` 的标 `pytest.mark.requires_engine`；两个标记都注册在
`pyproject.toml`，由 `openreltime_studio/tests/conftest.py` 执行。模块顶部
要导入适配层或控件的测试文件，必须在导入**之前**调用
`_availability.require_engine()` / `require_qt()`，这样缺依赖时报的是点名
成因与修复命令的显式跳过，而不是收集错误。也不许把真断言改成为无条件的
`pytest.skip`：`test_regressions_studio.py` 里留下的 3 个占位用例，只是因为
对应行为归手工脚本 `smoke_gui.py` 验证，它们都写明了自己推迟到哪一条检查。

**CI 跑的是什么、对着哪个引擎**：Studio 的 CI 对着引擎的**开发分支**跑，不是对着
冻结的发布标签——`ci.yml` 里 `ENGINE_REF: main`，装的是引擎仓库的 `main`。这是故意的：
界面上每个数都出自引擎，144 个 Studio 用例就是前端唯一的早期预警，提醒某个引擎提交
弄坏了适配层；钉住标签的话，这个预警只可能在引擎已经发版之后才响。若引擎确实改了
公共 API，Studio 构建变红是预期结果，请在同一个时间窗内修好适配层，并在引擎的
changelog 里写明。`release.yml` 仍固定标签：对外发布的 bundle 必须内嵌一个确定的、
可存档的引擎版本，发版时手工同步（见下面的清单）。测试矩阵是 `ubuntu-latest` ×
Python 3.10–3.13、`macos-latest` × 3.10–3.13 与 `windows-latest` × 3.13。加
Windows 那一行，是因为手稿写着 Windows 上的执行未经自动化测试：引擎与 Studio 都是
纯 Python，PySide6 发布 Windows 轮子，没有任何步骤走命令解释器，路径一律由
`pathlib` 组装。该行**尚未真正跑过**（本机无法运行 Windows 作业），下一次 push
就是验证。它要确认两件事：Qt 的 `offscreen` 平台插件能从 Windows 轮子里加载（那 46
个 `requires_qt` 用例靠它才能无头运行），以及打包文本不会用系统区域默认编码读写
——生产代码与测试都显式写 `encoding="utf-8"`，新增的文件写入也必须这样。
这 144 个用例管的是前端：适配层接线、打包、翻译、文档卫生与树形几何。它们不重跑
任何对照 R3F golden 文件或引擎验证门的比对（那些在引擎仓库里），因此 Studio 构建全绿
**不是**关于测年方法本身的证据。

**提交方式**：一个 PR 一个逻辑改动；面向用户的变更要同时更新
`CHANGELOG.md` 与 `CHANGELOG-zh.md`；PR 打向 `main`，CI 全绿后 squash
合入，无需自行整理提交历史。

**发版清单**：升 `pyproject.toml` 的 `version`；把 spec 里的
`CFBundleShortVersionString` 升到同一版本（release 工作流现在按模式匹配从标签改写
它，漏升不再让构建失败，但在下一个标签之前，本地产物与手工构建的 `.app` 会报旧版）；
更新两份 CHANGELOG；引擎发了新标签后，把 `release.yml` 的 `ENGINE_REF` 同步到该次要
内嵌的标签，而 `ci.yml` 的 `ENGINE_REF` 保持在开发分支上——那正是那个 job 的意义；
在 `main` 上打 `vX.Y.Z` 并推送 tag，release 工作流会自动构建 sdist/wheel 与 macOS
`.app` 包并挂到同名 Release；最后在干净虚拟环境里抽查资产并通过
`openreltime-studio --self-check`。等 Zenodo 为该标签生成了版本记录，再更新
`CITATION.cff`：把 `doi` 换成**新版本记录**的 DOI（现在写的是与版本无关的 concept
DOI，因为 0.1.1 还没有版本记录），并把 `date-released` 对齐该记录的发布日期；两边
的 DOI 都不是从本地生成的，记录要等 Release 真的存在才会出现。
