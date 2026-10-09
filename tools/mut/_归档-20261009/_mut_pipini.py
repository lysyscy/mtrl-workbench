#!/usr/bin/env python
"""「**依赖镜像只有一处定义**」的反向灵敏度 —— 证明 `tests/test_pipini_single_source.py` 那条判据**真的有牙**。

守什么（`backend/tests/test_pipini_single_source.py`）：
- ⭐ 2026-10-02（用户选「乙」）立：镜像 URL 原先**只**活在 `backend/.venv/pip.ini` 里，而 `.venv` 是
  `.gitignore` 挡掉的 ⇒ **不进 bundle** ⇒ 目标机**重建 venv** 后那份加固**当场失效**（悄悄走默认
  PyPI 官方源），而 `deploy_restore.ps1` 一个字都不报。修法 = **真源搬进仓**（`ops/pip.ini`）＋
  落地脚本复制成 venv 级。
- 判据守的是**「一处定义」**：`ops/pip.ini` = 唯一主人；`backend/.venv/pip.ini` = **副本**，两份必须**逐字节相同**。
- ⚠️ 所以本件**两头都打**：① 把**真源**改坏（指回官方源）② 把**副本**改坏（与真源不一致）；
  任一头单独破 ⇒ 都该红（这里不像"铁律在两头"那种需要同破的情形：两半各有一条断言）。

用法（在本仓根跑）：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\mut\\_mut_pipini.py

⚠️ 逐字节复原 + MD5 校验（本仓规矩）；⚠️ 副本原先**不存在**时（别的机器）会自动造一份再打，打完还原成"不存在"。
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
R = pathlib.Path(r"D:\dev\mtrl-workbench")
PY = R / "backend" / ".venv" / "Scripts" / "python.exe"
SRC = R / "ops" / "pip.ini"                        # ⭐ 真源（唯一主人）
DST = R / "backend" / ".venv" / "pip.ini"          # 副本（由 deploy_restore.ps1 落）
TEST = "tests/test_pipini_single_source.py"        # ← 台账「验的判据」列抓这一串
T1 = "test_依赖镜像的真源在仓里_且不是官方源"
T2 = "test_venv_那份是真源的副本_逐字节相同"


def md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def run_test() -> tuple[int, str]:
    """跑**那一条**判据（子进程 · 走真 pytest）。"""
    r = subprocess.run([str(PY), "-X", "utf8", "-m", "pytest", TEST, "-q", "-o", "addopts=",
                        "-p", "no:cacheprovider"],
                       cwd=R / "backend", capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    fail: list[str] = []

    if not SRC.exists():
        print(f"⛔ 真源不在（{SRC}）⇒ 先把它补回来再验")
        return 1
    src_orig = SRC.read_bytes()
    dst_existed = DST.exists()
    dst_orig = DST.read_bytes() if dst_existed else b""
    if not dst_existed:                       # 别的机器上副本可能不存在 ⇒ 造一份，验完还原成"不存在"
        DST.parent.mkdir(parents=True, exist_ok=True)
        DST.write_bytes(src_orig)

    rc0, out0 = run_test()
    print(f"基线：{TEST} ⇒ rc={rc0}")
    if rc0 != 0:
        print(out0[-800:])
        print("⛔ 基线就不是绿的 ⇒ 先把判据修绿（否则本件测不了东西）")
        return 1

    try:
        # ---- ① 打**真源**：指回官方源 ⇒ 「真源在、且不是官方源」那条必须红 ----
        print("变异①：把真源 `ops/pip.ini` 的 index-url 指回官方源 ⇒ 必红…")
        bad = src_orig.replace(b"https://mirrors.aliyun.com/pypi/simple/", b"https://pypi.org/simple/")
        assert bad != src_orig, "⚠️ 锚点没命中 —— 真源里的镜像 URL 变了？先核 `ops/pip.ini` 再改本件"
        SRC.write_bytes(bad)
        rc1, out1 = run_test()
        if rc1 == 0 or T1 not in out1:
            fail.append(f"① 真源改坏了但没红（rc={rc1}）—— 判据没牙")
        SRC.write_bytes(src_orig)
        if src_orig != SRC.read_bytes():
            fail.append("① 真源没复原")

        # ---- ② 打**副本**：与真源不一致 ⇒ 「两份逐字节相同」那条必须红 ----
        print("变异②：把副本 `backend/.venv/pip.ini` 改一行 ⇒ 必红（守「一处定义」）…")
        DST.write_bytes(dst_orig + b"\n" if dst_existed else src_orig + b"\n")
        rc2, out2 = run_test()
        if rc2 == 0 or T2 not in out2:
            fail.append(f"② 副本改坏了但没红（rc={rc2}）—— 判据没牙")
    finally:
        SRC.write_bytes(src_orig)
        if dst_existed:
            DST.write_bytes(dst_orig)
        else:
            DST.unlink(missing_ok=True)

    # ---- 复原 + 复检 ----
    if SRC.read_bytes() != src_orig or (DST.exists() != dst_existed):
        fail.append("复原不完整（真源 / 副本的存在性与字节要对上）")
    else:
        print(f"复原 ✅ 真源 MD5 {md5(src_orig)}"
              + (f" · 副本 MD5 {md5(dst_orig)}" if dst_existed else " · 副本原就无（已还原成无）"))
    rcN, outN = run_test()
    if rcN != 0:
        fail.append(f"复原后判据仍红（rc={rcN}）—— 留下了坏态")

    if fail:
        print("❌ " + "；".join(fail))
        return 1
    print(f"✅ 有区分力：①真源改坏 ⇒ rc={rc1} · ②副本改坏 ⇒ rc={rc2} · 复原后 rc={rcN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
