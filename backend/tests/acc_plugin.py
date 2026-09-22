"""验收绑定插件（M0-0D）。

依据：`PRD/验收/README.md` §三「机制契约」——
- **绑定**：每个测试**成对**声明「用例号 + 判据点号」，一条判据点 ↔ 一个测试；
  **不许只挂用例号**（否则报不出"哪条判据点还没验"）。
- **四态**：绿 / 红 / 待建 / 未绑定；**未绑定 ≠ 通过**。
- 本插件只做「**收集绑定 + 收集结果 → 落 JSON**」，四态汇总在 `tools/audit/acc_report.py`。

用法（测试里）：

    from tests.acc_plugin import acc

    @acc("ACC-PAY-PRINT-001", "001-03")
    def test_取不到版式须显式报错():
        ...

一个测试可挂多条判据点（累加多个 `@acc`）。
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Callable

BINDINGS_ATTR = "_acc_bindings"

_bindings: dict[str, list[list[str]]] = {}
_declared: dict[str, bool] = {}
_results: dict[str, str] = {}
_out_path: Path = Path("artifacts/acc_results.json")


def acc(case: str | None = None, point: str | None = None) -> Callable:
    """声明「用例号 + 判据点号」。

    两种用法：
    - `@acc("ACC-X-001", "001-01")` —— 正常绑定
    - `@acc()` —— **显式声明"本测试不绑定任何判据点"**（如工具自检），
      避免被"未绑定测试体检"误报。
    """

    def decorator(fn: Callable) -> Callable:
        binds: list[list[str]] = list(getattr(fn, BINDINGS_ATTR, []) or [])
        if case and point:
            binds.append([case, point])
        setattr(fn, BINDINGS_ATTR, binds)
        return fn

    return decorator


def pytest_configure(config) -> None:  # noqa: ARG001
    global _out_path
    raw = os.environ.get("ACC_RESULTS_PATH", "artifacts/acc_results.json")
    _out_path = Path(raw)
    _out_path.parent.mkdir(parents=True, exist_ok=True)


def pytest_collection_modifyitems(session, config, items) -> None:  # noqa: ARG001
    for item in items:
        fn = getattr(item, "function", None)
        # ⚠️ 区分两种"没有绑定"：
        #   - 函数上**没有** BINDINGS_ATTR ⇒ 作者根本没声明（体检要报出来）
        #   - 函数上有 BINDINGS_ATTR 但为空 ⇒ 作者用 `@acc()` **显式声明不绑定**（不报）
        declared = hasattr(fn, BINDINGS_ATTR) if fn is not None else False
        binds = list(getattr(fn, BINDINGS_ATTR, []) or [])
        _bindings[item.nodeid] = binds
        _declared[item.nodeid] = declared


def pytest_runtest_logreport(report) -> None:
    if report.when == "call":
        _results[report.nodeid] = report.outcome
    elif report.when == "setup" and report.outcome in ("failed", "skipped"):
        _results.setdefault(report.nodeid, report.outcome)
    elif report.when == "teardown" and report.outcome == "failed":
        _results.setdefault(report.nodeid, "failed")


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ARG001
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "pytest_exitstatus": int(exitstatus),
        "bindings": _bindings,
        "declared": _declared,
        "results": _results,
    }
    _out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    undeclared = [
        nodeid
        for nodeid, declared in _declared.items()
        if not declared and not _bindings.get(nodeid)
    ]
    if undeclared:
        print(
            f"\n[acc] ⚠️ {len(undeclared)} 个测试未声明绑定"
            f"（业务测试须 @acc(用例号, 判据点号)；工具自检请显式 @acc()）："
        )
        for nodeid in undeclared[:10]:
            print(f"      - {nodeid}")
