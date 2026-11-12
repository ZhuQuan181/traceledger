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
        if m.name not in {"base", "registry"}:
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
