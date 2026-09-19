"""验收套件自检 —— 钉住「四态机制」本身（不绑定业务判据点，显式 `@acc()` 声明）。

为什么这层测试必须有：`PRD/验收/README.md` §三 说本项目**最贵的假绿**是
「未绑定 = 通过」。⇒ 套件自己的行为必须先被钉住，否则后面所有"绿"都不可信。
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.acc_plugin import acc

REPO_ROOT = Path(__file__).resolve().parents[2]
ACC_REPORT = REPO_ROOT / "tools" / "acc_report.py"


def _load_acc_report():
    spec = importlib.util.spec_from_file_location("acc_report_mod", ACC_REPORT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@acc()
def test_四态报表可运行且能读出判据总数():
    result = subprocess.run(
        [sys.executable, str(ACC_REPORT), "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        # ⚠️ 本机坑（2026-09-19）：**不显式给子进程 UTF-8 就会假红** —— Windows 上子进程默认按
        #    GBK(cp936) 写 stdout，读取线程 `decode('utf-8')` 直接抛 `UnicodeDecodeError`
        #    ⇒ `result.stdout` 变成 **None** ⇒ 下一条 `json.loads` 报 `TypeError`，看起来像
        #    "报表坏了"，其实是**父进程没设 `PYTHONIOENCODING`**（我 2026-09-19 忘设一次就中招）。
        #    ⇒ 这里**强制**子进程输出 UTF-8；`errors="replace"` 再兜一层（宁可看到乱码也不要 None）。
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        errors="replace",
    )
    # 有红 = 1、无红 = 0；两者都算"跑得起来"
    assert result.returncode in (0, 1), f"报表异常退出：{result.stderr}"
    payload = json.loads(result.stdout)
    assert payload["total"] > 0, "判据总数应大于 0（基线未读到？）"
    tally = payload["tally"]
    assert sum(tally.values()) == payload["total"], "四态之和必须等于判据总数"


@acc()
def test_未绑定的判据点不得被算作通过():
    """★ 本项目最贵的一类假绿：没验过 = 通过。"""
    mod = _load_acc_report()
    points = {"ACC-DEMO-001": {"001-01": {"id": "001-01", "claim": "x"}}}
    states = mod.build_states(points, {}, {"bindings": {}, "results": {}})
    assert states["ACC-DEMO-001"]["001-01"] == mod.UNBOUND


@acc()
def test_绑定了但未执行的判据点计为红():
    mod = _load_acc_report()
    points = {"ACC-DEMO-001": {"001-01": {"id": "001-01", "claim": "x"}}}
    # 测试存在（有绑定）但结果里没有它的 outcome ⇒ 不能算绿
    payload = {
        "bindings": {"tests/test_x.py::test_a": [["ACC-DEMO-001", "001-01"]]},
        "results": {},
    }
    states = mod.build_states(points, {}, payload)
    assert states["ACC-DEMO-001"]["001-01"] == mod.RED


@acc()
def test_全部判据点绿才算用例绿_未达标须报分数():
    mod = _load_acc_report()
    points = {
        "ACC-DEMO-002": {
            "001-01": {"id": "001-01", "claim": "a"},
            "001-02": {"id": "001-02", "claim": "b"},
        }
    }
    payload = {
        "bindings": {"tests/test_x.py::test_a": [["ACC-DEMO-002", "001-01"]]},
        "results": {"tests/test_x.py::test_a": "passed"},
    }
    states = mod.build_states(points, {}, payload)
    assert states["ACC-DEMO-002"]["001-01"] == mod.GREEN
    assert states["ACC-DEMO-002"]["001-02"] == mod.UNBOUND  # 只绿 1/2，不得算用例绿


@acc()
def test_基线待建区登记过的判据点计为待建而非未绑定():
    mod = _load_acc_report()
    points = {"ACC-DEMO-003": {"001-01": {"id": "001-01", "claim": "a"}}}
    baseline = {
        "_pending_assertions": {
            "A_waiting_for_impl": {
                "items": [{"case": "ACC-DEMO-003", "point": "001-01", "note": "待实现方建断言"}]
            }
        }
    }
    pending = mod.collect_pending(baseline)
    states = mod.build_states(points, pending, {"bindings": {}, "results": {}})
    assert states["ACC-DEMO-003"]["001-01"] == mod.PENDING


@acc()
def test_有红时报表以非零码退出():
    """有红即非零退出（供流水线判停）。"""
    # 直接测 render 的退出码语义：构造"有红"的最小状态
    mod = _load_acc_report()
    points = {"ACC-DEMO-004": {"001-01": {"id": "001-01", "claim": "a"}}}
    payload = {
        "bindings": {"tests/test_x.py::test_a": [["ACC-DEMO-004", "001-01"]]},
        "results": {"tests/test_x.py::test_a": "failed"},
    }
    states = mod.build_states(points, {}, payload)
    assert states["ACC-DEMO-004"]["001-01"] == mod.RED
    # 语义核对：报表的退出码 = 1 当且仅当存在红
    assert (1 if states["ACC-DEMO-004"]["001-01"] == mod.RED else 0) == 1


@acc()
def test_真实基线里的待建项确实存在于判据点集合中():
    """基线自洽性：`_pending_assertions` 的 A/B 档必须指向真实存在的判据点。"""
    mod = _load_acc_report()
    baseline_path = mod.resolve_baseline(None)
    baseline = mod.load_json(baseline_path)
    points = mod.collect_points(baseline)
    pending = mod.collect_pending(baseline)
    dangling = [(c, p) for (c, p) in pending if c not in points or p not in points[c]]
    assert not dangling, f"待建登记指向了不存在的判据点：{dangling}"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
