"""TAIL-264～266 反向灵敏度：浏览器候选/合同定位/月序/取消与库存年度金额必须识别变坏。

只生成 scratch 副本并替换测试进程的输入；不改正式源码、不恢复文件、不写现场数据。
每个正常靶先通过；变异须 pytest exit 1 且 call 阶段仅 AssertionError，setup/timeout 不算见证。
用法：backend/.venv/Scripts/python.exe tools/mut/_mut_tail264_266.py
"""

from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
PYTHON = BACKEND / ".venv/Scripts/python.exe"
SCRATCH = ROOT / _run_dir('work')
PREFIX = "tmp-20261009-tail264-266-mut"
ACTIONS = ROOT / "backend/app/web/shell/actions.js"
INVENTORY = ROOT / "backend/app/mod07_setl/inventory_extract.py"

UI264 = "tests/test_tail264_ui.py::"
UI265 = "tests/test_tail265_ui.py::"
ANNUAL = "tests/test_tail266_inventory.py::test_inventory_year_months_future_and_balance_are_independent"

MUTATIONS = [
    ("supplier_filter", ACTIONS, "const cands=[...new Set(pool)].filter(name=>!q||name.includes(q));",
     "const cands=[...new Set(pool)];", UI264 + "test_supplier_search_choose_and_failed_enter_keeps_full_name"),
    ("contract_id", ACTIONS, "API.m11Fields({id:j.id,fields:{material_name:value}})",
     "API.m11Fields({id:'502',fields:{material_name:value}})", UI264 + "test_material_edit_uses_contract_id_and_preserves_failure"),
    ("month_sequence", ACTIONS, "el.dataset.ym=ymAdd(t.value,i);el.textContent=el.dataset.ym;",
     "el.dataset.ym=t.value;el.textContent=el.dataset.ym;", UI265 + "test_month_columns_increment_and_preserve_positions"),
    ("cancel_download", ACTIONS, "procExpCancel:()=>{procExpPjs=[];closeModal();},",
     "procExpCancel:()=>{dlExport('/api/m06/export?projects=cancel-mutant');procExpPjs=[];closeModal();},",
     UI265 + "test_export_same_modal_cancel_and_long_list_footer"),
    ("inventory_wrong_amount", INVENTORY, "**{'in':d.amount}", "**{'in':0}", ANNUAL),
    ("inventory_include_out", INVENTORY, "if d.direction == '入库'", "if d.direction in ('入库', '出库')", ANNUAL),
    ("inventory_tax_total", INVENTORY, "**{'in':d.amount}", "**{'in':d.tax_total}", ANNUAL),
    ("annual_drop_prior", INVENTORY,
     "prior = sum_money([value for ym,value in values.items() if ym < months[0]])",
     "prior = Decimal('0.00')", ANNUAL),
    ("annual_include_future", INVENTORY, "'total':sum_money([prior, *cells])",
     "'total':sum_money(list(values.values()))", ANNUAL),
]

PLUGIN = '''"""Process-local mutation input and typed failure evidence."""
import json
import os
from pathlib import Path
import pytest

FAILURES = []
INSTALLED = False

def pytest_runtest_setup(item):
    global INSTALLED
    path = os.environ.get("TAIL_INVENTORY_OVERRIDE")
    if path and not INSTALLED:
        from app.mod07_setl import inventory_extract as inventory
        namespace = {"__name__": "tail_inventory_mutant"}
        exec(compile(Path(path).read_text("utf-8"), path, "exec"), namespace)
        inventory.load_amounts = namespace["load_amounts"]
        inventory.annual_grid = namespace["annual_grid"]
        INSTALLED = True

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.failed:
        FAILURES.append({"nodeid": item.nodeid, "phase": report.when,
                         "type": call.excinfo.type.__name__ if call.excinfo else "unknown",
                         "assertion": bool(call.excinfo and issubclass(call.excinfo.type, AssertionError))})

def pytest_sessionfinish(session, exitstatus):
    Path(os.environ["TAIL_MUT_REPORT"]).write_text(
        json.dumps({"exit": int(exitstatus), "failures": FAILURES}, ensure_ascii=False), "utf-8")
'''


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(label: str, tests: list[str], *, override: Path | None = None, inventory=False) -> dict:
    env = os.environ.copy()
    env.pop("TAIL_ACTIONS_OVERRIDE", None)
    env.pop("TAIL_INVENTORY_OVERRIDE", None)
    env.update(PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
               PLAYWRIGHT_BROWSERS_PATH="C:/ProgramData/ms-playwright")
    env["PYTHONPATH"] = str(SCRATCH) + os.pathsep + env.get("PYTHONPATH", "")
    report_path = SCRATCH / f"{PREFIX}-{label}-failures.json"
    env["TAIL_MUT_REPORT"] = str(report_path)
    env["ACC_RESULTS_PATH"] = str(SCRATCH / f"{PREFIX}-{label}-acc.json")
    if override:
        env["TAIL_INVENTORY_OVERRIDE" if inventory else "TAIL_ACTIONS_OVERRIDE"] = str(override)
    command = [str(PYTHON), "-m", "pytest", "-q", "--tb=short", "-p", "tail264_266_mutation_plugin", *tests]
    result = subprocess.run(command, cwd=BACKEND, env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=180)
    output = result.stdout + result.stderr
    log = SCRATCH / f"{PREFIX}-{label}.log"
    log.write_text(output, "utf-8")
    report = json.loads(report_path.read_text("utf-8")) if report_path.exists() else {"failures": []}
    record = {"label": label, "command": command, "returncode": result.returncode,
              "failures": report["failures"], "log": str(log)}
    print(f"{label}: exit={result.returncode}; {record['failures']}", flush=True)
    return record


def main() -> int:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / "tail264_266_mutation_plugin.py").write_text(PLUGIN, "utf-8")
    originals = {path: (path.read_text("utf-8"), digest(path)) for path in (ACTIONS, INVENTORY)}
    # Exact function anchors were inspected before creation; fail before running tests if they drift.
    for label, path, old, new, test in MUTATIONS:
        assert originals[path][0].count(old) == 1, f"{label}: mutation anchor is not unique"
    tests = list(dict.fromkeys(row[4] for row in MUTATIONS))
    records = [run("baseline", tests)]
    if records[0]["returncode"] != 0:
        print("Normal baseline failed; mutants were not run. See baseline log.", flush=True)
        return 1
    bad = []
    for label, path, old, new, test in MUTATIONS:
        target = SCRATCH / f"{PREFIX}-{label}{path.suffix}"
        target.write_text(originals[path][0].replace(old, new, 1), "utf-8")
        record = run(label, [test], override=target, inventory=path == INVENTORY)
        records.append(record)
        failures = record["failures"]
        valid = (record["returncode"] == 1 and bool(failures)
                 and all(f["phase"] == "call" and f["assertion"] for f in failures))
        if not valid:
            bad.append(label)
    unchanged = all(digest(path) == sha for path, (_, sha) in originals.items())
    summary = {"records": records, "invalid_witnesses": bad, "source_unchanged": unchanged}
    (SCRATCH / f"{PREFIX}-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
    print(f"Witnesses: {len(MUTATIONS) - len(bad)}/{len(MUTATIONS)}; source unchanged: {unchanged}", flush=True)
    return 0 if not bad and unchanged else 1


if __name__ == "__main__":
    sys.exit(main())
