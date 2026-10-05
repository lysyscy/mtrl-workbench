#!/usr/bin/env python
"""**文档追加器** —— 往活文档追加一段，且**接上去这一步不出错**（2026-10-05 立，`/retro` 候选 5）。

⭐ 它收掉当天栽过的三个坑：
  1. **幂等守卫写歪** ⇒ 守卫永不触发，只剩 `assert` 意外挡住 ⇒ **那不叫幂等，叫运气**
     （本仓同族已犯两次）⇒ 本件用**片段自己的第一行**当守卫（逐字可搜 ⇒ 必然一致）。
  2. **行尾混着写** ⇒ 编辑工具插入的新行带裸 LF ⇒ 目标变成混合行尾
     （当天实测 `audit_meta.py` 6 处 · 阈值表 2 处）⇒ 本件按**目标自己的**行尾归一。
  3. **锚点末尾多写一个换行** ⇒ 下一行的行首被吞，工具只报「N lines removed」、闸门照不到
     ⇒ 本件收尾断言「锚点后第一行 == 片段第一行」。

⚠️ **它治不了「内容太长写不进去」** —— 编辑工具在长 markdown 上不稳定（实测同一段内容
连续两次、一次成一次败）⇒ **片段文件本身仍要分段写**。本件只保证「接上去」这一步不出错。
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
def _nl_of(raw: bytes) -> str:
    """目标文件自己的行尾（⛔ 混着写就是当天栽过的那个坑）。"""
    return "\r\n" if b"\r\n" in raw else "\n"


def _norm(text: str, nl: str) -> str:
    return text.replace("\r\n", "\n").replace("\n", nl)


GUARD_MIN = 12          # + 守卫串的最短长度（短行不具辨识度）


def _guard(fragment: str) -> str:
    """守卫串 = 片段**第一行非空行**。

    ⭐ 为什么用它：守卫必须与**真正被插入的文本**逐字一致 —— 写成「决定件 = D30」这种
    概括式，指针一动就永远不触发（当天栽过）⇒ 取片段自己的一行，不可能不一致。
    """
    for ln in fragment.splitlines():
        s = ln.strip()
        if len(s) >= GUARD_MIN:
            return s
    raise SystemExit("⛔ 片段是空的 ⇒ 没有守卫串可用来判幂等")
def main() -> int:
    ap = argparse.ArgumentParser(description="文档追加器（幂等 ＋ 行尾归一 ＋ 收尾断言）")
    ap.add_argument("target", help="目标活文档（仓内相对路径）")
    ap.add_argument("anchor", nargs="?", default=None, help="锚点：目标里逐字存在的一小段（不超一行）")
    ap.add_argument("fragment", help="片段文件（要追加的正文）")
    ap.add_argument("--at-end", action="store_true", help="追加到文件末尾（不找锚点）")
    ap.add_argument("--anchor-file", default=None, help="锚点从文件第一行读（**锚点含直引号时必须用这个**）")
    ap.add_argument("--dry", action="store_true", help="只报会做什么，不写")
    a = ap.parse_args()

    tgt = ROOT / a.target
    frag_p = ROOT / a.fragment if (ROOT / a.fragment).exists() else pathlib.Path(a.fragment)
    if not tgt.exists():
        print("⛔ 目标不存在：%s" % a.target)
        return 1
    if not frag_p.exists():
        print("⛔ 片段文件不存在：%s" % a.fragment)
        return 1

    if a.anchor_file:                      # ⭐ 当天实测：含直引号的锚点走 argv 会被拆坏
        a.anchor = pathlib.Path(a.anchor_file).read_text(encoding="utf-8").splitlines()[0].strip()
    raw = tgt.read_bytes()
    nl = _nl_of(raw)
    text = raw.decode("utf-8")
    frag = _norm(frag_p.read_text(encoding="utf-8"), nl)
    g = _guard(frag)

    if g in text:
        print("✅ 守卫命中（片段已在文件里）⇒ 不动文件 · 幂等成立")
        return 0
    if a.at_end:
        new = text.rstrip("\r\n") + nl + nl + frag.strip("\n") + nl
        where = "文件末尾"
    else:
        if not a.anchor:
            print("⛔ 要插入到锚点之后 ⇒ 给出锚点，或用 --at-end")
            return 2
        if text.count(a.anchor) != 1:
            print("⛔ 锚点命中 %d 次（要求恰好 1 次）⇒ 先核锚点" % text.count(a.anchor))
            return 1
        new = text.replace(a.anchor, a.anchor + nl + nl + frag.strip("\n"), 1)
        where = "锚点之后"
    if a.dry:
        print("[dry] 会在%s插入 %d 行（守卫：%s）" % (where, frag.count(nl), g[:40]))
        return 0
    tgt.write_bytes(new.encode("utf-8"))
    back = tgt.read_bytes().decode("utf-8")
    assert back.count(g) == 1, "守卫串出现次数不对 ⇒ 写坏了"
    assert ("\r\n" in back) == (nl == "\r\n"), "行尾被改乱 ⇒ 写坏了"
    if not a.at_end:
        after = back.split(a.anchor, 1)[1].strip().splitlines()
        assert after and after[0].strip() == g, "锚点后第一行不是片段首行 ⇒ 行首被吞了"
    print("✅ 已在%s插入 %d 行 · 守卫 1 次 · 行尾 %s · 现在共 %d 行"
          % (where, frag.count(nl), "CRLF" if nl == "\r\n" else "LF", len(back.splitlines())))
    return 0


if __name__ == "__main__":
    sys.exit(main())