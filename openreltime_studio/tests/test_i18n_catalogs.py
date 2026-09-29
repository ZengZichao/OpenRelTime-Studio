"""双语目录与主题令牌的静态检查。

这些检查不依赖 Qt，因此在没有显示环境（甚至没装 PySide6）的机器上也能跑：

* ``test_no_hardcoded_cjk_literals`` — 界面文案必须进目录，Python 源码里不许
  残留中文字符串字面量（注释与 docstring 不受限）。
* ``test_no_hardcoded_colors`` — 颜色只允许出现在 ``themes.py`` /
  ``appicon.py`` / ``resources/``，控件一律走令牌。
* ``test_every_referenced_key_exists`` — 代码里用到的每个键都在 en 与 zh 目录
  中存在（占位符集合一致）。
* ``test_catalog_languages_are_symmetric`` — 两种语言的键集合完全一致。
* ``test_no_dead_catalog_keys`` — 目录里不留无人引用的键。
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PKG_ROOT.parent
LOCALES = PKG_ROOT / "locales"
LANGS = ("en", "zh")

#: 取文案的函数：首个字符串参数必须是常量键。
TEXT_FUNCS = {"t", "bind", "bind_text", "bind_tooltip", "bind_placeholder"}

#: 允许出现中文源码字面量的文件（相对包根目录）。
CJK_ALLOWED: set[str] = {"resources/make_icon.py", "i18n.py"}

#: 允许硬编码颜色的文件（主题与图标本身）。
COLOR_ALLOWED = {"themes.py", "appicon.py", "i18n.py"}

#: 运行期拼接的键前缀（无法静态判定），允许目录中的键不被静态引用。
DYNAMIC_PREFIXES = ()

_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_KEY_SHAPE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$")


def _source_files() -> list[Path]:
    return sorted(
        p
        for p in PKG_ROOT.rglob("*.py")
        if "tests" not in p.parts and "__pycache__" not in p.parts
    )


def _catalog(lang: str) -> dict[str, str]:
    flat: dict[str, str] = {}
    base = LOCALES / lang
    assert base.is_dir(), f"missing catalog directory: {base}"
    for path in sorted(base.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for key, value in data.items():
            flat[f"{path.stem}.{key}"] = value
    return flat

def _namespaces() -> set[str]:
    """目录里已有的命名空间（= ``locales/en`` 下的文件名）。"""
    base = LOCALES / "en"
    return {p.stem for p in base.glob("*.json")} if base.is_dir() else set()


def _referenced_keys() -> set[str]:
    """源码中出现的消息键。

    除 ``t()`` / ``bind_*()`` 调用里的字面量键外，任何形如 ``命名空间.名字`` 的
    字符串字面量也算引用——键经辅助函数转手时仍能追溯。
    """
    keys: set[str] = set()
    ns = _namespaces()
    trees = [
        ast.parse(src.read_text(encoding="utf-8"), filename=str(src))
        for src in _source_files()
    ]
    for tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            value = node.value
            if value.split(".", 1)[0] in ns and _KEY_SHAPE.match(value):
                keys.add(value)
    for tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name not in TEXT_FUNCS:
                continue
            idx = 0 if name == "t" else (2 if name == "bind" else 1)
            if len(node.args) > idx:
                arg = node.args[idx]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    keys.add(arg.value)
    return keys


def _docstring_ids(tree: ast.AST) -> set[int]:
    """模块/类/函数首句 docstring 的字符串节点 id（非界面文案，不受限）。"""
    out: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            out.add(id(body[0].value))
    return out


def _string_literals(tree: ast.AST, *, skip_docstrings: bool = False) -> list[tuple[str, int]]:
    docs = _docstring_ids(tree) if skip_docstrings else set()
    return [
        (node.value, node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docs
    ]


def test_source_files_present() -> None:
    assert _source_files(), "no package sources discovered"


@pytest.mark.parametrize("lang", LANGS)
def test_catalog_directory_exists(lang: str) -> None:
    assert (LOCALES / lang).is_dir(), f"locales/{lang} is missing"


def test_no_hardcoded_cjk_literals() -> None:
    offenders = []
    for src in _source_files():
        if str(src.relative_to(PKG_ROOT)) in CJK_ALLOWED:
            continue
        tree = ast.parse(src.read_text(encoding="utf-8"), filename=str(src))
        for value, lineno in _string_literals(tree, skip_docstrings=True):
            if re.search(r"[\u4e00-\u9fff]", value):
                offenders.append(f"{src.relative_to(REPO_ROOT)}:{lineno}: {value[:40]!r}")
    assert not offenders, "UI text must live in locales/: \n" + "\n".join(offenders)


def test_no_hardcoded_colors() -> None:
    offenders = []
    for src in _source_files():
        rel = str(src.relative_to(PKG_ROOT))
        if rel in COLOR_ALLOWED or rel.startswith("resources/"):
            continue
        tree = ast.parse(src.read_text(encoding="utf-8"), filename=str(src))
        for value, lineno in _string_literals(tree, skip_docstrings=True):
            if _HEX_COLOR.search(value):
                offenders.append(f"{src.relative_to(REPO_ROOT)}:{lineno}")
    assert not offenders, "colors must come from themes.tokens(): \n" + "\n".join(offenders)


def test_catalog_languages_are_symmetric() -> None:
    en, zh = set(_catalog("en")), set(_catalog("zh"))
    assert en - zh == set(), f"keys only in en: {sorted(en - zh)[:10]}"
    assert zh - en == set(), f"keys only in zh: {sorted(zh - en)[:10]}"


def test_every_referenced_key_exists() -> None:
    keys = _referenced_keys()
    assert keys, "no message keys found — did the conversion happen?"
    catalogs = {lang: _catalog(lang) for lang in LANGS}
    missing = {
        lang: sorted(key for key in keys if key not in catalog)
        for lang, catalog in catalogs.items()
    }
    problems = [f"{lang}: {key}" for lang, keys_ in missing.items() for key in keys_]
    assert not problems, "missing catalog entries: \n" + "\n".join(problems)


def test_placeholders_match_between_languages() -> None:
    pattern = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
    en, zh = _catalog("en"), _catalog("zh")
    mismatched = [
        key
        for key in set(en) & set(zh)
        if set(pattern.findall(en[key])) != set(pattern.findall(zh[key]))
    ]
    assert not mismatched, f"placeholder mismatch: {mismatched}"


def test_no_dead_catalog_keys() -> None:
    keys = _referenced_keys()
    dead = sorted(set(_catalog("en")) - keys)
    dead = [key for key in dead if not key.startswith(DYNAMIC_PREFIXES)]
    assert not dead, f"unused catalog keys: {dead}"
