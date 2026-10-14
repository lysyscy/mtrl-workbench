# -*- coding: utf-8 -*-
"""反向灵敏度（一次性）：证明 `test_wired_boot.py::test_跨页写动作后全标脏` 有区分力 —— 改坏 ⇒ 必须变红。
跑完逐字节复原（MD5 校验）。用完即删。

⭐⭐ **2026-09-24 修过一次（这次教训本身比本件重要）**：本件原来**只锚 `shell/core.js` 一个文件**；
当天把 `API` 块拆成 `shell/api.js` 之后，两处 `markCrossPageStale()` 跟着搬走
⇒ **M1 / M3 锚点命中 0 次 ⇒ 命中数从 3/3 静默退化成 1/3**
（⛔ **红没亮，不是判据好，是尺子瞎了** —— 与同日 `shell_verify` 基线那次**同一类**：拆件打瞎尺子）。

⇒ 修法两条（缺一不可）：
　① **全壳搜索**：锚点在 `index.html` ＋ `shell/*.js` 里**全局唯一**即可，**落在哪个件就改哪个件**
　　⇒ 以后再拆/再合件，都不会让它静默失效；
　② ⭐ **锚点不带行尾**（本仓 `index.html` / 新拆出的 `api.js` 是 **CRLF**，而 `.py` 与部分 `.js` 是 **LF**）
　　⇒ 锚点若以 `\\n` 结尾，在 CRLF 件里**永远命中 0 次**（第一次修完仍是 1/3，就是栽在这）
　　⇒ 一律用**文本子串匹配**（不含行尾），复原仍用**那一件的原字节**。

⚠️ `TAIL-48` 余项 `P3`②（2026-09-24）：证据 = `docs/architecture/write-refresh.md`。
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web"
PARTS = [WEB / "index.html"] + sorted((WEB / "shell").glob("*.js"))
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
TEST = "tests/test_wired_boot.py"

#: (说明, 原文, 改坏成) —— 6 处调用**行尾注释各不相同**，正好用来认人。
#: ⛔ **原文一律不含行尾**（理由见文件头 ②）。
MUTS = [
    ("M1 抽掉 `API.post` 的标脏（JSON 写之后别的页留旧数）",
     "    markCrossPageStale();         /* ⭐ `TAIL-48` `P3`②：JSON 写出口（见 `markCrossPageStale`） */",
     ""),
    ("M2 唯一出口改成空函数（标脏整体失效）",
     "function markCrossPageStale() { LOADED.clear(); }",
     "function markCrossPageStale() { }"),
    ("M3 `m07` 抓取不再标脏（落 `setl_detail` ⇒ m06/m07 都读它）",
     "    markCrossPageStale();         /* ⭐ `TAIL-48` `P3`②：抓取落 `setl_detail` ⇒ m06/m07 都读它 */",
     ""),
]


def red() -> int:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
           "PLAYWRIGHT_BROWSERS_PATH": r"C:\ProgramData\ms-playwright",
           "ACC_RESULTS_PATH": "../artifacts/acc_results.json"}
    r = subprocess.run([PY, "-m", "pytest", "-q", TEST, "-p", "no:cacheprovider", "--tb=line"],
                       cwd=str(ROOT / "backend"), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    return r.returncode


def locate(old_s: str) -> tuple[pathlib.Path | None, int]:
    """锚点必须在**整个壳**（`index.html` ＋ `shell/*.js`）里**唯一** ⇒ 返回它落在哪个件。

    ⛔ 走**文本子串**（不是 bytes）⇒ 绕开 CRLF/LF 差异。
    """
    hits = [(p, p.read_text(encoding="utf-8").count(old_s)) for p in PARTS]
    hits = [(p, n) for p, n in hits if n]
    return (hits[0][0] if len(hits) == 1 and hits[0][1] == 1 else None), sum(n for _, n in hits)


def main() -> int:
    snap = {p: p.read_bytes() for p in PARTS}          # ⛔ 复原一律用**那一件的原字节**
    md5 = {p: hashlib.md5(b).hexdigest() for p, b in snap.items()}
    print("壳件 %d 个：%s" % (len(PARTS), " · ".join(p.name for p in PARTS)))
    print("基线（未改坏）pytest 期望 rc=0 ⇒ 实测 rc=%d" % red())
    hit = 0
    try:
        for name, old_s, new_s in MUTS:
            tgt, total = locate(old_s)
            if tgt is None:
                print("❌ %s：锚点在整个壳里命中 %d 次（必须唯一）" % (name, total))
                continue
            tgt.write_bytes(tgt.read_text(encoding="utf-8").replace(old_s, new_s).encode("utf-8"))
            rc = red()
            tgt.write_bytes(snap[tgt])
            ok = rc != 0
            hit += ok
            print("%s %s（落在 `%s`）→ pytest rc=%d"
                  % ("✅" if ok else "❌ 假绿", name, tgt.name, rc))
    finally:
        for p, b in snap.items():
            if p.read_bytes() != b:
                p.write_bytes(b)
                print("  ↩︎ 兜底复原 %s" % p.name)
    after = {p: hashlib.md5(p.read_bytes()).hexdigest() for p in PARTS}
    print("\n命中 %d/%d" % (hit, len(MUTS)))
    print("复原校验（MD5 逐字节）：%s"
          % ("✅ 已复原" if all(after[p] == md5[p] for p in PARTS) else "❌ 未复原"))
    return 0 if (hit == len(MUTS) and all(after[p] == md5[p] for p in PARTS)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
