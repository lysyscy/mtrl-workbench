#!/usr/bin/env python
"""反向灵敏度：依赖清单不许漏登记（守 backend/tests/test_deps_declared.py）。

守什么（2026-10-05 立 · 出处 = `M8 ①` 落地第一天）：`app/import_kit/readers.py` 按魔术字节认老
`.xls` 并 `import xlrd`，而 `backend/requirements.txt` **从来没登记过它** ⇒ 换机落地后 venv 里没有
⇒ 用户的集采台账（三份全是 `.xls`）一导就「解析失败 —— 请重试」，而**开发机 venv 什么都有 ⇒ 本机测不出来**。

跑法（仓根）：backend/.venv/Scripts/python.exe -X utf8 tools/mut/_mut_deps.py
⚠️ 逐字节复原 + MD5（本仓规矩）。⚠️ 两头都打：① 删 `xlrd` 行 ② 删 `openpyxl` 行
（① 证明「点名那条」有牙；② 证明「全量扫那条」**不是只对 xlrd 特判**）。
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
REQS = ROOT / "backend" / "requirements.txt"          # ← 靶：依赖清单（唯一主人）
TEST = "tests/test_deps_declared.py"
T1 = "test_代码里用到的第三方库都在依赖清单里"
T2 = "test_老xls台账的读表件在依赖清单里"


def md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def run_test() -> tuple[int, str]:
    """跑**那两条**判据（子进程 · 走真 pytest）。"""
    r = subprocess.run([str(PY), "-X", "utf8", "-m", "pytest", TEST, "-q", "-o", "addopts=",
                        "-p", "no:cacheprovider"],
                       cwd=ROOT / "backend", capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def drop_line(raw: bytes, prefix: bytes) -> bytes:
    """从清单原始字节里删掉以 `prefix` 开头的那一行（**含换行**）—— 逐字节操作，不重排任何东西。"""
    lines = raw.splitlines(keepends=True)
    kept = [ln for ln in lines if not ln.lstrip().startswith(prefix)]
    assert len(kept) == len(lines) - 1, (
        f"⚠️ 锚点没命中 —— 清单里没有 `{prefix.decode()}` 这一行？先核 requirements.txt 再改本件")
    return b"".join(kept)


def main() -> int:
    fail: list[str] = []
    rc1 = rc2 = -1
    if not REQS.exists():
        print(f"⛔ 依赖清单不在（{REQS}）⇒ 没东西可验")
        return 1
    orig = REQS.read_bytes()

    rc0, out0 = run_test()
    print(f"基线：{TEST} ⇒ rc={rc0}")
    if rc0 != 0:
        print(out0[-800:])
        print("⛔ 基线就不是绿的 ⇒ 先把判据修绿（否则本件测不了东西）")
        return 1

    try:
        print("变异①：删掉清单里的 `xlrd==2.0.1` ⇒ 两条判据都必须红…")
        REQS.write_bytes(drop_line(orig, b"xlrd=="))
        rc1, out1 = run_test()
        if rc1 == 0 or T1 not in out1 or T2 not in out1:
            fail.append(f"① 删了 xlrd 但没红（rc={rc1}）—— 判据没牙")
        REQS.write_bytes(orig)
        if orig != REQS.read_bytes():
            fail.append("① 清单没复原")

        print("变异②：删掉清单里的 `openpyxl==…` ⇒ 「全量扫」那条必须红（证明不是只对 xlrd 特判）…")
        REQS.write_bytes(drop_line(orig, b"openpyxl=="))
        rc2, out2 = run_test()
        if rc2 == 0 or T1 not in out2:
            fail.append(f"② 删了 openpyxl 但没红（rc={rc2}）—— 全量扫那条没牙")
    finally:
        REQS.write_bytes(orig)

    if REQS.read_bytes() != orig:
        fail.append("复原不完整（清单要逐字节回到原样）")
    else:
        print(f"复原 ✅ 清单 MD5 {md5(orig)}")
    rcN, outN = run_test()
    if rcN != 0:
        fail.append(f"复原后判据仍红（rc={rcN}）—— 留下了坏态")

    if fail:
        print("❌ " + "；".join(fail))
        return 1
    print(f"✅ 有区分力：①删 xlrd ⇒ rc={rc1} · ②删 openpyxl ⇒ rc={rc2} · 复原后 rc={rcN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
