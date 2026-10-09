"""双截止和机械覆盖：只改隔离副本，正常通过后确认指定缺陷能被判据捕获。"""
from pathlib import Path
import subprocess
import sys
from _isolated import isolated_backend

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    ("类别截止", "mod06_proc/importer.py", "limit = mech_cutoff if key in D.MECH_KEYS else cutoff",
     "limit = cutoff", "test_category_cutoffs_filter_before_amount_validation"),
    ("截止不挡读取", "mod06_proc/domain.py", "return SOURCE_SNAPSHOT\n\n\ndef column_editable",
     "return SOURCE_SNAPSHOT if section_of(ym, cutoff_ym) == SECTION_HISTORY else SOURCE_INV\n\n\ndef column_editable", "test_effective_sources_ignore_import_cutoffs"),
    ("重导不累加", "mod06_proc/repository.py", "setattr(effective, key, value)",
     "setattr(effective, key, (getattr(effective, key) or 0) + value)", "test_import_manual_reimport_and_rollback_preserve_later_edits"),
    ("回滚保后改", "mod06_proc/repository.py", "if origins.get(change.column_key) != batch_no:",
     "if False:", "test_import_manual_reimport_and_rollback_preserve_later_edits"),
    ("数字零写入", "mod06_proc/importer.py", 'has_amounts=any(rec.get(lb) not in (None, "") for lb in amount_labels)',
     'has_amounts=any(bool(rec.get(lb)) for lb in amount_labels)', "test_numeric_zero_is_imported_and_category_defaults_are_independent"),
    ("回滚保手录零", "mod06_proc/repository.py", 'and not origins.get("__manual") and no_remaining_import',
     'and no_remaining_import', "test_rollback_removes_only_import_created_month_and_preserves_explicit_manual_zero"),
]


def main():
    with isolated_backend("tmp-proc-split-mut-") as (base, env):
        for label, rel, old, new, test in CASES:
            cmd = [str(ROOT / "backend/.venv/Scripts/python.exe"), "-X", "utf8", "-m", "pytest",
                   "tests/test_proc_split_cutoffs.py::" + test, "-q", "--tb=short"]
            normal = subprocess.run(cmd, cwd=base, env=env, capture_output=True, text=True, encoding="utf-8", timeout=45)
            assert normal.returncode == 0, normal.stdout + normal.stderr
            path = base / "app" / rel
            original = path.read_bytes()
            source = original.decode("utf-8").replace("\r\n", "\n")
            assert source.count(old) == 1, (label, source.count(old))
            path.write_text(source.replace(old, new), encoding="utf-8")
            try:
                red = subprocess.run(cmd, cwd=base, env=env, capture_output=True, text=True, encoding="utf-8", timeout=45)
                assert red.returncode and "FAILED " in red.stdout, red.stdout + red.stderr
                print("PASS 正常绿、指定缺陷红：" + label, flush=True)
            finally:
                path.write_bytes(original)
    return 0


if __name__ == "__main__":
    sys.exit(main())
