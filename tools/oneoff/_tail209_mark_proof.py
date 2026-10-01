"""`TAIL-209` 余项 ② 自证：**壳源码扫查类的两条判据**都"真会拦、且不误伤注释"。

被证的两条（都在 `backend/tests/test_ux_text.py`）：
  `T1` = `test_壳源码里不许有双层星号_加粗标记`（`**` 加粗标记不许原样上屏）
  `T2` = `test_用户可见串里不许出现工程代号`（`（R8）` / `DEV-J-01` / `链路 A` … 不许上屏）

证 5 个点（缺一面这个自证就没意义）：
  ① 基线：两条都绿；
  ② 往壳件**字符串**里塞 `**x**` ⇒ `T1` **必须红**；
  ③ 往壳件**字符串**里塞 `（R99）` ⇒ `T2` **必须红**；
  ④ 往壳件**注释**里塞 `**…**` 与 `（R99）` ⇒ 两条**必须仍绿**（注释不是上屏文字 ——
     壳里 `DEV-*` / `链路 X` / `决策 N` / 大量 `**` **只活在注释里**，这是"不误伤"的关键一条）；
  ⑤ 逐字节还原（MD5 比对）。
⚠️ 别拿"加了一点点没红"当证据（2026-10-01 踩过：自证加长没顶破阈值 ⇒ 假通过）。
⚠️ 本件被 §13.6 的**入门口令**点名 ⇒ 必须有 `main()` ＋ `__main__`（`T17` 守）。
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
W = ROOT / "backend" / "app" / "web"
CODE_TARGET = W / "shell" / "legacy.js"
CMT_TARGET = W / "shell" / "api.js"
ANCHOR = "<b>整批回滚后重导</b>"
T1 = "tests/test_ux_text.py::test_壳源码里不许有双层星号_加粗标记"
T2 = "tests/test_ux_text.py::test_用户可见串里不许出现工程代号"

_ENV = {"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}


def _rc(test: str) -> int:
    run = [str(ROOT / "backend/.venv/Scripts/python.exe"), "-X", "utf8", "-m", "pytest", "-q", test,
           "-p", "no:cacheprovider", "--tb=no", "--no-header"]
    r = subprocess.run(run, cwd=ROOT / "backend", env={**os.environ, **_ENV},
                       capture_output=True, text=True, encoding="utf-8")
    print(f"   {test.rsplit('::', 1)[-1][:28]:30s} rc={r.returncode}")
    return r.returncode


def main() -> int:
    code_orig, cmt_orig = CODE_TARGET.read_bytes(), CMT_TARGET.read_bytes()
    h_code, h_cmt = hashlib.md5(code_orig).hexdigest(), hashlib.md5(cmt_orig).hexdigest()
    code_txt = code_orig.decode("utf-8")
    if code_txt.count(ANCHOR) != 1:
        print(f"⛔ 锚点不唯一（{code_txt.count(ANCHOR)} 处）—— 自证要重定靶")
        return 1

    ok = False
    try:
        print("① 基线（未改动）—— 两条都必须绿")
        base = _rc(T1) == 0 and _rc(T2) == 0

        print("② 往**字符串**里塞 `**x**` ⇒ T1 必须红")
        CODE_TARGET.write_text(code_txt.replace(ANCHOR, f"**x**{ANCHOR}", 1),
                               encoding="utf-8", newline="")
        t1_red = _rc(T1) != 0
        CODE_TARGET.write_bytes(code_orig)

        print("③ 往**字符串**里塞 `（R99）` ⇒ T2 必须红")
        CODE_TARGET.write_text(code_txt.replace(ANCHOR, f"（R99）{ANCHOR}", 1),
                               encoding="utf-8", newline="")
        t2_red = _rc(T2) != 0
        CODE_TARGET.write_bytes(code_orig)

        print("④ 往**注释**里塞 `**…**` 与 `（R99）` ⇒ 两条必须仍绿（注释不是上屏文字）")
        CMT_TARGET.write_text(cmt_orig.decode("utf-8")
                              + "\n/* **自证用：注释里的星号与（R99）都不该被算** */\n",
                              encoding="utf-8", newline="")
        cmt_ok = _rc(T1) == 0 and _rc(T2) == 0
        ok = base and t1_red and t2_red and cmt_ok
    finally:
        CODE_TARGET.write_bytes(code_orig)
        CMT_TARGET.write_bytes(cmt_orig)

    clean = (hashlib.md5(CODE_TARGET.read_bytes()).hexdigest() == h_code
             and hashlib.md5(CMT_TARGET.read_bytes()).hexdigest() == h_cmt)
    print(f"⑤ 逐字节还原：{'✅ 一致' if clean else '❌ 不一致！'}")
    print("结论：" + ("✅ 两条判据都有区分力（写进去必红）＋ 不误伤注释 ＋ 还原干净"
                     if ok and clean else "❌ 见上面"))
    return 0 if ok and clean else 1


if __name__ == "__main__":
    sys.exit(main())
