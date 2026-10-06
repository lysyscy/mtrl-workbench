"""**反向灵敏度**：证明 `T3`（幽灵路径）在 `TAIL-238` 收窄之后**既没变瞎、也没被放水**。

背景（为什么非做不可）：`TAIL-238` 把 `T3` 的叙述豁免词表（`audit_common.T3_OLD_PATH_HINTS`）
从「那个地址**已作数**」扩到「那个地址**本来就不成立 / 是我写错的**」⇒ 六天内 ≥10 次**误伤**该收，
但这是**形态判据**（可被绕过）⇒ ⛔ 必须同批钉住两个方向，否则就是"为了让闸门变绿而放宽判据"。

四条各钉一个方向（⚠️ 靶与判据成对，同本仓老话）：
- `N1` **真幽灵仍红**：活文档里一个**没有任何叙述词**的裸引用 ⇒ 必须报红
  ⇒ 钉「收窄没有把 `T3` 关掉」；
- `N2` **叙述句被豁免**：同一份活文档里写一句「那天我**误写**了那个路径」⇒ **必须不再报**
  ⇒ 钉「收窄真的生效」（否则误伤一点没少，本票等于没做）；
- `N3` ⭐ **票仓里不带叙述词的同类句仍红** ⇒ 钉死本票铁律「⛔ 不许只放宽一半」
  （靶＝**票面**；这一条同时证伪 (C) 方案「整层放行票仓」—— 那一层正是真幽灵的出没地）；
- `N4` ⭐ **距离闸仍承重**：叙述词挪到**离路径 >16 字**的远处 ⇒ 仍必须报红
  ⇒ 钉「没有退化成整行命中」（词表一扩，泛词更容易巧合命中）。

做法与骨架照 `tools/mut/_mut_docaudit.py`：**改坏 → 跑 `doc_audit` → 立刻按原 bytes 复原 → MD5 逐字节校验**。
⚠️ 一律走 bytes ＋ 按目标文件行尾归一（`.md` 可能是 CRLF，`write_text` 会静默换行尾 ⇒ MD5 假 BAD）。
⚠️ 追加块**前后各留 3 空行**：`_hit` 的豁免窗口 = 命中行 **±2 行** ⇒ 贴着正文追加可能被邻行的
   「已删 / 改为 / 原」之类词**降档**（那就成了"变异没命中"，看着跟"检查瞎了"**一模一样**）。
⚠️ 判据串要**够窄**：`T3` 的报法是「黄/红 <路径> <路径名>」⇒ 一律用**元组**（同一行同时出现），
   且路径名**每条各不相同**（`nope_ghost238a/b/c/d`）⇒ 不会在基线里就命中（基线含判据 ⇒ 本件当场拒跑整支）。
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
#: 活文档靶（`ops/*.md` ∈ `SCAN_GLOBS`，且**不在** `LENIENT_GLOBS` ⇒ `T3` 命中即红）。
#: 照 `M6`/`M30` 同款选它：本仓最常见的"引用一个不存在的仓内相对路径"。
THRESHOLD = ROOT / "ops" / "阈值表.md"
#: ⭐ `N3` 的靶：**票面**（`.codebuddy/work/50-tickets/*.md`，同样严判 ⇒ 命中即红）。
#: ⚠️ 为什么不用「临时造一张票」：`T6` 会先报「幽灵票文件」⇒ 报的就不是 `T3` 了（同 `M20` 的坑）。
TICKET = ROOT / ".codebuddy" / "work" / "50-tickets" / "TAIL-238-T3幽灵路径收窄只对真在指路的句.md"
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"


def _b(s: str) -> bytes:
    return s.replace("\r\n", "\n").encode("utf-8")


def _fit(frag: bytes, sample: bytes) -> bytes:
    """按**靶件自己的行尾**归一（`.md` 可能是 CRLF）。"""
    if b"\r\n" in sample:
        return frag.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return frag.replace(b"\r\n", b"\n")


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_doc_audit() -> tuple[int, str]:
    """→ (`必须修 N`, 全量输出)。⚠️ **不看退出码** —— rc 还含黄档与其它档，两回事。
    ⚠️ **必须带 `-v`**：默认只把黄档按件聚合 ⇒ 判据串在输出里根本看不见（假绿）。
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([str(PY), str(ROOT / "tools" / "audit" / "doc_audit.py"), "-v"],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"必须修 (\d+)", out)
    return (int(m.group(1) if m else -1), out)


def _needle_hit(needle: tuple[str, ...], out: str) -> bool:
    return any(all(x in ln for x in needle) for ln in out.splitlines())


