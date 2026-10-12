"""守过程报表同源、机械资格、空态与回滚：隔离副本逐靶断言造红，不改正式源码。"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from _isolated import isolated_backend

ROOT = Path(__file__).resolve().parents[2]
TEST = "tests/test_proc_report_data.py"
MUTATIONS = [
    ("omit-mechanical-projects", "app/mod06_proc/service.py",
     '"projects": projects_of(inv, history + manual)', '"projects": projects_of(inv, history)',
     "each_effective_source"),
    ("shared-first-cutoff", "app/mod06_proc/service.py",
     'data["cutoffs"].get(warehouse) or ""', 'next(iter(data["cutoffs"].values()), "")',
     "each_effective_source"),
    ("swap-raw-adjusted", "app/mod06_proc/service.py",
     '(("raw", False), ("adjusted", True))', '(("raw", True), ("adjusted", False))',
     "each_effective_source"),
    ("monthly-as-document-diff", "app/mod06_proc/service.py",
     'diffs = D.diff_rows(data["inv"], warehouse=warehouse)',
     'diffs = D.difference_rows(raw, adjusted)', "page_shape_document"),
    ("reload-for-each-export", "app/report_export/service.py",
     'tables = assembled["matrices"][key]',
     'tables = M6.build_matrices(session, warehouses=[key])["matrices"][key]', "zip_contents"),
    ("resurrect-rolled-back-history", "app/mod06_proc/service.py",
     "return R.load_history(session, **kw)",
     "return R.load_history(session, active_only=False, **kw)", "rollback_removes"),
    ("cutoff-hides-existing-mechanical", "app/mod06_proc/service.py",
     '"manual": manual, "history": history',
     '"manual": [row for row in manual if row["ym"] <= load_cutoffs(s).get(row["warehouse"], "")], "history": history',
     "each_effective_source"),
    ("omit-blank-subtotals", "app/report_export/process_export.py",
     'sub = {COL_OF_KEY[k]: totals[k] if totals[k] is not None else "" for k in D.DATA_KEYS}',
     'sub = {COL_OF_KEY[k]: totals[k] for k in D.DATA_KEYS if totals[k] is not None}',
     "subtotals_explicitly"),
]


def run(base, env, selection=""):
    command = [sys.executable, "-X", "utf8", "-m", "pytest", "-o", "addopts=-p tests.acc_plugin",
               "-q", "-p", "no:cacheprovider", "--tb=line", TEST]
    if selection:
        command.extend(["-k", selection])
    result = subprocess.run(command, cwd=base, env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    return result.returncode, result.stdout + result.stderr


def verify(base, env):
    """先正常放行，再逐个断言造红，最后复原放行；环境错误不算命中。"""
    env.update(SESSION_SECRET="isolated-proc-report-key", I8_USER="fake-env-i8",
               I8_PASSWORD="fake-env-i8-password", PYTHONDONTWRITEBYTECODE="1")
    originals = {ROOT / "backend" / row[1]: (ROOT / "backend" / row[1]).read_bytes() for row in MUTATIONS}
    code, output = run(base, env)
    if code:
        print(output)
        return 1
    print(output.strip().splitlines()[-1], flush=True)
    for label, relative, old, new, selection in MUTATIONS:
        path = base / relative
        original = path.read_bytes()
        newline = "\r\n" if b"\r\n" in original else "\n"
        old_bytes, new_bytes = (part.replace("\n", newline).encode() for part in (old, new))
        assert original.count(old_bytes) == 1, f"{label}: 变异锚不唯一或不存在"
        try:
            path.write_bytes(original.replace(old_bytes, new_bytes))
            code, output = run(base, env, selection)
            assertion = "AssertionError" in output or "E   assert " in output
            if code != 1 or "FAILED " not in output or not assertion or "ERROR tests/" in output:
                print(output)
                raise AssertionError(f"{label}: 未产生明确行为断言失败")
            print(f"{label}: 行为断言造红", flush=True)
        finally:
            path.write_bytes(original)
    code, output = run(base, env)
    if code:
        print(output)
        raise AssertionError("隔离复原后失败")
    assert all(path.read_bytes() == content for path, content in originals.items()), "正式源码字节被改变"
    print(output.strip().splitlines()[-1], flush=True)
    print(f"复原通过；{len(MUTATIONS)}/{len(MUTATIONS)}隔离靶命中；正式源码字节未变", flush=True)
    return 0


def main():
    with isolated_backend("tmp-proc-report-") as (base, env):
        return verify(base, env)


if __name__ == "__main__":
    raise SystemExit(main())
