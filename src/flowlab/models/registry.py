"""模型注册表：插件化接入，新增模型只需加一个文件。"""

from __future__ import annotations

import importlib
import pkgutil

from flowlab.models.base import Detector

_REGISTRY: dict[str, type[Detector]] = {}
_discovered = False


def register(name: str):
    def deco(cls: type[Detector]):
        if name in _REGISTRY and _REGISTRY[name] is not cls:
            raise ValueError(f"模型名重复注册: {name}")
        cls.name = name
        _REGISTRY[name] = cls
        return cls

    return deco


def _discover() -> None:
    global _discovered
    if _discovered:
        return
    pkg = importlib.import_module("flowlab.models")
    for m in pkgutil.iter_modules(pkg.__path__):
        # 跳过骨架与模板：下划线开头约定为"不自动加载"，
        # 否则 _template.py 会把 my_model 塞进模型列表
        if m.name in {"base", "registry"} or m.name.startswith("_"):
            continue
        importlib.import_module(f"flowlab.models.{m.name}")
    _discovered = True


def available() -> list[str]:
    _discover()
    return sorted(_REGISTRY)


def create(name: str, **params) -> Detector:
    _discover()
    if name not in _REGISTRY:
        raise KeyError(f"未知模型 {name!r}，可用: {available()}")
    return _REGISTRY[name](**params)
