#!/usr/bin/env python
"""**交付面尾部守卫** —— `T27`（页脚之后不许有内容）＋ `T28`（`PRD/` 规格件**只许变长**）。

> 2026-10-06 立（`TAIL-234`）· 由 `doc_audit` 调用（同一份 `raw` ⇒ 同一个 rc）

## 为什么是这两条（**都是真事故打出来的，不是想出来的**）

- **`T27`**：当天实测 `MOD-14.md` 的两条 `ACC-*` 验收清单条目**掉到了页脚之后** ⇒ 渲染出来是
  页脚下面的孤行。⚠️ `T1`–`T26` **没有一层能看见它** —— 用例号是真的、路径是真的、只是**位置错了**
  （本仓最贵的一族：「内容齐了」≠「摆对了」）。
- **`T28`**：WPS 云同步把整个交付面**盖回过历史快照**（至少两次）。实测退化件与真源的差别
  **多数是"等长"**（24 件里只有 2 件变短）⇒ **只钉行数不够**，必须再钉一个**抗改词、抗改行**的锚点。

## 三条形态纪律（⛔ 违反其中任何一条，这张网就会变成噪音源）

1. **相对基线·只许变长** —— ⛔ 不用「绝对行数」：那会让**每一次正常增删都报红**。
   （与 `T21` 的「只许变短」同款思路，方向相反。）
2. **锚点只取机械可算的那一个**（编号表的**最大行号**）—— ⛔ 不手挑 24 条关键句：
   手挑的锚点会随正常改词而失效，**失效的那天没人记得它曾管过什么** ⇒ 判据自己悄悄退场。
   ⚠️ 行号锚点**抗改词、抗改行**，只对**删行 / 删整节**有牙 ⇒ 已知缺口写在下面「⛔ 抓不到什么」。
3. **单一出口** —— 标记、排除目录、扫描面、基线表**全部只定义一次**
   （前三个在 `audit_common`、基线表在本件）⇒ ⛔ 别在尺子、变异脚本、探针里各写一遍。

##⛔ 抓不到什么（**明写，免得把覆盖当全校**）

- 「等长但整段换成旧内容」（回退删掉的行数与新增的恰好抵平）⇒ 要靠人眼。
- `PRD/00-总览.md` **没有页脚标记** ⇒ 该件不在 `T27` 眼里（不是"判过了"，是**没覆盖**）。
- 每件的**编号表**被整表删掉又按新内容重建（行数不降、行号不降）⇒ 抓不到。

## 目标机（**不装交付面**）上的代价

⛔ 拿不到交付面根 ⇒ 两条都**跳过、不并进 rc**（同 `doc_audit --ui` 的三条「跳过」：那是
`ops/deployment.md` 写明的已知代价，⛔ 判红只会让人开始忽略它 —— **比不判还坏**）。

用法：
    backend/.venv/Scripts/python.exe tools/audit/audit_face.py            # 跑两条（有红即非零退出）
    backend/.venv/Scripts/python.exe tools/audit/audit_face.py --stamp# ⭐ 打印当前基线表（重录时用）

⚠️ **重录基线的口径**：改了件（有意增删）⇒ **同批**把该件的数抄进 `PRD_DOC_BASELINE`
⇒ 「一个数两处用」同批改两处。⛔ 别为了让红变绿去改判据。
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from audit_common import (                                          # noqa: E402
    FOOTER_EXCLUDE_PARTS, FOOTER_MARKER, FOOTER_SCAN_GLOB, PRD_DOC_GLOB,
    RED, YELLOW, delivery_root,
)

#: 编号表（能力表 / 清单表）里 `| N |` 那一列 —— `T28` 的行号锚点就取它的**最大值**。
_ROW_NUM = re.compile(r"^\|\s*(\d+)\s*\|")


def _lines_of(path: pathlib.Path) -> list[str]:
    """**行数与行内容的唯一定义**（⛔ 别在别处再写一遍 `split("\\n")`）。

    ⚠️ 用 `splitlines()` 而不是 `split("\\n")`：后者会把**末尾那个换行**多算一行
    ⇒ 同一份件在两种写法下差 1，基线表就跟着漂。
    """
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _row_max(lines: list[str]) -> int:
    """编号表（`| N |`）的最大编号；没有 ⇒ 0。"""
    best = 0
    for ln in lines:
        m = _ROW_NUM.match(ln)
        if m:
            best = max(best, int(m.group(1)))
    return best


#: ⭐⭐ **PRD 规格件基线表（唯一真源）** —— `相对路径 → (行数, 编号表最大行号)`。
#:
#: ⚠️ **只许变长**：`行数` 与 `最大行号` 都**只当下限**（涨了不管、跌了即红）。
#: ⛔ **别把"哪几件、各多少"抄进 `ops/阈值表.md`** —— 抄一份必然过期（同 `LINE_WALL_BASELINE` 的口径，
#: 那条明写「⛔ 别把"哪几件、各几行"抄到本表」）⇒ 阈值表只登记**阈值**，数据留在这里。
#: ⚠️ **改动纪律**：有意增删某件 ⇒ 同批更新这一行（`--stamp` 打印的就是这张表的当前应然形态）。
#: ⛔ **不要为了"让红变绿"而放宽基线** —— 先问「这份件是不是真的被改小了/被换回旧版了」。
PRD_DOC_BASELINE: dict[str, tuple[int, int]] = {
    "PRD/00-总览.md": (59, 0),
    "PRD/01-需求索引.md": (83, 0),
    "PRD/02-功能规格/MOD-01.md": (70, 12),
    "PRD/02-功能规格/MOD-02.md": (62, 8),
    "PRD/02-功能规格/MOD-03.md": (92, 17),
    "PRD/02-功能规格/MOD-04.md": (75, 12),
    "PRD/02-功能规格/MOD-05.md": (77, 11),
    "PRD/02-功能规格/MOD-06.md": (70, 11),
    "PRD/02-功能规格/MOD-07.md": (74, 11),
    "PRD/02-功能规格/MOD-08.md": (68, 8),
    "PRD/02-功能规格/MOD-09.md": (67, 9),
    "PRD/02-功能规格/MOD-10.md": (64, 5),
    "PRD/02-功能规格/MOD-11.md": (75, 14),
    "PRD/02-功能规格/MOD-12.md": (69, 9),
    "PRD/02-功能规格/MOD-13.md": (75, 12),
    "PRD/02-功能规格/MOD-14.md": (75, 11),
    "PRD/02-功能规格/MOD-15.md": (68, 9),
    "PRD/02-功能规格/README.md": (50, 0),
    "PRD/03-非功能需求.md": (72, 11),
    "PRD/04-Non-goals.md": (31, 0),
    "PRD/05-任务分解.md": (87, 6),
    "PRD/99-追溯表.md": (167, 9),
    "PRD/验收/README.md": (39, 0),
    "PRD/验收/用例索引.md": (94, 0),
}


def _hit(code: str, rel: str, what: str, why: str, fix: str, *, line: int = 1,
         level: str = RED) -> dict:
    """本件共用的命中形状（与 `audit_work._hit` 同款；⛔ 别在别处手拼同样的 dict）。"""
    return {"code": code, "side": "面", "rel": rel, "line": line,
            "what": what, "why": why, "fix": fix, "level": level, "text": ""}


def _excluded(rel: str) -> bool:
    """排除目录（`FOOTER_EXCLUDE_PARTS`）—— 归档留痕里"页脚后有内容"是**对的**，不是缺陷。"""
    parts = pathlib.PurePosixPath(rel).parts[:-1]
    return any(p in FOOTER_EXCLUDE_PARTS for p in parts)


# ----------------------------------------------------------------------- T27 页脚


#: ⭐ **`T27` 的扫描实现 —— 唯一一份**（`(相对路径, 页脚之后的非空行, 是否被排除)`）。
#:
#: ⚠️ **为什么抽出来**：`_mut_facedoc.py`（变异件）也要"页脚之后有没有东西"，而
#: `/code-review` 2026-10-06 当场指出它在那边**又写了一遍 `rglob` ＋ `parts[:-1]` ＋ 标记字面**
#: ⇒ 判据一改它不跟着变（本仓老路："同一件事两处写"＝必漂）⇒ **两边都调本函数**。
#: 第三段 `是否被排除` 是给变异件用的：它要证明"排除清单 **load-bearing**"
#:（那几处孤儿**确实还在**，只是被排除掉了 ⇒ 不是把扫描面缩窄当修复）。
def scan_footer_tails() -> list[tuple[str, list[str], bool]]:
    root = delivery_root()
    if not root or not root.is_dir():
        return []
    out: list[tuple[str, list[str], bool]] = []
    for f in sorted(root.glob(FOOTER_SCAN_GLOB)):
        if not f.is_file():
            continue
        rel = f.relative_to(root).as_posix()
        lines = _lines_of(f)
        idx = next((i for i, ln in enumerate(lines) if ln.startswith(FOOTER_MARKER)), None)
        tail: list[str] = []
        if idx is not None:
            tail = [ln for i, ln in enumerate(lines[idx + 1:], start=idx + 2) if ln.strip()]
        out.append((rel, tail, _excluded(rel)))
    return out


def check_footer_tail() -> list[dict]:
    """`T27`：**页脚标记之后还有非空行** ⇒ 红（⚠️ 排除目录按实测，不按想象）。

    ⭐ 扫描在 `scan_footer_tails()`（**唯一一份**）· 本函数只把它的结果变成命中。
    ⚠️ **一份件可以有多次页脚标记吗** —— 不检查（实测 24 件各只有一处；
    真出现了"两处页脚"也该由人去核，本条只抓"标记之后还有东西"这一种形态）。
    """
    hits: list[dict] = []
    for rel, tail, excluded in scan_footer_tails():
        if excluded or not tail:
            continue
        hits.append(_hit(
            "T27", rel, f"页脚标记之后还有内容（第 {len(tail)} 处）：{tail[0].strip()[:40]}",
            "落款之后的内容渲染出来是孤行 —— 用例号 / 路径都是真的，⛔ 所以 `T1`–`T26` 一层都看不见它"
            "（本仓最贵的一族：「内容齐了」≠「摆对了」）",
            "把那几行挪回它该在的章节（**挪位，别改字**）；若它确实该在页脚之后，"
            "那就把它移到另一份件或另起一件 —— 页脚之后不许留内容",
            line=0))
    return hits


# ----------------------------------------------------------------------- T28 基线


def check_prd_baseline() -> list[dict]:
    """`T28`**：`PRD/` 规格件**只许变长** ＋ **编号表只许变多**（红）／新件未登记（黄）。

    ⚠️ **为什么"缺件"也判红**：交付面被云同步盖回旧版时，最先消失的往往就是**整件**
    （本仓真发生过）。修法 = 确认是有意删的之后，同批把基线表里那一行删掉。
    """
    root = delivery_root()
    if not root or not root.is_dir():
        return []
    hits: list[dict] = []
    seen: set[str] = set()
    for f in sorted(root.glob(PRD_DOC_GLOB)):
        if not f.is_file():
            continue
        rel = f.relative_to(root).as_posix()
        seen.add(rel)
        lines = _lines_of(f)
        n_now, row_now = len(lines), _row_max(lines)
        base = PRD_DOC_BASELINE.get(rel)
        if base is None:
            hits.append(_hit(
                "T28", rel, f"新件未登记基线（现 {n_now} 行 · 编号表最大 {row_now}）",
                "⛔ 没有基线就判不了「只许变长」—— 新件进来这一轮是**裸奔**的（下次回退就抓不到）",
                "跑 `tools/audit/audit_face.py --stamp` 把这一行抄进 `PRD_DOC_BASELINE`",
                level=YELLOW))
            continue
        n_base, row_base = base
        if n_now < n_base:
            hits.append(_hit(
                "T28", rel, f"变短了：{n_now} 行 < 基线 {n_base} 行（少 {n_base - n_now} 行）",
                "交付面被**整体换回旧版本**的典型签名（WPS 云同步至少干过两次）—— "
                "⛔ 少掉的内容没有任何尺子看得见：本仓真出现过整份`MOD-11` 被换回 `TAIL-97` 之前",
                "确认是**有意**精简 ⇒ 同批把本表这一行改成新行数；"
                "⛔ 若不是有意（本票的常态就是这一种）⇒ 按备份/重新同步**恢复**"))
        if row_base and row_now < row_base:
            hits.append(_hit(
                "T28", rel, f"编号表最大行号变小：{row_now} < 基线 {row_base}（**等长也抓得到**的那一半）",
                "⭐ 行数相等时**抓不到**内容被换旧，这一半就是为它准备的："
                "编号表少到最后一行 ⇒ 一定是少了一节能力",
                "同上：有意删节 ⇒ 同批改本表；⛔ 若不是有意 ⇒ 恢复"))
    for rel in sorted(set(PRD_DOC_BASELINE) - seen):
        hits.append(_hit(
            "T28", rel, "基线里有、盘上已没有这件",
            "整件消失是交付面回退最重的一种形态 —— **比变短更危险**（连人眼都不容易立刻发现）",
            "确认是有意删件 ⇒ 同批把 `PRD_DOC_BASELINE` 里这一行删掉；⛔ 若不是 ⇒ 恢复该件"))
    return hits


# --------------------------------------------------------------------------- 出口


def summary() -> str:
    """**常态报一句**（同 `T23`/`T24`/`T25`/`T26` 那条理由：「判据存在 ≠ 被看见」）。"""
    rows = scan_footer_tails()
    if not rows:
        return "交付面尾部 `T27`/`T28`：⏭ 跳过（拿不到交付面根 —— 目标机不装交付面属已知代价）"
    n_foot = sum(1 for _rel, tail, _ex in rows if tail is not None and _has_marker(_rel))
    n_ex = sum(1 for _rel, _tail, ex in rows if ex)
    n_prd = len(list(delivery_root().glob(PRD_DOC_GLOB)))
    return (f"交付面尾部 `T27`/`T28` 结论：扫描 {len(rows)} 份件（页脚标记 {n_foot} 份 · "
            f"排除 {n_ex} 份 {'/'.join(FOOTER_EXCLUDE_PARTS)} 下）· `PRD` 基线 "
            f"{len(PRD_DOC_BASELINE)} 件 / 盘上 {n_prd} 件 ✅")


def _has_marker(rel: str) -> bool:
    """该件**有没有**页脚标记（`scan_footer_tails` 的第三段只给 tail ⇒ 这里另查一次标记）。"""
    f = delivery_root() / rel
    return any(ln.startswith(FOOTER_MARKER) for ln in _lines_of(f))


def stamp() -> str:
    """打印**当前应然**的基线表（重录用；⛔ 别手抄行数 —— 抄错一位就是一条假红）。

    ⚠️⚠️ **护栏：基线只能"变上"，变下要**显式承认**（2026-10-06 `/code-review` 抓到的真漏洞）**——
    没有它的话，「把退化件的全表 `--stamp` 追认一遍」就是**一条命令把回退洗白**，
    而 `T28` 的全部意义就是"不许变小"。⇒ 打印时**逐件对比现基线**，只要有任何一件变小就**大声报**。
    ⛔ 本函数**只打印、不写盘**（写基线＝改判据 ⇒ 按纪律要人点头）。
    """
    root = delivery_root()
    assert root and root.is_dir(), "拿不到交付面根"
    rows, lower = [], []
    for f in sorted(root.glob(PRD_DOC_GLOB)):
        rel = f.relative_to(root).as_posix()
        lines = _lines_of(f)
        now = (len(lines), _row_max(lines))
        base = PRD_DOC_BASELINE.get(rel)
        if base and (now[0] < base[0] or (base[1] and now[1] < base[1])):
            lower.append(f"{rel} 现 {now} < 基线 {base}")
        rows.append(f'    "{rel}": {now},')
    head = "PRD_DOC_BASELINE: dict[str, tuple[int, int]] = {\n" + "\n".join(rows) + "\n}"
    if lower:
        head += ("\n\n# ⛔⛔ **下面这些件比现基线小 —— 别直接抄！**\n"
                 + "\n".join(f"# #   {x}" for x in lower)
                 + "\n# ⛔ 要确认是**有意**精简，才照抄；否则那不是'精简'，是**回退/写坏**。")
    return head


def main() -> int:
    ap = argparse.ArgumentParser(description="交付面尾部守卫（T27/T28）")
    ap.add_argument("--stamp", action="store_true", help="打印当前应然的基线表")
    a = ap.parse_args()
    if a.stamp:
        print(stamp())
        return 0
    hits = check_footer_tail() + check_prd_baseline()
    print(summary())
    for h in hits:
        print(f"  [{'红' if h['level'] == RED else '黄'}] [{h['code']}] {h['side']}·{h['rel']}:{h['line']}  {h['what']}")
        print(f"        {h['why']} → {h['fix']}")
    n = sum(1 for h in hits if h["level"] == RED)
    print(f"\n必须修 {n} · 疑似 {len(hits) - n}")
    return 1 if n else 0


__all__ = ["PRD_DOC_BASELINE", "check_footer_tail", "check_prd_baseline",
           "scan_footer_tails", "stamp", "summary"]


if __name__ == "__main__":
    raise SystemExit(main())