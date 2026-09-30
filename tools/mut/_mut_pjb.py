"""反向灵敏度（`PJB` 项目选择按钮件 —— `TAIL-64` **P4-d** 的**统一按钮出口**）——
证明「项目选择按钮走一个出口」那条判据**真有区分力**。

⚠️ 本件为什么必需：把 `pjwrap` 里那枚 ▾ 按钮（连同它那串 `min-width` / `inline-flex` / `gap` 样板）
抽进 `PJB` 之后，**渲染字节一字不变** ⇒ 页面、`U1`（原型那侧还是旧形态、无从对位）、真机
**都看不出**某一处换没换 ⇒ 只有"改坏了必须红"能证明它。

两靶（改完**立刻按 bytes 复原** ＋ MD5 校验）：
- `M1` **去掉委托**：把 `V.m03` 那处的 `PJB({act:'pjToggle'` 改成 `PJBBROKEN({act:'pjToggle'`
  （合法标识符 ⇒ **不触发**语法错，只会让"项目按钮没走统一出口"那一条红）。
- `M2` **掏空内核**：把 `PJB` 体内的 `'<span>'+label+'</span>'` 改成 `'<span>'+''+'</span>'`
  ⇒ "内核没把标签拼进按钮里"必须红（⚠️ 靶在 `shell/proj.js` —— `PJB` 住在那儿，⛔ 别假设在 `index.html`）。

⚠️ 判据 = **目标测试件 rc≠0** ＋ **那条断言的原话出现在输出里**（⛔ 别只看 rc）。
⚠️ 子集 pytest 用 `ACC_RESULTS_PATH` 指到 `artifacts/_mut_acc_results.json`（⭐ 别把权威四态冲成残档）。

用法：python tools/mut/_mut_pjb.py
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHELL = ROOT / "backend" / "app" / "web" / "index.html"
#: ⭐ `PJB` 的口径件住在 `shell/proj.js`（同 `TBL`/`FBAR`）—— ⛔ 别假设源码在 `index.html`（哑靶的教训）。
PROJ = ROOT / "backend" / "app" / "web" / "shell" / "proj.js"
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
TARGETS: tuple[str, ...] = ("tests/test_ux_pages.py",)   #: ⭐ P4-d 那条判据所在件
PARTIAL_ACC = ROOT / "artifacts" / "_mut_acc_results.json"


def _b(s: str) -> bytes:
    """⚠️ `bytes` 字面量**只能放 ASCII** ⇒ 含中文的靶串必须这样编（踩过：`SyntaxError`）。"""
    return s.encode("utf-8")


CASES: list[tuple[pathlib.Path, str, bytes, bytes, str]] = [
    (SHELL, "M1 去掉委托（`m03` 的项目按钮不再走 `PJB`）", _b("PJB({act:'pjToggle'"),
     _b("PJBBROKEN({act:'pjToggle'"), "按钮没走统一出口"),
    # ⚠️ 靶串取自内核的那一段：`…'><span>'+label+'</span><span class="mut"…'` ⇒ 收尾那个引号在
    #    `</span>` **之后**（不在它紧邻处）—— 第一版写成 `'</span>'` 就**命中不到**（哑靶）。
    (PROJ, "M2 掏空内核（`PJB` 不再把标签拼进按钮里）", _b("span>'+label+'</span>"),
     _b("span>'+''+'</span>"), "没有把标签拼进按钮里"),
]


def run_target() -> tuple[int, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
           "ACC_RESULTS_PATH": str(PARTIAL_ACC)}
    r = subprocess.run([str(PY), "-m", "pytest", "-q", *TARGETS, "-p", "no:cacheprovider",
                        "--tb=line"], cwd=str(ROOT / "backend"), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    files = sorted({c[0] for c in CASES})
    orig = {p: p.read_bytes() for p in files}
    md5_before = {p: hashlib.md5(b).hexdigest() for p, b in orig.items()}

    rc0, out0 = run_target()
    print(f"基线（未改坏）{' + '.join(TARGETS)} rc={rc0}（应为 0）")
    if rc0 != 0:
        print("  ⛔ 基线就红 ⇒ 先清红再来跑本件")
        return 1

    hit = 0
    for path, desc, old, new, needle in CASES:
        src = orig[path]
        if src.count(old) != 1:
            print(f"  ⛔ {desc} —— 靶串在 `{path.name}` 里命中 {src.count(old)} 次（期望 1）⇒ **未验证**")
            continue
        try:
            path.write_bytes(src.replace(old, new, 1))
            rc, out = run_target()
        finally:
            path.write_bytes(src)                     # ⭐ 立刻按原 bytes 复原
        ok = rc != 0 and needle in out
        print(("  ✅ " if ok else "  ⛔ 未命中 ") + desc + f"  → rc={rc}"
              + ("" if ok else f"（判据「{needle}」没出现在输出里）"))
        hit += ok

    bad = [p.name for p in files
           if hashlib.md5(p.read_bytes()).hexdigest() != md5_before[p]]
    print()
    print(f"  命中 {hit}/{len(CASES)}")
    print(f"  复原校验（MD5 逐字节 · {len(files)} 件）："
          + ("✅ 复原" if not bad else "❌ 未复原 " + ", ".join(bad)))
    print("⚠️ 本件只跑了目标件 ⇒ **接着必须重跑全套 pytest 写回权威四态**（否则报表掉绿）。")
    return 0 if (hit == len(CASES) and not bad) else 1


if __name__ == "__main__":
    raise SystemExit(main())
