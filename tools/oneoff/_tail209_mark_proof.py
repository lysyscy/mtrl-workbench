"""壳源码扫查类判据的自证（`TAIL-209` ＋ 第二轮）：**每条都要"写进去必红 ＋ 注释里不算"**。

被证的四条（都在 `backend/tests/test_ux_text.py`）：
  `T1` = `test_壳源码里不许有双层星号_加粗标记`（`**` 不许原样上屏）
  `T2` = `test_用户可见串里不许出现工程代号`（`（R8）` / `DEV-J-01` / `链路 A` …）
  `T3` = `test_悬停文案也不超长`（`title="…"` > 200 字）
  `T4` = `test_用户可见串里不许出现工程侧文件名`（`ops/…` / `.codebuddy` / `.md` …）

怎么证（每个 case 都注入到**同一个壳件**、跑完**逐字节还原**）：
  ① 基线：四条都绿；
  ② 逐条往**字符串**里塞该条要拦的东西 ⇒ 那条**必须红**；
  ③ 把四样东西一起塞进**一条块注释** ⇒ 四条**必须仍绿**（注释不是上屏文字 ——
     壳里 `DEV-*` / `链路 X` / `ops/…` / 大量 `**` **绝大多数只活在注释里**，这是"不误伤"的关键一条）；
  ④ 逐字节还原（MD5 比对）。
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
TARGET = W / "shell" / "legacy.js"
TEST = "tests/test_ux_text.py::"

T1 = TEST + "test_壳源码里不许有双层星号_加粗标记"
T2 = TEST + "test_用户可见串里不许出现工程代号"
T3 = TEST + "test_悬停文案也不超长"
T4 = TEST + "test_用户可见串里不许出现工程侧文件名"

#: 往**字符串**里塞的东西（每条对应一条判据）
INJECT: tuple[tuple[str, str], ...] = (
    (T1, 'var _probe1 = "**x**";'),
    (T2, 'var _probe2 = "（R99）";'),
    (T3, 'var _probe3 = 0; title="' + "测" * 220 + '";'),
    (T4, 'var _probe4 = "见 ops/README.md";'),
)
#: 四样东西**一起塞进一条块注释**（四条都该绿）
IN_COMMENT = ("\n/* var _c1 = \"**x**\"; var _c2 = \"（R99）\"; "
              + 'title="' + "测" * 220 + '"; var _c4 = "见 ops/README.md"; */\n')

_ENV = {"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}


def _rc(test: str) -> int:
    run = [str(ROOT / "backend/.venv/Scripts/python.exe"), "-X", "utf8", "-m", "pytest", "-q", test,
           "-p", "no:cacheprovider", "--tb=no", "--no-header"]
    r = subprocess.run(run, cwd=ROOT / "backend", env={**os.environ, **_ENV},
                       capture_output=True, text=True, encoding="utf-8")
    return r.returncode


def main() -> int:
    orig = TARGET.read_bytes()
    h0 = hashlib.md5(orig).hexdigest()
    text = orig.decode("utf-8")
    ok = False
    try:
        print("① 基线（未改动）—— 四条都必须绿")
        base = all(_rc(t) == 0 for t, _ in INJECT)
        print(f"   基线 ⇒ {'✅ 全绿' if base else '❌ 有红的'}")

        reds: list[bool] = []
        for i, (test, frag) in enumerate(INJECT, 1):
            name = test.split("::")[-1][:30]
            TARGET.write_text(text + f"\n{frag}\n", encoding="utf-8", newline="")
            rc = _rc(test)
            reds.append(rc != 0)
            print(f"   {i}) 塞进【{frag[:26]}…】⇒ {name} rc={rc}（必须非 0）")
        TARGET.write_bytes(orig)

        TARGET.write_text(text + IN_COMMENT, encoding="utf-8", newline="")
        greens = [(_rc(t) == 0) for t, _ in INJECT]
        print(f"③ 四样一起塞进【块注释】⇒ 四条 rc={'全 0 ✅' if all(greens) else '有非 0 ❌'}")
        ok = base and all(reds) and all(greens)
    finally:
        TARGET.write_bytes(orig)

    clean = hashlib.md5(TARGET.read_bytes()).hexdigest() == h0
    print(f"④ 逐字节还原：{'✅ 一致' if clean else '❌ 不一致！'}")
    print("结论：" + ("✅ 四条判据都有区分力（写进去必红）＋ 不误伤注释 ＋ 还原干净"
                     if ok and clean else "❌ 见上面"))
    return 0 if ok and clean else 1


if __name__ == "__main__":
    sys.exit(main())