#: ⚠️ `N3` 的追加行**刻意不含任何叙述词**（不得出现「没建 / 未建 / 没创建 / 误写 / 写错 /
#: 裸路径 / 裸写法」，也不得出现老词「旧路径 / 已不存在 / 已退场 / 已搬走 / 已移出 / 不在仓内」）
#:    ⇒ 它就是"**真在指路**"的形状 ⇒ 必须报红。
#: ⚠️⚠️ `frag` 必须**追加**（`src + 片段`）—— `tools/mut/_mut_docaudit.py` 的 `frag` 是
#:    「**整件替换成那个片段**」（它只看注入串出不出得来，故而省事）。
#:    ⛔ 照抄那一半的后果**当场量到**：票面被换成 5 行 ⇒ `T6` 顺手报 3 条（"票里缺栏 / 没有复选框
#:    / 找不到 Status"）＋ `T3` 报的行号是 **4**（追加本该 100+）⇒ 那三条红与本票无关，
#:    真正的判据被**淹在噪音里**（"报的不是这条"和"没变红"长得一模一样）。
CASES: list[dict] = [
    {"desc": "N1 `T3` 真幽灵仍红（活文档里一个没有任何叙述词的裸引用）", "mode": "red",
     "also": ("[T3]", "nope_ghost238a"), "path": THRESHOLD,
     "frag": lambda src: src + _fit(_b(
         "\n\n\n另见 `backend/app/core/nope_ghost238a.py` 这一段的说明。\n\n\n"), src)},
    {"desc": "N2 叙述句**被豁免**（同一句里明说「误写了那个路径」⇒ 必须不再报）", "mode": "silent",
     "silent": ("[T3]", "nope_ghost238b"), "path": THRESHOLD,
     "frag": lambda src: src + _fit(_b(
         "\n\n\n⚠️ 那天我误写了 `backend/app/core/nope_ghost238b.py`，"
         "尺子当场报红，留一句记着。\n\n\n"), src)},
    {"desc": "N3 ⭐ 票面里**不带叙述词**的同类句**仍必须报红**（钉「不许只放宽一半」）", "mode": "red",
     "also": ("[T3]", "nope_ghost238c"), "path": TICKET,
     "frag": lambda src: src + _fit(_b(
         "\n\n\n落点见 `backend/app/core/nope_ghost238c.py`（变异注入 · 用完即复原）。\n\n\n"), src)},
    {"desc": "N4 ⭐ 距离闸仍承重（叙述词挪到离路径 >16 字远处 ⇒ 仍必须报红）", "mode": "red",
     "also": ("[T3]", "nope_ghost238d"), "path": THRESHOLD,
     "frag": lambda src: src + _fit(_b(
         "\n\n\n⚠️ 那天我误写了一个文件名，这里只留个提醒（判据自己会报），"
         "下一句才是真的引用 —— 见 `backend/app/core/nope_ghost238d.py`。\n\n\n"), src)},
]


def main() -> int:
    for c in CASES:
        assert c["path"].exists(), f"靶件不在位：{c['path']}"
    before = {c["path"]: c["path"].read_bytes() for c in CASES}

    base_red, base_out = run_doc_audit()
    print(f"基线（未改坏）doc_audit 必须修 {base_red}（应为 0）· 输出 {len(base_out)} 字符")
    for c in CASES:
        n = c.get("also") or c["silent"]
        if _needle_hit(n, base_out):
            print(f"  ⛔ 基线的输出里**已经**有「{n}」⇒ 本件这条判据无效，先重定靶")
            return 1
    if base_red != 0:
        print("  ⛔ 基线就有「必须修」⇒ 先把红清了再来跑本件")
        return 1

    hit = 0
    for c in CASES:
        src = c["path"].read_bytes()
        c["path"].write_bytes(c["frag"](src))               # `frag` 自己已按行尾 `_fit` 过
        try:
            red, out = run_doc_audit()
        finally:
            c["path"].write_bytes(src)                      # ⭐ 逐条立刻按原 bytes 还原
        if c["mode"] == "red":
            ok = red > 0 and _needle_hit(c["also"], out)
            tail = f"必须修 {red}（变红）" if red > 0 else f"必须修 {red}（没变红）"
            if red > 0 and not _needle_hit(c["also"], out):
                tail += " ⚠️ **但报的不是这条**"
        else:
            ok = not _needle_hit(c["silent"], out)
            tail = "输出里**没有**它（豁免生效）" if ok else "⚠️ 仍然报了（豁免没生效）"
        print(("  ✅ " if ok else "  ⛔ 未命中 ") + c["desc"] + "  → " + tail)
        hit += bool(ok)

    print()
    dirty = [p for p, b in before.items() if md5(p) != hashlib.md5(b).hexdigest()]
    ok = not dirty
    print(f"  命中 {hit}/{len(CASES)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 全部复原' if not dirty else '❌ 未复原：' + '、'.join(map(str, dirty))}")
    return 0 if (hit == len(CASES) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())