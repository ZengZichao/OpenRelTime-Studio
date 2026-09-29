#!/usr/bin/env python3
"""界面文案静态自检：可只检查单个文件，便于分工时独立验证。

用法::

    python tools/check_i18n.py openreltime_studio/widgets/param_panels.py ...

检查项（与 ``openreltime_studio/tests/test_i18n_catalogs.py`` 同一套规则）：

1. 源码字符串字面量里不得残留中文（docstring 除外）；
2. 源码字符串字面量里不得残留 ``#rrggbb`` 颜色（themes/appicon 除外）；
3. ``t()`` / ``bind_*()`` 引用的键必须同时存在于 ``locales/en`` 与 ``locales/zh``；
4. 目录里不得有无人引用的键（全仓库扫描）。
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "openreltime_studio"
LANGS = ("en", "zh")
TEXT_FUNCS = {"t", "bind", "bind_text", "bind_tooltip", "bind_placeholder"}
#: 允许出现中文源码字面量的文件（语言名本身、开发脚本的控制台输出）。
CJK_ALLOWED = {"resources/make_icon.py", "i18n.py"}
COLOR_ALLOWED = {"themes.py", "appicon.py", "i18n.py"}
_CJK = re.compile(r"[\u4e00-\u9fff]")
_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_KEY_SHAPE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$")


def catalog(lang: str) -> dict[str, str]:
    flat: dict[str, str] = {}
    base = PKG / "locales" / lang
    for path in sorted(base.glob("*.json")) if base.is_dir() else []:
        for key, value in json.loads(path.read_text(encoding="utf-8")).items():
            flat[f"{path.stem}.{key}"] = value
    return flat


def docstring_ids(tree: ast.AST) -> set[int]:
    out: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        body = getattr(node, "body", None)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            out.add(id(body[0].value))
    return out


def literals(tree: ast.AST) -> list[tuple[str, int]]:
    docs = docstring_ids(tree)
    return [
        (n.value, n.lineno)
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs
    ]


def _namespaces() -> set[str]:
    """目录里已有的命名空间（= locales/en 下的文件名）。"""
    base = PKG / "locales" / "en"
    return {p.stem for p in base.glob("*.json")} if base.is_dir() else set()


def referenced_keys(trees: list[tuple[Path, ast.AST]]) -> set[str]:
    """源码中出现的消息键。

    两条来源合并：一是 ``t()`` / ``bind_*()`` 调用里的字面量键；二是任何形如
    ``命名空间.名字`` 的字符串字面量（键经辅助函数转手时仍能追溯到）。
    """
    keys: set[str] = set()
    ns = _namespaces()
    for _, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            value = node.value
            head = value.split(".", 1)[0]
            if head in ns and _KEY_SHAPE.match(value) and value != head:
                keys.add(value)
            if isinstance(node, ast.Constant):
                continue
    for _, tree in trees:
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


def main(argv: list[str]) -> int:
    targets = [Path(a).resolve() for a in argv] or sorted(PKG.rglob("*.py"))
    targets = [
        p
        for p in targets
        if p.is_file()
        and p.suffix == ".py"
        and "tests" not in p.parts
        and "__pycache__" not in p.parts
    ]
    problems: list[str] = []
    checked: list[tuple[Path, ast.AST]] = []
    for path in targets:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        checked.append((path, tree))
        rel = str(path.relative_to(PKG))
        allow_cjk = rel in CJK_ALLOWED
        for value, lineno in literals(tree):
            if _CJK.search(value) and not allow_cjk:
                problems.append(f"{rel}:{lineno}: 中文字面量 {value[:32]!r}")
            if _HEX.search(value) and rel not in COLOR_ALLOWED and not rel.startswith(
                "resources/"
            ):
                problems.append(f"{rel}:{lineno}: 硬编码颜色 {value[:24]!r}")

    keys = referenced_keys(checked)
    catalogs = {lang: catalog(lang) for lang in LANGS}
    for key in sorted(keys):
        for lang in LANGS:
            if key not in catalogs[lang]:
                problems.append(f"catalog[{lang}]: 缺少键 {key}")

    all_sources = []
    for p in sorted(PKG.rglob("*.py")):
        if "tests" in p.parts or "__pycache__" in p.parts:
            continue
        try:
            all_sources.append((p, ast.parse(p.read_text(encoding="utf-8"), filename=str(p))))
        except SyntaxError:
            # 并行分工时其它人的文件可能正处于写入中间态，不参与全量扫描
            print(f"note: skipping unparsed {p.name}", file=sys.stderr)
    dead = sorted(set(catalogs["en"]) - referenced_keys(all_sources))
    for key in dead:
        problems.append(f"catalog: 无人引用的键 {key}")

    for line in problems:
        print(line, file=sys.stderr)
    print(f"checked {len(targets)} file(s), {len(keys)} key(s) referenced: "
          f"{'FAIL' if problems else 'OK'}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
