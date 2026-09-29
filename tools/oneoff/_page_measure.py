"""一次性 · 逐页量测（`TAIL-117` 逐页推进计划的**第 1 步：量测先行**）

**为什么需要它**：本会话实测过 —— 审计件给的底数被**推翻 4 次**（"21 处展开区"实为 12 常驻 ＋ 9 真展开区 ·
"内联 `--fscale` 173 处"实为 3 处 · "全站下拉只许 3 处"是误读 · "死代码 47 条"里 10 条是尺子假阳性）。
⇒ 规矩：**先量再说**（计划件 `work/10-designs/设计-前端逐页推进计划-20260929.md` §二 第 1 步）。

量什么（每页固定这几项，便于跨页对比）：切片行数 / 动作数 / 浮层与提示出口 / 状态件 / 内联样式 /
原生下拉 / 表格 / 可见长文案（>40 字）/ 该页在接线层（`shell/*.js`）的落点分布。

用法：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_page_measure.py m05
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_page_measure.py m05 m03 --all
⛔ **只读**（不写任何文件）；⛔ 输出**别抄进文档**（会变）。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web"
INDEX = WEB / "index.html"

SLICE_RE = re.compile(r"^V\.([A-Za-z0-9_]+)\s*=")
TAG_RE = re.compile(r"<[^>]+>")
#: 可见文案：`>` 与 `<` 之间 ≥40 字、且不是纯代码/模板表达式
TXT_RE = re.compile(r">([^<>{}]{40,}?)<")


def slices(lines: list[str]) -> dict[str, tuple[int, int]]:
    """`V.<名>=` 顶层声明切出的切片表（与 `ui_parity` 认 `^V\\.` 同一口径）。"""
    out: dict[str, tuple[int, int]] = {}
    hits = [(i, SLICE_RE.match(l).group(1)) for i, l in enumerate(lines) if SLICE_RE.match(l)]
    for k, (i, name) in enumerate(hits):
        end = hits[k + 1][0] if k + 1 < len(hits) else len(lines)
        out.setdefault(name, (i, end))
    return out


def measure(page: str, lines: list[str], span: tuple[int, int]) -> None:
    a, b = span
    body = lines[a:b]
    txt = "\n".join(body)
    acts = sorted(set(re.findall(r'data-act="([^"]+)"', txt)))
    longs = sorted((len(x.strip()) for x in TXT_RE.findall(txt)), reverse=True)[:3]
    comments = sum(1 for l in body if l.strip().startswith(("//", "/*", "*")))
    blanks = sum(1 for l in body if not l.strip())

    print(f"── `V.{page}` 切片：L{a + 1}–{b}（{len(body)} 行 · 非空 {len(body) - blanks} · 注释 {comments}）──")
    print(f"  动作 `data-act`      {len(acts)} 个：{' '.join(acts) if acts else '（无）'}")
    print(f"  浮层/提示出口        modal( {txt.count('modal(')} · toast( {txt.count('toast(')} · "
          f"class=\"tip {txt.count('class=\"tip')} · EMPTYROW( {txt.count('EMPTYROW(')}")
    print(f"  状态件               pageState( {txt.count('pageState(')} · pageGate( {txt.count('pageGate(')} · "
          f"rawFetch( {txt.count('rawFetch(')} · errHuman( {txt.count('errHuman(')}")
    print(f"  内联样式与下拉        style=\" {txt.count('style=\"')} · <select {txt.count('<select')} · "
          f"projPanel( {txt.count('projPanel(')} · <table {txt.count('<table')}")
    print(f"  金额/数字出口        MONEY( {txt.count('MONEY(')} · N2( {txt.count('N2(')}")
    print(f"  最长可见文案         {' / '.join(str(n) + ' 字' for n in longs) if longs else '（无 ≥40 字）'}")
    if longs:
        for x in TXT_RE.findall(txt):
            if len(x.strip()) == longs[0]:
                print(f"    ⤷ 最长那句：{x.strip()[:150]}")
                break
    print()


def _sp_end(head: str, sp: int) -> int:
    """`.sp` 那段的结束下标（按 `<span` / `</span>` **深度回零** —— 工具区里常嵌着别的 span）。

    ⚠️ 入参 `sp` 是 `class="sp` 的下标（**已经在外面那层 `<span` 里**）⇒ 起始深度必须是 **1**：
       从 0 起算会把"内层 span 的闭合"当成 `.sp` 的收尾 ⇒ 把合规的卡头误报成不合规（本件第一版就这么错过）。
    """
    j, depth = sp, 1
    while j < len(head):
        if head.startswith("<span", j):
            depth, j = depth + 1, j + 5
        elif head.startswith("</span>", j):
            depth, j = depth - 1, j + 7
            if depth == 0:
                return j
        else:
            j += 1
    return len(head)


def cardhead_report() -> str:
    """守则 §5.13 的**两种**不合形态：① 按钮裸挂在标题后（判据抓的）② 按钮在 `.sp` 之外但仍在 `h4` 内（**判据盲区**）。"""
    src = "\n".join(
        [INDEX.read_text(encoding="utf-8")]
        + [p.read_text(encoding="utf-8") for p in sorted((WEB / "shell").glob("*.js"))]
    )
    lines = src.splitlines()
    bare: list[str] = []
    outside: list[str] = []
    for i, ln in enumerate(lines):
        for m in re.finditer(r"<h4[> ]", ln):
            seg = ln[m.start():] + "\n" + "\n".join(lines[i + 1:i + 6])   # 与判据同一个 6 行窗口
            end = seg.find("</h4>")
            head = seg[:end] if end > 0 else seg
            b = head.find("<button")
            if b < 0:
                continue
            spm = re.search(r'class="sp[\s"]', head)
            tag = " ".join(head.split())[:80]
            if not spm or spm.start() > b:
                bare.append(tag)
            elif b > _sp_end(head, spm.start()):
                outside.append(tag)
    out = ["── 卡头形态清点（守则 §5.13）──",
           f"  ① 按钮**裸挂**在标题后（判据 `test_卡头里的按钮都在右侧工具区` 会抓）：{len(bare)} 处"]
    out += [f"     · {x}" for x in bare[:6]]
    out += [f"  ② 按钮在 `.sp` **之外**（仍在 `h4` 内 —— ⚠️ 上面那条判据的**盲区**）：{len(outside)} 处"]
    out += [f"     · {x}" for x in outside[:8]]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="逐页量测（只读）")
    ap.add_argument("pages", nargs="+", help="页 id，如 m05 / m03 / home")
    ap.add_argument("--shell", action="store_true", help="顺带扫 `shell/*.js` 里该页的落点分布")
    ap.add_argument("--cardhead", action="store_true",
                    help="全站卡头形态清点（守则 §5.13：**两种**形态都列 —— 判据现在只抓第一种）")
    a = ap.parse_args()

    lines = INDEX.read_text(encoding="utf-8").splitlines()
    table = slices(lines)
    print(f"index.html {len(lines)} 行 · 切片 {len(table)} 个（`V.*` 原型切片 · ⛔ 按计划 §23 不许搬）")
    print()
    for page in a.pages:
        if page not in table:
            print(f"⛔ 找不到 `V.{page}` 切片；可用：{' '.join(sorted(table))}")
            continue
        measure(page, lines, table[page])

    if a.shell:
        for page in a.pages:
            print(f"── `{page}` 在接线层（`shell/*.js`）的落点 ──")
            for p in sorted((WEB / "shell").glob("*.js")):
                hits = [i + 1 for i, l in enumerate(p.read_text(encoding="utf-8").splitlines())
                        if re.search(rf"\b{re.escape(page)}\b", l)]
                if hits:
                    print(f"  {p.name:<18} {len(hits):>3} 处  行号：{hits[:14]}{' …' if len(hits) > 14 else ''}")
            print()

    if a.cardhead:
        print(cardhead_report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
