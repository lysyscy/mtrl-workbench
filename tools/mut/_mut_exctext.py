#!/usr/bin/env python
"""「**用户可见串里不许拼异常正文**」的反向灵敏度 —— 证明 `test_ux_text.py::test_用户可见串里不许拼异常正文` **真的有牙**。

守什么（`backend/tests/test_ux_text.py` · `TAIL-220` · 架构走查候选③）：
- ⭐ 2026-10-02 立：既有那条判据（`TAIL-212`）只挡 **`type(exc).__name__`（类名）**，
  而**正文**（`{exc}`）一路没人管 ⇒ 这一类**落在射程之外**。实测真该改 5 处（`readers.py` ×4 ＋
  `setl_export.py` 那处会跟着报错上屏的 `problems`），本批已改完。
- ⚠️ 所以本件**三个靶**：① 正打（外来异常的正文上屏 ⇒ 必红）＋ **②③ 两个反例**（我们自己的异常 / `error_message=`
  ⇒ **必须不红**）—— 没有反例的话，"把判据放宽成一律报红"也能骗过本件。

靶法：在 `backend/app/` 下**临时新建**一个 `.py`（判据是 `rglob("*.py")` 扫那一层）⇒ 写完必删（`finally`）。
⚠️ 这类"往仓里放临时件"的靶**必须**在 `finally` 清掉：本仓有"靶件留坏态污染基线"的亏（见 `_mut_t20.py` 文件头）。

用法（在本仓根跑）：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\mut\\_mut_exctext.py
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
R = pathlib.Path(r"D:\dev\mtrl-workbench")
PY = R / "backend" / ".venv" / "Scripts" / "python.exe"
PROBE = R / "backend" / "app" / "_mut_probe_tmp.py"          # ⭐ 临时靶件（必删）
TEST = "tests/test_ux_text.py::test_用户可见串里不许拼异常正文"

#: ① 正打：**外来**异常的正文拼进用户可见串（`raise RuntimeError(f"…{exc}")`）
CASE_BAD = '''\
def probe(x):
    try:
        int(x)
    except Exception as exc:
        raise RuntimeError(f"失败：{exc}")
'''
#: ② 反例：handler 是**我们自己的**异常（`MustReportError`）⇒ 正文是"我们写的人话"⇒ **不许红**
CASE_OURS = '''\
from app.core.errors import MustReportError


def probe(x):
    try:
        int(x)
    except MustReportError as exc:
        raise RuntimeError(f"失败：{exc}")
'''
#: ③ 反例：走**执行记录**（`error_message=`，排障面）⇒ **不许红**
CASE_LOGGED = '''\
def probe(x):
    try:
        int(x)
    except Exception as exc:
        rec = dict(error_message=f"{type(exc).__name__}: {exc}")
        return rec
'''


def run_test() -> tuple[int, str]:
    r = subprocess.run([str(PY), "-X", "utf8", "-m", "pytest", TEST, "-q", "-o", "addopts=",
                        "-p", "no:cacheprovider"],
                       cwd=R / "backend", capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    fail: list[str] = []
    rc0, out0 = run_test()
    print(f"基线：rc={rc0}")
    if rc0 != 0:
        print(out0[-800:])
        print("⛔ 基线不是绿的 ⇒ 先修绿（否则本件测不了东西）")
        return 1

    results: dict[str, int] = {}
    try:
        for tag, text, want_red in (("① 外来异常正文上屏", CASE_BAD, True),
                                    ("② 我们自己的异常（反例）", CASE_OURS, False),
                                    ("③ error_message=（反例）", CASE_LOGGED, False)):
            print(f"变异{tag}：{'必红' if want_red else '**不许红**'}…")
            PROBE.write_text(text, encoding="utf-8")
            rc, out = run_test()
            results[tag] = rc
            if want_red and (rc == 0 or "_mut_probe_tmp" not in out):
                fail.append(f"{tag} ⇒ 期望红、实得 rc={rc}（判据没牙）")
            if (not want_red) and rc != 0:
                fail.append(f"{tag} ⇒ 期望**不红**、实得 rc={rc}（判据过宽 ⇒ 假红）")
    finally:
        PROBE.unlink(missing_ok=True)                  # ⚠️ 必删（否则污染基线 / 进 git）
    if PROBE.exists():
        fail.append("临时靶件没清掉")

    rcN, outN = run_test()
    if rcN != 0:
        fail.append(f"清场后判据仍红（rc={rcN}）—— 留下了坏态")
        print(outN[-600:])

    if fail:
        print("❌ " + "；".join(fail))
        return 1
    print(f"✅ 有区分力：① 外来正文 ⇒ rc={results['① 外来异常正文上屏']} · "
          f"② 我们的异常 ⇒ rc={results['② 我们自己的异常（反例）']} · "
          f"③ error_message= ⇒ rc={results['③ error_message=（反例）']} · 清场后 rc={rcN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
