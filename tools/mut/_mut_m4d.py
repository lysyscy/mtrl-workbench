"""**真机抓取暴露的两处修复**的反向灵敏度：把实现改回坏样子，确认断言**确实变红**。

跑法：`python tools/_mut_m4d.py`（工程根）—— 退出码非 0 = 有"仍绿"或有还原失败。
⚠️ 三条纪律同 `tools/_mut_m4c.py`（`_fit()` 归一 · 中文用 `str` · 跑完必须重跑全套 `pytest`）。
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
BE = ROOT / "backend"
PY = str(BE / ".venv/Scripts/python.exe")

MUTATIONS: list[tuple[str, str, str, str, str]] = [
    ("① 幂等范围退回「只按核算年月」（同月多仓库会互相删行 —— 真机实测 559→18）",
     "backend/app/mod08_inv/repository.py",
     "    existing = {_key_of(d): d for d in list_details(s, ym=(ym or None))\n"
     "                if str(d.warehouse_name or \"\") == str(warehouse or \"\")}",
     "    existing = {_key_of(d): d for d in list_details(s, ym=(ym or None))}",
     "tests/test_acc_inv_fetch.py"),

    ("② 表头认列退回「上下拼接」（真机表头是 分组名＋真实列名 ⇒ 关键列全认不出）",
     "backend/app/mod07_setl/importer.py",
     "    rows = [grid[r] for r in range(min(depth, len(grid)))]\n"
     "    width = max((len(r) for r in rows), default=0)\n"
     "    out: list[str] = []\n"
     "    for c in range(width):\n"
     "        name = \"\"\n"
     "        for row in rows:                       # 自上而下 ⇒ 最后一个非空者胜出\n"
     "            v = row[c] if c < len(row) else \"\"\n"
     "            if v:\n"
     "                name = v\n"
     "        out.append(name)\n"
     "    return out",
     "    width = max((len(grid[r]) for r in range(min(depth, len(grid)))), default=0)\n"
     "    out: list[str] = []\n"
     "    for c in range(width):\n"
     "        parts: list[str] = []\n"
     "        for r in range(min(depth, len(grid))):\n"
     "            v = grid[r][c] if c < len(grid[r]) else \"\"\n"
     "            if v and v not in parts:\n"
     "                parts.append(v)\n"
     "        out.append(\"\".join(parts))\n"
     "    return out",
     "tests/test_acc_setl_fetch.py"),

    ("③ 只试 1 行表头（不再试 2 行 ⇒ 真机两行表头直接认不出）",
     "backend/app/mod07_setl/importer.py",
     "    for depth in (2, 1):",
     "    for depth in (1,):",
     "tests/test_acc_setl_fetch.py"),
]


def _fit(fragment: str, sample: bytes) -> bytes:
    raw = fragment.replace("\r\n", "\n").encode("utf-8")
    return raw.replace(b"\n", b"\r\n") if b"\r\n" in sample else raw


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
