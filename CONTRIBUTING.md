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
python -m pip install "openreltime[plot] @ git+https://github.com/ZengZichao/OpenRelTime.git@v0.1.0"
python -m pip install -e ".[dev]"
```

Studio is a PySide6 desktop app. The tests run headless: on Linux install
`libegl1 libgl1 libxkbcommon0`, and export `QT_QPA_PLATFORM=offscreen`
(the CI workflow already does both).

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

## Submitting changes

1. Fork / branch, keep one logical change per pull request.
2. Run the checks above; add or update tests for behavior changes.
3. Update `CHANGELOG.md` **and** `CHANGELOG-zh.md` for anything user-facing.
4. Open the pull request against `main`. CI must be green; merges are
   squash-only, so no history cleanup is needed on your side.

## Release checklist (maintainer)

1. Bump `version` in `pyproject.toml`.
2. Bump `CFBundleShortVersionString` in
   `openreltime_studio/resources/OpenRelTimeStudio.spec`.
3. Update `CHANGELOG.md` and `CHANGELOG-zh.md` (move the "Unreleased" notes
   under the new version).
4. If the engine published a new tag, sync `ENGINE_REF` in both
   [.github/workflows/ci.yml](.github/workflows/ci.yml) and
   [.github/workflows/release.yml](.github/workflows/release.yml).
5. Tag `vX.Y.Z` on `main` and push the tag — the release workflow builds the
   sdist/wheel and the macOS `.app` bundle, then attaches them to a release
   named after the tag.
6. Spot-check the attached assets, and confirm the wheel passes
   `openreltime-studio --self-check` in a clean venv.

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

**提交方式**：一个 PR 一个逻辑改动；面向用户的变更要同时更新
`CHANGELOG.md` 与 `CHANGELOG-zh.md`；PR 打向 `main`，CI 全绿后 squash
合入，无需自行整理提交历史。

**发版清单**：升 `pyproject.toml` 的 `version`；升 spec 里的
`CFBundleShortVersionString`；更新两份 CHANGELOG；若引擎发了新 tag，
同步两份 workflow 里的 `ENGINE_REF`；在 `main` 上打 `vX.Y.Z` 并推送 tag，
release 工作流会自动构建 sdist/wheel 与 macOS `.app` 包并挂到同名
Release；最后在干净虚拟环境里抽查资产并通过 `--self-check`。
