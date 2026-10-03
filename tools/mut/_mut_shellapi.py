#!/usr/bin/env python
"""「壳的语义口径**认结构**、且查不到会喊」的反向灵敏度 —— 证明 `tests/test_shell_api.py` 那几条判据**真的有牙**。

守什么（`backend/tests/test_shell_api.py` · ⭐ `TAIL-219` 批 1 · 2026-10-03）：
- 壳的"界面口径"原先**没有可调用的窗口** ⇒ 13 件各写"按字面剪一段"的剪刀（实测 **16 把**）。
  批 1 立了 `tools/audit/shell_api.py`（`page_slice` / `func_body` / `act_entry` / `const_obj`）。
- 三条要守的性质：① **认结构**（配平跳过字符串/模板串/注释/正则）② **找不到 ⇒ 必抛**（⛔ 不静默回空）
  ③ 对象成员的**值要取整**（跨行也算，⛔ 不截在换行或半路）。

用法（在本仓根跑）：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\mut\\_mut_shellapi.py

⚠️ 逐字节复原 + MD5 校验（本仓规矩）；⚠️ 靶 = `tools/audit/shell_api.py` 一件（复原走 `finally`）。
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
R = pathlib.Path(r"D:\dev\mtrl-workbench")
PY = R / "backend" / ".venv" / "Scripts" / "python.exe"
TARGET = R / "tools" / "audit" / "shell_api.py"
TEST = "tests/test_shell_api.py"          # ← 台账「验的判据」列抓这一串

#: 变异①：`_match` 里不认字符串 ⇒ 字符串里的 `}` 会被当成收尾
M1_OLD = """        if c in _QUOTES:
            i = _skip_string(s, i)
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            j = s.find("\\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "*":
            j = s.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c == "/" and _regex_ok(s, i):
            i = _skip_regex(s, i)
            continue
        if c == open_ch:
"""
M1_NEW = M1_OLD.replace("        if c in _QUOTES:\n",
                        "        if False and c in _QUOTES:      # 变异 M1：不认字符串\n", 1)
M1_TEST = "test_取函数体_认结构"

#: 变异②：`page_slice` 找不到时静默回空（⛔ 那是"看着绿、其实什么都没查"）
M2_OLD = """    if page not in m:
        raise LookupError(f"壳里没有 `V.{page}=` 切片（现有：{', '.join(sorted(m))}）")
"""
M2_NEW = """    if page not in m:
        return ""                            # 变异 M2：静默回空
"""
M2_TEST = "test_取不到必须抛_不许静默回空"

#: 变异③：定位**不先剥注释** ⇒ 注释里那份"列 0 的假定义"会被当成真的
M3_OLD = "    return source, _blank_comments(source)\n"
M3_NEW = "    return source, source                       # 变异 M3：定位不剥注释\n"
M3_TEST = "test_取动作条_注释里列0的假定义不算数"


def md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def run_test() -> tuple[int, str]:
    r = subprocess.run([str(PY), "-X", "utf8", "-m", "pytest", TEST, "-q", "-o", "addopts=",
                        "-p", "no:cacheprovider"],
                       cwd=R / "backend", capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    fail: list[str] = []
    orig = TARGET.read_bytes()

    rc0, out0 = run_test()
    print(f"基线：{TEST} ⇒ rc={rc0}")
    if rc0 != 0:
        print(out0[-900:])
        print("⛔ 基线就不是绿的 ⇒ 先把判据修绿（否则本件测不了东西）")
        return 1

    try:
        for tag, old, new, name in (("①", M1_OLD, M1_NEW, M1_TEST),
                                    ("②", M2_OLD, M2_NEW, M2_TEST),
                                    ("③", M3_OLD, M3_NEW, M3_TEST)):
            src = orig.decode("utf-8")
            assert old in src, f"⚠️ 变异{tag} 锚点没命中（`shell_api.py` 变了？先核再改本件）"
            TARGET.write_bytes(src.replace(old, new, 1).encode("utf-8"))
            rc, out = run_test()
            hit = name in out
            print(f"  变异{tag}（{name}）⇒ rc={rc} · 命中该条={hit}")
            if rc == 0 or not hit:
                fail.append(f"{tag} 改坏了但没红/没命中（rc={rc}）—— 判据没牙")
            TARGET.write_bytes(orig)
            if TARGET.read_bytes() != orig:
                fail.append(f"{tag} 没复原")
    finally:
        TARGET.write_bytes(orig)

    if TARGET.read_bytes() != orig:
        fail.append("复原不完整")
    else:
        print(f"复原 ✅ MD5 {md5(orig)}")
    rcN, _ = run_test()
    if rcN != 0:
        fail.append(f"复原后判据仍红（rc={rcN}）—— 留下了坏态")

    if fail:
        print("❌ " + "；".join(fail))
        return 1
    print(f"✅ 有区分力：三条都必红 · 复原后 rc={rcN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
