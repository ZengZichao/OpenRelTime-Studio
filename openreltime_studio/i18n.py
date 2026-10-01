"""双语消息目录（English / 简体中文）与即时语言切换。

设计要点：

* 目录按 *命名空间* 分散在 ``locales/<lang>/<namespace>.json``，键写作
  ``"<namespace>.<key>"``（``t("import.tree_file")``）。分散存放使不同界面
  模块可以独立增删文案而互不冲突。
* ``bind_text`` / ``bind_tooltip`` / ``bind_placeholder`` 在控件构造时登记
  「控件 → 键」绑定；切换语言时统一重放，界面无需重启即可换语言。
* 动态文本（状态栏、消息框、结果表）在使用的当下调用 ``t()``，不登记绑定。
* 语言偏好写入 ``QSettings("OpenRelTime", "Studio")``，默认英文。
"""

from __future__ import annotations

import contextlib
import inspect
import json
import weakref
from collections.abc import Callable
from pathlib import Path

__all__ = [
    "DEFAULT_LANGUAGE",
    "LANGUAGES",
    "LANGUAGE_LABELS",
    "LANGUAGE_SETTINGS_KEY",
    "available_languages",
    "bind",
    "bind_placeholder",
    "bind_text",
    "bind_tooltip",
    "catalog_keys",
    "configured_language",
    "has_key",
    "language",
    "load_catalog",
    "locales_dir",
    "on_language_change",
    "persist_language",
    "retranslate",
    "t",
]

LANGUAGES = ("en", "zh")
LANGUAGE_LABELS = {"en": "English", "zh": "简体中文"}
DEFAULT_LANGUAGE = "en"
LANGUAGE_SETTINGS_KEY = "ui/language"

#: ``locales/<lang>/`` 的父目录（与本模块同级的包资源）。
_LOCALE_ROOT = Path(__file__).resolve().parent / "locales"

_catalogs: dict[str, dict[str, str]] = {}
_language = DEFAULT_LANGUAGE
_listeners: list["_Listener"] = []
_bindings: list[tuple[weakref.ReferenceType, str, str, dict]] = []
_seen_missing: set[str] = set()


def locales_dir() -> Path:
    """消息目录所在的包内路径。"""
    return _LOCALE_ROOT


def available_languages() -> tuple[str, ...]:
    """支持的语言代码。"""
    return LANGUAGES


def load_catalog(lang: str) -> dict[str, str]:
    """读取并缓存某一语言的扁平字典（``命名空间.键`` → 文案）。"""
    if lang not in LANGUAGES:
        raise ValueError(f"unsupported language: {lang!r}")
    cached = _catalogs.get(lang)
    if cached is not None:
        return cached
    flat: dict[str, str] = {}
    base = _LOCALE_ROOT / lang
    for path in sorted(base.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path}: top level must be an object")
        stem = path.stem
        for key, value in data.items():
            if not isinstance(value, str):
                raise ValueError(f"{path}:{key}: values must be strings")
            flat[f"{stem}.{key}"] = value
    _catalogs[lang] = flat
    return flat


def catalog_keys(lang: str) -> set[str]:
    """某一语言的全部键。"""
    return set(load_catalog(lang))


def has_key(key: str, lang: str | None = None) -> bool:
    """键是否存在（默认检查当前语言）。"""
    return key in load_catalog(lang or _language)


def t(key: str, **params: object) -> str:
    """取当前语言下 ``key`` 的文案，可用 ``{name}`` 占位符传参。

    当前语言缺失时退回另一种语言，仍缺失则原样返回键名，保证界面永不崩溃；
    缺失组合只报告一次，避免热路径上重复打印。
    """
    catalog = load_catalog(_language)
    text = catalog.get(key)
    if text is None:
        for other in LANGUAGES:
            if other != _language:
                text = load_catalog(other).get(key)
                if text is not None:
                    break
    if text is None:
        if key not in _seen_missing:
            _seen_missing.add(key)
            import logging

            logging.getLogger("openreltime.studio").warning(
                "missing translation: %s (%s)", key, _language
            )
        return key
    if params:
        return text.format(**params)
    return text


def language() -> str:
    """当前语言代码。"""
    return _language


def configured_language() -> str:
    """启动时应使用的语言：已保存的偏好优先，否则默认英文。"""
    stored = _read_setting(LANGUAGE_SETTINGS_KEY)
    if isinstance(stored, str) and stored in LANGUAGES:
        return stored
    return DEFAULT_LANGUAGE


def persist_language(lang: str) -> None:
    """把语言偏好写回 ``QSettings``。"""
    _write_setting(LANGUAGE_SETTINGS_KEY, lang)


