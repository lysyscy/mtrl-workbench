"""单格机械保存保留其他列金额和来源；仅在隔离副本造出误清其他列的缺陷。"""
from pathlib import Path
import subprocess
import sys
from _isolated import isolated_backend

ROOT = Path(__file__).resolve().parents[2]


def main():
    with isolated_backend("tmp-tail270-") as (base, env):
        cmd = [sys.executable, "-X", "utf8", "-m", "pytest",
               "tests/test_proc_split_cutoffs.py::test_single_cell_api_preserves_other_amounts_and_origins",
               "-q", "--tb=short"]
        normal = subprocess.run(cmd, cwd=base, env=env, capture_output=True,
                                text=True, encoding="utf-8", timeout=60)
        assert normal.returncode == 0, normal.stdout + normal.stderr
        path = base / "app/mod06_proc/router.py"
        source = path.read_text(encoding="utf-8")
        target = "if k in req.values}"
        assert source.count(target) == 1
        path.write_text(source.replace(target, "if True}"), encoding="utf-8")
        red = subprocess.run(cmd, cwd=base, env=env, capture_output=True,
                             text=True, encoding="utf-8", timeout=60)
        assert red.returncode and "FAILED " in red.stdout, red.stdout + red.stderr
        print("PASS 正常绿、误清其他机械列红（隔离副本，测试库事务回滚）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
