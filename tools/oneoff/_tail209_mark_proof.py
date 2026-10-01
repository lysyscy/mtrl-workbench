"""源码扫查类判据的自证（`TAIL-209` ＋ 第二轮 ＋ `TAIL-211`）：**每条都要"写进去必红 ＋ 注释里不算"**。

被证的五条（都在 `backend/tests/test_ux_text.py`）：
  `T1` = `test_壳源码里不许有双层星号_加粗标记`（`**` 不许原样上屏）
  `T2` = `test_用户可见串里不许出现工程代号`（`（R8）` / `DEV-J-01` / `链路 A` …）—— 靶 = **壳**
  `T3` = `test_悬停文案也不超长`（`title="…"` > 200 字）
  `T4` = `test_用户可见串里不许出现工程侧文件名`（`ops/…` / `.codebuddy` / `.md` …）—— 靶 = **壳**
  `T5` = `test_后端的用户可见串里也不许出现工程代号`（`TAIL-211` 补的**后端那一半**）

怎么证（每条都注入到**真实文件**、跑完**逐字节还原**）：
  ① 基线：五条都绿；
  ② 逐条往**字符串**里塞该条要拦的东西 ⇒ 那条**必须红**（`T1`–`T4` 塞进壳件 `shell/legacy.js`；
     `T5` 塞进一个**后端模块**，⚠️ 必须是**赋值**形态 —— 裸字符串语句按口径**不算**）；
  ③ 反向：四样东西一起塞进**壳里的块注释** ⇒ `T1`–`T4` 必须仍绿；
     `T5` 那边另给两样：**注释** ＋ **裸字符串语句**（"文档式"）⇒ 必须仍绿；
  ④ 两个文件**逐字节还原**（MD5 比对）。
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
TARGET = ROOT / "backend" / "app" / "web" / "shell" / "legacy.js"          # 壳件（T1–T4 的靶）
BACK = ROOT / "backend" / "app" / "mod09_fee" / "service.py"               # 后端件（T5 的靶）
TEST = "tests/test_ux_text.py::"

T1 = TEST + "test_壳源码里不许有双层星号_加粗标记"
T2 = TEST + "test_用户可见串里不许出现工程代号"
T3 = TEST + "test_悬停文案也不超长"
T4 = TEST + "test_用户可见串里不许出现工程侧文件名"
T5 = TEST + "test_后端的用户可见串里也不许出现工程代号"

#: 往**壳件**的字符串里塞的东西（每条对应一条判据）
SHELL_INJECT: tuple[tuple[str, str], ...] = (
    (T1, 'var _probe1 = "**x**";'),
    (T2, 'var _probe2 = "（R99）";'),
    (T3, 'var _probe3 = 0; title="' + "测" * 220 + '";'),
    (T4, 'var _probe4 = "见 ops/README.md";'),
)
#: 四样东西**一起塞进一条块注释**（四条都该绿）
SHELL_COMMENT = ("\n/* var _c1 = \"**x**\"; var _c2 = \"（R99）\"; "
                 + 'title="' + "测" * 220 + '"; var _c4 = "见 ops/README.md"; */\n')

#: 后端那条（`T5`）：**赋值**形态必须红
BACK_INJECT = '_probe5 = "（R99）"'
#: 后端那条的**反向**：注释（ast 看不见）＋**裸字符串语句**（口径上按"文档式"跳过）⇒ 都必须绿
BACK_SOFT = ('\n# _probe6 = "（R99）"   ← 注释：ast 根本看不见\n'
             '# 下面这句 = "拿字符串当注释"的老写法（口径上按"文档式"跳过 ⇒ 不是上屏文字）\n'
             '"（R99）"\n')

_ENV = {"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}


def _rc(test: str) -> int:
    run = [str(ROOT / "backend/.venv/Scripts/python.exe"), "-X", "utf8", "-m", "pytest", "-q", test,
           "-p", "no:cacheprovider", "--tb=no", "--no-header"]
    r = subprocess.run(run, cwd=ROOT / "backend", env={**os.environ, **_ENV},
                       capture_output=True, text=True, encoding="utf-8")
    return r.returncode


def main() -> int:
    files = (TARGET, BACK)
    orig = {p: p.read_bytes() for p in files}
    md5 = {p: hashlib.md5(orig[p]).hexdigest() for p in files}
    ok = False
    try:
        cases = [(p, f) for _, f in SHELL_INJECT for p in [TARGET]]
        alltests = [t for t, _ in SHELL_INJECT] + [T5]

        print("① 基线（未改动）—— 五条都必须绿")
        base = all(_rc(t) == 0 for t in alltests)
        print(f"   基线 ⇒ {'✅ 全绿' if base else '❌ 有红的'}")

        reds: list[bool] = []
        for i, (test, frag) in enumerate(SHELL_INJECT, 1):
            name = test.split("::")[-1][:28]
            TARGET.write_text(orig[TARGET].decode("utf-8") + f"\n{frag}\n", encoding="utf-8", newline="")
            rc = _rc(test)
            reds.append(rc != 0)
            print(f"   {i}) 壳件塞进【{frag[:24]}…】⇒ {name} rc={rc}（必须非 0）")
        TARGET.write_bytes(orig[TARGET])

        BACK.write_text(orig[BACK].decode("utf-8") + f"\n{BACK_INJECT}\n", encoding="utf-8", newline="")
        rc5 = _rc(T5)
        reds.append(rc5 != 0)
        print(f"   5) 后端件塞进【{BACK_INJECT}】⇒ 后端那条 rc={rc5}（必须非 0）")
        BACK.write_bytes(orig[BACK])

        TARGET.write_text(orig[TARGET].decode("utf-8") + SHELL_COMMENT, encoding="utf-8", newline="")
        greens = [(_rc(t) == 0) for t, _ in SHELL_INJECT]
        print(f"③ 四样一起塞进【壳件块注释】⇒ 四条 rc={'全 0 ✅' if all(greens) else '有非 0 ❌'}")
        TARGET.write_bytes(orig[TARGET])

        BACK.write_text(orig[BACK].decode("utf-8") + BACK_SOFT, encoding="utf-8", newline="")
        g5 = _rc(T5) == 0
        print(f"③′ 后端件塞进【注释 ＋ 裸字符串语句】⇒ 后端那条 rc={'0 ✅' if g5 else '非 0 ❌'}")
        BACK.write_bytes(orig[BACK])

        ok = base and all(reds) and all(greens) and g5
    finally:
        for p in files:
            p.write_bytes(orig[p])

    clean = all(hashlib.md5(p.read_bytes()).hexdigest() == md5[p] for p in files)
    print(f"④ 逐字节还原（{len(files)} 件）：{'✅ 全一致' if clean else '❌ 有不一致！'}")
    print("结论：" + ("✅ 五条判据都有区分力（写进去必红）＋ 不误伤注释 / 文档式串 ＋ 还原干净"
                     if ok and clean else "❌ 见上面"))
    return 0 if ok and clean else 1


if __name__ == "__main__":
    sys.exit(main())