def set_language(lang: str, *, persist: bool = True, notify: bool = True) -> str:
    """切换语言；返回实际生效的语言代码。"""
    global _language
    if lang not in LANGUAGES:
        raise ValueError(f"unsupported language: {lang!r}")
    _language = lang
    if persist:
        persist_language(lang)
    load_catalog(lang)
    if notify:
        retranslate()
    return _language


def on_language_change(callback: Callable[[str], None]) -> Callable[[], None]:
    """注册语言变化回调，返回注销函数。

    绑定方法按弱引用登记：控件销毁后回调自动脱落，不会在切换语言时打到
    已经没了的 C++ 对象上。
    """
    entry = _Listener(callback)
    _listeners.append(entry)

    def unregister() -> None:
        with contextlib.suppress(ValueError):  # pragma: no cover - 重复注销
            _listeners.remove(entry)

    return unregister


def _bind(
    widget: object,
    setter: str,
    key: str,
    params: dict[str, object],
    *,
    apply_now: bool = True,
) -> None:
    """登记绑定本体；``params`` 以普通字典传递，避免 **kwargs 解包歧义。"""
    ref = weakref.ref(widget)
    entry = (ref, setter, key, params)
    _bindings.append(entry)
    if apply_now:
        _apply(entry)


def bind(
    widget: object,
    setter: str,
    key: str,
    *,
    apply_now: bool = True,
    **params: object,
) -> None:
    """把控件的某一属性绑定到消息键，语言切换时自动重放。

    ``setter`` 是控件上的方法名（如 ``"setText"``）。控件被销毁后绑定自动
    失效（弱引用），因此反复重建对话框不会累积回调。
    """
    _bind(widget, setter, key, params, apply_now=apply_now)


def bind_text(widget: object, key: str, **params: object) -> None:
    """绑定可见文本（按钮、标签、菜单项、分组框标题）。"""
    _bind(widget, "setText", key, params)


def bind_tooltip(widget: object, key: str, **params: object) -> None:
    """绑定悬停提示。"""
    _bind(widget, "setToolTip", key, params)


def bind_placeholder(widget: object, key: str, **params: object) -> None:
    """绑定输入框占位文本。"""
    _bind(widget, "setPlaceholderText", key, params)


def retranslate() -> None:
    """重放全部绑定并通知监听者（供外部主动刷新动态文本）。"""
    alive = []
    for binding in _bindings:
        if _apply(binding):
            alive.append(binding)
    _bindings[:] = alive
    live = []
    for listener in list(_listeners):
        if listener.alive():
            listener(_language)
            live.append(listener)
    _listeners[:] = live


def clear_bindings() -> None:
    """清空绑定、监听与缺失记录（测试隔离用）。"""
    _bindings.clear()
    _listeners.clear()
    _seen_missing.clear()


def _apply(entry) -> bool:
    """把键写到控件上；控件已销毁时返回 False，让绑定自然脱落。"""
    ref, setter, key, params = entry
    widget = ref()
    if widget is None or not _alive(widget):
        return False
    method = getattr(widget, setter, None)
    if method is None:  # pragma: no cover - 控件类型不符
        return False
    try:
        method(t(key, **params))
    except RuntimeError:  # pragma: no cover - C++ 侧刚被销毁
        return False
    return True


def _alive(widget) -> bool:
    """Python 包装器还在，但底层 C++ 对象可能已被 Qt 销毁。"""
    try:
        import shiboken6
    except ImportError:  # pragma: no cover - 非 PySide 环境
        return True
    return shiboken6.isValid(widget)


def _read_setting(key: str):
    try:
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication
    except ImportError:  # pragma: no cover - 无 Qt 时退回到默认值
        return None
    if QApplication.instance() is None:
        return None
    return QSettings("OpenRelTime", "Studio").value(key)


def _write_setting(key: str, value: str) -> None:
    try:
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication
    except ImportError:  # pragma: no cover - 无 Qt 时忽略持久化
        return
    if QApplication.instance() is None:
        return
    settings = QSettings("OpenRelTime", "Studio")
    settings.setValue(key, value)
    settings.sync()


class _Listener:
    """语言回调的弱引用包装：绑定方法只指向实例，不阻止其回收。"""

    def __init__(self, callback: Callable[[str], None]) -> None:
        if inspect.ismethod(callback):
            self._target: weakref.ReferenceType | None = weakref.ref(callback.__self__)
            self._method_name = callback.__func__.__name__
            self._plain = None
        else:
            self._target = None
            self._method_name = ""
            self._plain = callback

    def alive(self) -> bool:
        if self._target is not None:
            owner = self._target()
            return owner is not None and _alive(owner)
        return True

    def __call__(self, lang: str) -> None:
        if self._target is not None:
            owner = self._target()
            if owner is None:
                return
            getattr(owner, self._method_name)(lang)
        elif self._plain is not None:
            self._plain(lang)
