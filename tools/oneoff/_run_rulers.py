"""收口闸门一把跑：16 把尺子逐个跑、只打印"该读的那几行"，rc≠0 的列进 `BAD`。

**为什么单独落成文件**：2026-09-29 实测 —— 这套命令用 `python -c "…\\nfor …"` 的**内联多行**写法
在 PowerShell 里**反复被吃掉换行**（`unexpected character after line continuation character` ✗）。
⇒ 凡是"反复要跑的一串命令"，落成脚本；⛔ 别在命令行里拼多行 Python。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_run_rulers.py`
      `… --all`   #: 连 pytest 一起跑（默认只跑尺子 —— 没动代码时不必）
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")

KEEP = ("必须修", "结论", "_smoke", "_links", "_ids", "_doccheck", "台账一致", "逐行一致",
        "判据点合计", "幽灵", "[T6]", "[T10]", "[T13]", "[T20]")

CMDS: list[tuple[str, list[str]]] = [
    ("tools/audit/doc_audit.py", ["--ui"]),
    ("tools/audit/audit_drift.py", []),
    ("tools/audit/audit_meta.py", []),
    ("tools/audit/syntax_audit.py", []),
    ("tools/audit/ui_parity.py", []),
    ("tools/audit/wiring_audit.py", []),
    ("tools/audit/chain_audit.py", []),
    ("tools/audit/asset_audit.py", []),
    ("tools/audit/claim_audit.py", []),
    ("tools/audit/cover_gap.py", []),
    ("tools/audit/prg_form_audit.py", []),
    ("tools/audit/shell_verify.py", []),
    ("tools/audit/sticky_probe.py", []),
    ("tools/audit/mut_cover.py", ["--check"]),
    ("tools/audit/acc_report.py", []),
    ("tools/probe/_audit_face.py", []),
]


def main() -> int:
    with_pytest = "--all" in sys.argv
    bad: list[str] = []
    for rel, args in CMDS:
        p = subprocess.run([PY, "-X", "utf8", str(ROOT / rel)] + args, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
        ls = [x for x in (p.stdout or "").strip().splitlines() if x.strip()]
        keep = [x for x in ls if any(k in x for k in KEEP)]
        print("%-34s rc=%d  %s" % (rel, p.returncode, " || ".join(keep[:3])[:175]))
        if p.returncode:
            bad.append(rel)
    if with_pytest:
        env = {"ACC_RESULTS_PATH": str(ROOT / "artifacts" / "acc_results.json"),
               "PLAYWRIGHT_BROWSERS_PATH": r"C:\ProgramData\ms-playwright",
               "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
        import os
        e = dict(os.environ, **env)
        p = subprocess.run([PY, "-m", "pytest", "-q", "tests/", "-p", "no:cacheprovider", "--tb=line"],
                           cwd=str(ROOT / "backend"), env=e, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        tail = [x for x in (p.stdout or "").strip().splitlines() if x.strip()][-2:]
        print("%-34s rc=%d  %s" % ("pytest", p.returncode, " || ".join(tail)[:175]))
        if p.returncode:
            bad.append("pytest")
    print("BAD:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
