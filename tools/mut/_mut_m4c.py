"""机械手录、月份校验、共享预览载具和路由引用的反向灵敏度。"""

from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import hashlib
import os
import pathlib
import subprocess

# ⛔ **结果隔离**（本仓纪律）：本脚本跑的是**子集** pytest ⇒ 必须把四态结果写到**临时文件**，
#    否则会把权威 `var/state/verification/acc_results.json` 冲成"只有这几条"（`doc_audit` 的 T4 立刻报红）。

ROOT = pathlib.Path(__file__).resolve().parents[2]
BE = ROOT / "backend"
PY = str(BE / ".venv/Scripts/python.exe")

#: `(说明, 相对路径, 原文, 替换, 该变异应被哪几个测试文件抓住)`
MUTATIONS: list[tuple[str, str, str, str, str]] = [
    ("① 手录放过负数（§8.4：机械 6 列 ≥ 0）",
     "backend/app/mod06_proc/mech_ui.py",
     "        if value < 0:\n            raise ValueError(f\"「{label}」不得为负数（当前 {value}）\")",
     "        if False:\n            raise ValueError(f\"「{label}」不得为负数（当前 {value}）\")",
     "tests/test_page_m06.py tests/test_acc_proc_002.py"),
    ("④ `YYYY-MM` 归一放过 13 月",
     "backend/app/mod06_proc/domain.py",
     "    if not 1 <= mm <= 12:",
     "    if False:",
     "tests/test_page_m06.py"),
    ("⑮ 预览暂存取不到时**回落成空**（而不是显式报错）",
     "backend/app/core/preview_store.py",
     "    if not path.exists():\n        raise MustReportError(EXPIRE_TIP)",
     "    if not path.exists():\n        return {}",
     "tests/test_page_m06.py"),
    ("⑯ 路由把出口挂到错的模块上（`normalize_ym` 其实住在 `domain`）",
     "backend/app/mod06_proc/router.py",
     "    ym = D.normalize_ym(req.ym)",
     "    ym = mech_ui.normalize_ym(req.ym)",
     "tests/test_router_refs.py tests/test_acc_rpt_big.py")
]


def _fit(fragment: str, sample: bytes) -> bytes:
    """把片段的行尾归一成 `sample` 的样子（本仓源码行尾不统一）。"""
    raw = fragment.replace("\r\n", "\n").encode("utf-8")
    if b"\r\n" in sample:
        return raw.replace(b"\n", b"\r\n")
    return raw


def run_tests(targets: str) -> int:
    return subprocess.run([PY, "-m", "pytest", *targets.split(), "-qq", "--no-header",
                           "-p", "no:cacheprovider"], cwd=BE, capture_output=True).returncode


def main() -> int:
    files = sorted({rel for _d, rel, _o, _n, _t in MUTATIONS})
    src0 = {f: (ROOT / f).read_bytes() for f in files}
    md5_0 = {f: hashlib.md5(b).hexdigest() for f, b in src0.items()}
    bad = 0
    for desc, rel, old_s, new_s, targets in MUTATIONS:
        src = src0[rel].replace(b"\r\n", b"\n")
        o, n = old_s.encode("utf-8"), new_s.encode("utf-8")
        if src.count(o) != 1:
            print(f"[SKIP ] ❓ {desc} —— 锚点命中 {src.count(o)} 次（应为 1）")
            bad += 1
            continue
        (ROOT / rel).write_bytes(_fit(src.replace(o, n, 1).decode("utf-8"), src0[rel]))
        rc = run_tests(targets)
        (ROOT / rel).write_bytes(src0[rel])
        print(f"[{'RED ' if rc else 'GREEN'}] {'✅' if rc else '❌'} {desc}")
        bad += 0 if rc else 1
    print("\n--- 还原复核（MD5 逐字节）---")
    for f in files:
        now = hashlib.md5((ROOT / f).read_bytes()).hexdigest()
        ok = now == md5_0[f]
        print(("OK  " if ok else "BAD "), f, now)
        bad += 0 if ok else 1
    print(f"\n合计问题 = {bad}（0 = 全部变异都被判据抓住、且源文件逐字节复原）")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
