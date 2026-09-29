"""文档卫生检查：Studio 与引擎是两个独立仓库，文档不得用本地路径互相引用。

``test_no_relative_paths_outside_repo`` 拦住 ``../`` 之类的越界引用；
``test_engine_referenced_as_distribution_only`` 拦住把引擎写成本地目录
（例如 ``OpenRelTime-项目代码``、``../../openreltime``）的说法。

``test_no_revision_provenance_markers`` 拦的是另一类东西：内部改版记录或
同行评审痕迹（工单号、评审轮次、投稿清单标记）不得进入发布出去的源码或
文档，也不得在之后被重新写回来。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MARKDOWN = sorted(REPO_ROOT.glob("**/*.md"))
PYTHON_SOURCES = sorted(REPO_ROOT.glob("**/*.py"))

#: 只有在源码检出里才谈得上文档卫生：安装版没有 README/docs。
IS_SOURCE_CHECKOUT = (REPO_ROOT / "pyproject.toml").is_file() and (
    REPO_ROOT / "openreltime_studio" / "locales"
).is_dir()

#: 指向引擎的本地路径写法（文档里一律不允许出现）。
ENGINE_AS_PATH = re.compile(
    r"(?:\.\./|~/|/Users/|/home/)+[^\s`)]*openreltime[^\s`)]*项目代码",
    re.IGNORECASE,
)
DISTRIBUTION_REF = re.compile(
    r"openreltime-studio|OpenRelTime-Studio|github\.com/ZengZichao/OpenRelTime"
)

#: The public home of the engine repository.  The README has to point at it
#: when it explains that Studio depends on the engine.
ENGINE_URL = "github.com/ZengZichao/OpenRelTime"

#: Neither distribution is on a package index yet, so the README must install
#: both wheels from the release instead of naming an index.  These are the two
#: URLs it has to carry; a typo in either is an install failure for every user.
ENGINE_WHEEL = (
    "github.com/ZengZichao/OpenRelTime/releases/download/"
    "v0.1.0/openreltime-0.1.0-py3-none-any.whl"
)
STUDIO_WHEEL = (
    "github.com/ZengZichao/OpenRelTime-Studio/releases/download/"
    "v0.1.0/openreltime_studio-0.1.0-py3-none-any.whl"
)

#: Revision-provenance markers: a ticket id, a review round, or a submission
#: checklist tag.  None of them belong in a released project, and none of them
#: may creep back in later.  Matching is case-sensitive on purpose: the
#: uppercase tokens below are placeholder markers, whereas ordinary UI copy
#: legitimately contains words such as "placeholder".
PROVENANCE_MARKERS: tuple[re.Pattern[str], ...] = (
    re.compile(r"review\s+(?:P?\d|issue)"),
    re.compile("审阅"),
    re.compile("评审"),
    re.compile("SUBMISSION-CHECKLIST"),
    re.compile("PLACEHOLDER"),
    re.compile("PENDING"),
)


def _is_outside_our_control(path: Path) -> bool:
    """Files we neither own nor can edit: build output and the frozen bundle.

    ``dist/OpenRelTimeStudio.app`` ships byte-for-byte as built and ad-hoc
    signed, and it carries the license files of bundled third-party
    dependencies (numpy and friends).  Those texts are not ours to change, so
    scanning them would let an upstream rewrite turn our CI red.
    """
    parts = [p.lower() for p in path.relative_to(REPO_ROOT).parts]
    return (
        "dist" in parts
        or "build" in parts
        or "__pycache__" in parts
        or ".pytest_cache" in parts
        or any(part.endswith(".app") for part in parts)
    )


def _docs() -> list[Path]:
    """Our own Markdown: everything outside build output and the frozen bundle."""
    return [path for path in MARKDOWN if not _is_outside_our_control(path)]


def _publishable_sources() -> list[Path]:
    """Our own Markdown and Python, minus the message catalogs.

    ``locales/{en,zh}/*.json`` holds UI copy, where words such as "review" are
    legitimate; the frozen bundle's Python belongs to third-party packages.
    """
    here = Path(__file__).resolve()
    sources: list[Path] = []
    for path in [*MARKDOWN, *PYTHON_SOURCES]:
        if _is_outside_our_control(path):
            continue
        # This module spells the banned markers out in order to detect them, so
        # it can never be judged by them.
        if path.resolve() == here:
            continue
        if "locales" in path.relative_to(REPO_ROOT).parts:
            continue
        sources.append(path)
    return sources


if not IS_SOURCE_CHECKOUT or not _docs():
    pytest.skip("documentation checks need a source checkout", allow_module_level=True)


def test_no_relative_paths_outside_repo() -> None:
    offenders = []
    for path in _docs():
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if "../" in line:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()[:80]}")
    assert not offenders, "docs must not reach outside the repository: \n" + "\n".join(offenders)


def test_engine_referenced_as_distribution_only() -> None:
    offenders = []
    for path in _docs():
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if ENGINE_AS_PATH.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}")
    assert not offenders, (
        "the engine must be referenced as an installed distribution or a URL, "
        "never as a local path: \n" + "\n".join(offenders)
    )


def test_local_markdown_links_resolve() -> None:
    """仓库内的相对链接（截图、手册互链）必须指向真实文件。"""
    broken = []
    for md in _docs():
        for link in re.findall(r"\[[^\]]*\]\(([^)#][^)\s]*)\)", md.read_text(encoding="utf-8")):
            if link.startswith(("http://", "https://", "mailto:")):
                continue
            if not (md.parent / link).resolve().exists():
                broken.append(f"{md.relative_to(REPO_ROOT)}: {link}")
    assert not broken, "broken local links: \n" + "\n".join(broken)


def test_readme_states_the_dependency_relationship() -> None:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert STUDIO_WHEEL in text
    assert ENGINE_WHEEL in text
    assert ENGINE_URL in text
    assert DISTRIBUTION_REF.search(text)


#: Neither project is on a package index, so a bare index install is a
#: guaranteed failure that reads perfectly plausibly.  Guard every shipped
#: Markdown and Python file against reintroducing one — module docstrings ship
#: inside the wheel, so they are as user-facing as the manual.
INDEX_INSTALL = re.compile(
    r"pip install[^\n]*?(?:\s|\")OpenRelTime-Studio(?:\[dev\])?(?:\"|\s|$)"
    r"|pip install[^\n]*?\"openreltime==",
    re.IGNORECASE,
)


def test_docs_do_not_name_an_index_that_has_no_release() -> None:
    offenders = []
    for path in _publishable_sources():
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if INDEX_INSTALL.search(line):
                offenders.append(
                    f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()[:70]}"
                )
    assert not offenders, (
        "no index release exists yet, so docs must install from the release "
        "URLs or from source: \n" + "\n".join(offenders)
    )


def test_no_revision_provenance_markers() -> None:
    """No tracked Markdown or Python may carry internal review provenance.

    Every file is read line by line so the report points at the exact place a
    marker was reintroduced.
    """
    offenders = []
    for path in _publishable_sources():
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        ):
            for pattern in PROVENANCE_MARKERS:
                if pattern.search(line):
                    offenders.append(
                        f"{path.relative_to(REPO_ROOT)}:{lineno}: "
                        f"{pattern.pattern!r} in {line.strip()[:60]}"
                    )
                    break
    assert not offenders, (
        "revision / peer-review provenance must not appear in shipped sources: \n"
        + "\n".join(offenders)
    )
