"""Conditionally package the built Web UI.

A source checkout should be installable before the frontend has been built
(``uv sync`` must work for CLI-only development and CI). Release builds still
include ``web/dist`` when it exists, so wheel and sdist artifacts remain
self-contained.
"""

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict) -> None:
        dist = Path(self.root) / "web" / "dist"
        if not dist.is_dir() or not any(dist.iterdir()):
            return

        destination = "flowlab/web" if self.target_name == "wheel" else "web/dist"
        build_data.setdefault("force_include", {})["web/dist"] = destination
