"""Independent process cutoff and unrestricted mechanical edit negative witnesses."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    ("mechanical month payload", "legacy.js",
     "mechanical_cutoff_ym: mechCut ? mechCut.value : IMP.mechanicalCutoff",
     "mechanical_cutoff_ym: cut ? cut.value : IMP.cutoff",
     "test_independent_cutoffs_preview_invalidation_and_project_switch"),
    ("mechanical preview invalidation", "legacy.js",
     "ACT.impMechCutEdit=t=>{IMP.mechanicalCutoff=t.value;IMP.preview=null;IMP.problems=[];};",
     "ACT.impMechCutEdit=t=>{IMP.mechanicalCutoff=t.value;IMP.problems=[];};",
     "test_independent_cutoffs_preview_invalidation_and_project_switch"),
    ("project mechanical month", "legacy.js",
     "if (IMP.hasMechCut) IMP.mechanicalCutoff = String((IMP.mechanicalCutoffs || {})[v] || '');",
     "if (IMP.hasMechCut) IMP.mechanicalCutoff = String((IMP.cutoffs || {})[v] || '');",
     "test_independent_cutoffs_preview_invalidation_and_project_switch"),
    ("history edit block", "actions.js", "   let ok=0, fail='';",
     "   if((MECH_SECTIONS[wh]||{})[ym]==='history') return;\n   let ok=0, fail='';",
     "test_mechanical_history_month_reaches_real_save_action"),
]


def main():
    with tempfile.TemporaryDirectory(prefix="tmp-proc-split-shell-", dir=ROOT / ".scratch/local") as folder:
        isolated = Path(folder)
        for part in ("backend/app", "backend/tests", "tools/audit"):
            shutil.copytree(ROOT / part, isolated / part, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(ROOT / "backend/pytest.ini", isolated / "backend/pytest.ini")
        env = os.environ.copy()
        env["ACC_RESULTS_PATH"] = str(isolated / "results.json")
        def run(test):
            return subprocess.run([str(ROOT / "backend/.venv/Scripts/python.exe"), "-X", "utf8", "-m", "pytest",
                                   "tests/test_proc_split_shell.py::" + test, "-q", "--tb=short"],
                                  cwd=isolated / "backend", env=env, capture_output=True, text=True, encoding="utf-8", timeout=45)
        for label, file, old, new, test in CASES:
            good = run(test)
            assert good.returncode == 0, good.stdout + good.stderr
            target = isolated / "backend/app/web/shell" / file
            original = target.read_bytes()
            source = original.decode("utf-8").replace("\r\n", "\n")
            assert source.count(old) == 1, (label, source.count(old))
            target.write_bytes(source.replace(old, new).encode("utf-8"))
            try:
                bad = run(test)
                assert bad.returncode != 0 and "FAILED " in bad.stdout, bad.stdout + bad.stderr
                print("PASS normal green / defect red: " + label, flush=True)
            finally:
                target.write_bytes(original)


if __name__ == "__main__":
    main()
