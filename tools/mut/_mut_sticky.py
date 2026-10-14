"""反向灵敏度（`sticky_probe` —— 合计行「视口吸附置底」）—— 证明新判据**真会红**。

⚠️ 本件为什么必需：2026-09-24 **之前**本探针 `main()` 末尾是 `os._exit(0)` ⇒ **不管实测结果如何
   `rc` 恒 0**，而它**每轮都在收工闸门的清单里跑** ⇒ 那一行**什么都没判**
   （**同族第五例**：`shell_verify` · `cover_gap` · `audit_drift` · `audit_meta`）。
   ⇒ 当天给它装了**窄判据**（只钉「我们在用的那条 `E` ＋ 两个备选 `D`/`C` 必须有效」，
   ⛔ 不断言 `A` 必须失败）—— 本件就是那条判据的自证：**把 sticky 抹掉 ⇒ 必须判红**。

⚠️ 靶是 `tools/audit/sticky_probe.py` **自己**（只改它自建复现页里那两段 CSS，改完**立刻按 bytes 复原**）——
   ⛔ 与壳 / 原型无关：那个文件只是"复现页"，**不读工程代码**。
⚠️ 替换**按 CSS 选择器整段锚定**（⛔ 别全局替 `position:sticky` —— 页里四段对照都有它，一替就全坏，
   那样"变红"证明不了判据分得清是**哪一条**失效）。

用法：python tools/mut/_mut_sticky.py   （⚠️ 需 `PLAYWRIGHT_BROWSERS_PATH`，否则浏览器起不来）
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
RULER = ROOT / "tools" / "audit" / "sticky_probe.py"
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"

#: `(对照字母, 期望在输出里同现的两个串)` —— 靶 = 该对照那段 CSS 里的 `position:sticky`
CASES: list[tuple[str, tuple[str, str]]] = [
    ("E", ("判据未过", "`E`")),      # 本工程采用
    ("D", ("判据未过", "`D`")),      # 备选 tfoot
]
#: 各对照的 CSS 选择器（`E` 是末行 `tr` 自身 / `D` 是 `tfoot` 整块）
SELECTOR = {"E": "tbody tr.sumrow", "D": "tfoot"}


def run_probe() -> tuple[int, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
           "PLAYWRIGHT_BROWSERS_PATH": os.environ.get("PLAYWRIGHT_BROWSERS_PATH",
                                                      r"C:\ProgramData\ms-playwright")}
    r = subprocess.run([str(PY), str(RULER)], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    src = RULER.read_bytes()
    md5_before = hashlib.md5(src).hexdigest()
    text = src.decode("utf-8")

    rc0, out0 = run_probe()
    print(f"基线（未改坏）sticky_probe rc={rc0}（应为 0）· 输出 {len(out0)} 字符")
    for _k, needle in CASES:
        if any(all(x in ln for x in needle) for ln in out0.splitlines()):
            print(f"  ⛔ 基线的输出里**已经**有「{needle}」⇒ 先查基线")
            return 1
    if rc0 != 0:
        print("  ⛔ 基线就红 ⇒ 先确认是不是浏览器行为变了（那是**真信息**，"
              "见 `docs/reference/sticky-total-row.md`）")
        return 1

    hit = 0
    for key, needle in CASES:
        rule = re.search(rf"\.case{key} {re.escape(SELECTOR[key])}\{{([^}}]*)\}}", text)
        if rule is None or "position:sticky" not in rule.group(1):
            print(f"  ⛔ `{key}` —— 取不到那段 CSS（探针改写法了）⇒ **未验证**")
            continue
        broken = rule.group(0).replace("position:sticky", "position:static", 1)   # 只坏这一条
        try:
            RULER.write_text(text.replace(rule.group(0), broken, 1), encoding="utf-8", newline="")
            rc, out = run_probe()
        finally:
            RULER.write_bytes(src)                         # ⭐ 立刻按原 bytes 复原
        ok = rc != 0 and any(all(x in ln for x in needle) for ln in out.splitlines())
        print(("  ✅ " if ok else "  ⛔ 未命中 ") + f"M{'1' if key == 'E' else '2'} 抹掉 `{key}` "
              + f"（{'本工程采用' if key == 'E' else '备选'}）的 `position:sticky`  ⇒ rc={rc}"
              + ("" if ok else f"（判据 {needle} 未同现在一行）"))
        hit += ok

    ok_md5 = hashlib.md5(RULER.read_bytes()).hexdigest() == md5_before
    print()
    print(f"  命中 {hit}/{len(CASES)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 复原' if ok_md5 else '❌ 未复原'}")
    return 0 if (hit == len(CASES) and ok_md5) else 1


if __name__ == "__main__":
    sys.exit(main())
