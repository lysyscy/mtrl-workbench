"""历史判据报表纯测试；只读伪基线和伪运行结果，不加载业务配置。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ACC_REPORT = REPO_ROOT / "tools" / "audit" / "acc_report.py"      # ⭐ `TAIL-58` 分目录


def _load_acc_report():
    spec = importlib.util.spec_from_file_location("acc_report_mod", ACC_REPORT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_配置的相对基线始终以仓根解释_显式CLI路径保持原语义(tmp_path, monkeypatch):
    mod = _load_acc_report()
    monkeypatch.setattr(mod, 'REPO_ROOT', tmp_path)
    (tmp_path / '.env').write_text('PRD_ACCEPTANCE_BASELINE=docs/requirements/baseline.json\n', encoding='utf8')
    elsewhere = tmp_path / 'backend'
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert mod.resolve_baseline(None) == tmp_path / 'docs/requirements/baseline.json'
    assert mod.resolve_baseline('explicit.json') == Path('explicit.json')


def test_未绑定的判据点不得被算作通过():
    """★ 本项目最贵的一类假绿：没验过 = 通过。"""
    mod = _load_acc_report()
    points = {"ACC-DEMO-001": {"001-01": {"id": "001-01", "claim": "x"}}}
    states = mod.build_states(points, {}, {"bindings": {}, "results": {}})
    assert states["ACC-DEMO-001"]["001-01"] == mod.UNBOUND


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


@pytest.mark.parametrize("outcome, exit_code, color", [("failed", 1, "RED"), ("passed", 0, "GREEN")])
def test_报表退出码跟随实际判据状态(tmp_path, outcome, exit_code, color):
    mod = _load_acc_report()
    baseline_path, results_path = tmp_path / "baseline.json", tmp_path / "results.json"
    baseline_path.write_text(json.dumps({"asof": "selftest", "cases": {
        "ACC-DEMO-004": {"points": [{"id": "001-01", "claim": "a"}]},
    }}), encoding="utf-8")
    results_path.write_text(json.dumps({
        "pytest_exitstatus": 1 if outcome == "failed" else 0,
        "bindings": {"tests/test_x.py::test_a": [["ACC-DEMO-004", "001-01"]]},
        "results": {"tests/test_x.py::test_a": outcome},
    }), encoding="utf-8")
    actual_code, meta = mod.render(SimpleNamespace(
        baseline=str(baseline_path), results=str(results_path),
        verbose=False, by_stage=False, json=False, json_out=None,
    ))
    assert actual_code == exit_code
    assert meta["tally"][getattr(mod, color)] == 1


@pytest.fixture
def report_input(tmp_path):
    baseline = tmp_path / "baseline.json"
    results = tmp_path / "results.json"
    baseline.write_text(json.dumps({"cases": {
        "ACC-DEMO-001": {"points": [{"id": "001-01", "claim": "a"}]},
    }}), encoding="utf-8")
    args = SimpleNamespace(baseline=str(baseline), results=str(results),
                           verbose=False, by_stage=False)
    return args, results, {
        "pytest_exitstatus": 0,
        "bindings": {"test_bound": [["ACC-DEMO-001", "001-01"]]},
        "results": {"test_bound": "passed"},
    }


@pytest.mark.parametrize("kind", ["unbound_failure", "missing_exitstatus", "nonzero",
                                      "no_results", "missing_result", "unknown"])
def test_判据全绿不能掩盖运行失败或不完整(report_input, kind, capsys):
    args, path, payload = report_input
    if kind == "unbound_failure":
        payload["results"]["test_unbound"] = "failed"
    elif kind == "missing_exitstatus":
        del payload["pytest_exitstatus"]
    elif kind == "nonzero":
        payload["pytest_exitstatus"] = 2
    elif kind == "no_results":
        payload["bindings"] = {}
        payload["results"] = {}
    elif kind == "missing_result":
        payload["bindings"]["test_not_run"] = []
    elif kind == "unknown":
        payload["results"]["test_unknown"] = "unknown"
    path.write_text(json.dumps(payload), encoding="utf-8")
    mod = _load_acc_report()
    code, meta = mod.render(args)
    assert code == 1
    assert meta["run_issues"]
    assert meta["pytest_exitstatus"] == payload.get("pytest_exitstatus")
    if kind in ("unbound_failure", "missing_exitstatus", "nonzero", "missing_result", "unknown"):
        assert meta["tally"][mod.GREEN] == 1
    if kind == "unbound_failure":
        assert meta["unbound_failed_tests"] == ["test_unbound"]
        assert "test_unbound" in capsys.readouterr().out
    if kind == "missing_result":
        assert meta["missing_results"] == ["test_not_run"]
    if kind == "unknown":
        assert meta["unknown_results"] == ["test_unknown"]


def test_结果文件缺失不能报通过(report_input):
    args, path, _ = report_input
    assert not path.exists()
    code, meta = _load_acc_report().render(args)
    assert code == 1
    assert "运行结果文件缺失" in meta["run_issues"]


@pytest.mark.parametrize("phase", ["setup", "teardown"])
def test_前后置失败按已记录failed结果计红(report_input, phase):
    args, path, payload = report_input
    # 插件把 setup/teardown 失败折算为 failed；报表消费该结果。
    nodeid = f"test_{phase}_failed"
    payload["bindings"] = {nodeid: [["ACC-DEMO-001", "001-01"]]}
    payload["results"] = {nodeid: "failed"}
    payload["pytest_exitstatus"] = 1
    path.write_text(json.dumps(payload), encoding="utf-8")
    mod = _load_acc_report()
    code, meta = mod.render(args)
    assert code == 1
    assert meta["tally"][mod.RED] == 1
    assert meta["failed_tests"] == [nodeid]


def test_CLI只读取显式伪输入并输出运行状态(report_input):
    import os
    import subprocess
    import sys

    args, path, payload = report_input
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ACC_REPORT), "--baseline", args.baseline,
         "--results", args.results, "--json"],
        capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert result.returncode == 0, result.stderr
    meta = json.loads(result.stdout)
    assert meta["pytest_exitstatus"] == 0
    assert meta["report_exitstatus"] == 0
    assert meta["total"] == 1
    assert not meta["run_issues"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
