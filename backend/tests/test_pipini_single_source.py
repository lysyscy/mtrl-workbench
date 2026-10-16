"""项目安装源由 pyproject.toml 持有，不另存 pip 配置副本。"""

from __future__ import annotations

import pathlib
import tomllib

from tests.acc_plugin import acc

BACKEND = pathlib.Path(__file__).resolve().parents[1]
PROJECT = BACKEND / "pyproject.toml"


@acc()
def test_依赖安装源由项目配置唯一管理():
    config = tomllib.loads(PROJECT.read_text(encoding="utf-8"))
    indexes = config.get("tool", {}).get("uv", {}).get("index", [])
    assert indexes == [{"name": "pypi", "url": "https://pypi.org/simple", "default": True}]
