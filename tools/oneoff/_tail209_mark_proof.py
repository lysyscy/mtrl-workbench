"""`TAIL-209` 余项 ② 自证：新判据 `test_壳源码里不许有双层星号_加粗标记` **真会拦、且不误伤注释**。

两面都证（缺一面这个自证就没意义）：
  ① **有区分力**：往壳件**字符串**里塞一个 `**x**` ⇒ 判据**必须红**（⛔ 别拿"加了一点点没红"当证据）；
  ② **不假阳性**：往壳件**注释**里塞 `**…**` ⇒ 判据**必须仍绿**（注释里 Markdown 加粗极多，
     这正是本仓"扫源码"类检查历史上栽跟头的地方 ⇒ 必须专门证一次）。
跑完**逐字节还原**（MD5 比对）。

⚠️ 为什么要有它：判据的靶在**弹窗 / `title` / `toast`** 这些真机 ㉙ 视野外的地方 ⇒
   ⛔ 不能只靠"看着对"，要有"写进去必红"的证据（`TAIL-205` 那条纪律：判据带反向灵敏度）。
⚠️ 本件被 §13.6 的**入门口令**点名 ⇒ 必须有 `main()` ＋ `__main__`（`T17` 守「口令里列的件不许是僵尸闸门」）。
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
TEST = "tests/test_ux_text.py::test_壳源码里不许有双层星号_加粗标记"

_ENV = {"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
_RUN = [str(ROOT / "backend/.venv/Scripts/python.exe"), "-X", "utf8", "-m", "pytest", "-q", TEST,
        "-p", "no:cacheprovider", "--tb=no", "--no-header"]


def _leak(tag: str) -> int:
    r = subprocess.run(_RUN, cwd=ROOT / "backend", env={**os.environ, **_ENV},
                       capture_output=True, text=True, encoding="utf-8")
    print(f"   {tag} ⇒ rc={r.returncode}")
    return r.returncode


def main() -> int:
    code_orig = CODE_TARGET.read_bytes()
    cmt_orig = CMT_TARGET.read_bytes()
    h_code, h_cmt = hashlib.md5(code_orig).hexdigest(), hashlib.md5(cmt_orig).hexdigest()
    code_txt = code_orig.decode("utf-8")
    if code_txt.count(ANCHOR) != 1:
        print(f"⛔ 锚点不唯一（{code_txt.count(ANCHOR)} 处）—— 自证要重定靶")
        return 1

    ok = False
    try:
        print("① 基线（未改动）")
        base = _leak("基线")
        print("② 往**字符串**里塞 `**x**`（必须红）")
        CODE_TARGET.write_text(code_txt.replace(ANCHOR, f"**x**{ANCHOR}", 1),
                               encoding="utf-8", newline="")
        mut = _leak("变异码")
        CODE_TARGET.write_bytes(code_orig)
        print("③ 往**注释**里塞 `**…**`（必须仍绿 —— 注释不是上屏文字）")
        CMT_TARGET.write_text(cmt_orig.decode("utf-8") + "\n/* **自证用：注释里的星号不该被算** */\n",
                              encoding="utf-8", newline="")
        cmt = _leak("变异注释")
        ok = base == 0 and mut != 0 and cmt == 0
    finally:
        CODE_TARGET.write_bytes(code_orig)
        CMT_TARGET.write_bytes(cmt_orig)

    after_code = hashlib.md5(CODE_TARGET.read_bytes()).hexdigest()
    after_cmt = hashlib.md5(CMT_TARGET.read_bytes()).hexdigest()
    clean = after_code == h_code and after_cmt == h_cmt
    print(f"④ 逐字节还原：{'✅ 一致' if clean else '❌ 不一致！'}")
    print("结论：" + ("✅ 判据有区分力（写 `**` 必红）＋ 不误伤注释 ＋ 还原干净"
                     if ok and clean else "❌ 见上面"))
    return 0 if ok and clean else 1


if __name__ == "__main__":
    sys.exit(main())
