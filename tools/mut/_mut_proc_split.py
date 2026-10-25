"""历史读取不受旧导入截止遮挡；只修改隔离副本。"""
from pathlib import Path
import subprocess
import sys
from _isolated import isolated_backend

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    ("截止不挡读取", "mod06_proc/domain.py", "return SOURCE_SNAPSHOT\n\n\ndef column_editable",
     "return SOURCE_SNAPSHOT if section_of(ym, cutoff_ym) == SECTION_HISTORY else SOURCE_INV\n\n\ndef column_editable", "test_effective_sources_ignore_import_cutoffs")
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
