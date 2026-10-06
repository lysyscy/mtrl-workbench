r"""`TAIL-232` 修复脚本（幂等 · 可复跑 · `--write` 才落盘）—— **只做本票三堆，逐条带断言**。

堆1「能力编号不连续」：**不是断号，是排版损坏** —— 5 行表格行首多了一个 `|`
    （`MOD-03` 1· `MOD-04` 1· `MOD-10` 2· `MOD-14` 1）⇒ 尺子正则 `^\|\s*(\d+)\s*\|` 抓不到
    ⇒ 报成「缺号」。**能力内容一字不动，只删行首多出的那个竖线**（不重排编号 · 不造能力）。

堆1b「页脚孤儿行」：`MOD-14.md` 的 `ACC-CFG-SETUP-001` §四验收清单那一条**掉到文件页脚之后**
    ⇒ 渲染出来是页脚下面的孤行。**归位**到§四 的 `ACC-*` 清单里（挪位，不改一个字）。

堆2「用例索引漏登」：补两行 `ACC-JC-IGNORE-001` / `ACC-UI-SHELL-001`
    —— 两条都在 `验收基线.json` 里（4 点 / 63 点），但**全交付面再无第二处落点**
    ⇒ 需求号与来源**照基线的 `req` / `source` 抄**，不自己编。

⛔ 堆3（`MOD-06` / `MOD-11` / `MOD-14` 能力表漏引用）**本脚本一律不动** —— 那是 `TAIL-234`
    （WPS 云同步回退）的病：实测 `MOD-11.md` 整份是 `TAIL-97` **之前**的旧版。

用法：`python _tail232_fix.py`（默认干跑）/ `--write`（真写）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools" / "audit"))
from audit_common import delivery_root

FACE = delivery_root()
MOD_DIR = FACE / "PRD" / "02-功能规格"
INDEX = FACE / "PRD" / "验收" / "用例索引.md"
BACKUP_DIR = pathlib.Path(__file__).resolve().parents[2] / ".codebuddy" / "backups" / "2026-10-06-TAIL-232"
ACC_HEAD_RE = re.compile(r"^\|\s*`(ACC-[A-Z0-9-]+)`\s*\|", re.M)

# ── 堆1：行首多一个竖线的那5 行（按「文件 → 行首前缀」定位，逐条断言唯一） ──────────
BAD_ROWS: list[tuple[str, str]] = [
    ("MOD-03.md", "|| 14 | **集采付款的特殊处理**"),
    ("MOD-04.md", "|| 11 | 实际执行偏离的处理"),
    ("MOD-10.md", "|| 2 | 机械费的**源头**"),
    ("MOD-10.md", "|| 3 | ⭐ **「结算金额」由源头派生、只读**"),
    ("MOD-14.md", "|| 6 | 全局一致性清单的**展示**"),
]

# ── 堆1b：页脚之后那条孤儿行（挪回§四 清单里，锚 = 它前面那条 `ACC-X-DEL-001`） ──────────
ORPHAN_ANCHOR = "- `ACC-X-DEL-001` —— 配置类数据的删除策略（**本页不单独判**）"
ORPHAN_LINE = ("- `ACC-CFG-SETUP-001` —— **系统设置**：连接参数项 · 取值优先级（库→`.env`）· "
               "**改动留痕** · 版式 ID 反直觉提示")

# ── 堆2：补进 `用例索引.md` 的两行（照邻居写法；需求号/来源取自 `验收基线.json`） ──────────
LAST_ROW_PREFIX = "| `ACC-ODDVAL-001` |"
NEW_ROWS = [
    "| `ACC-JC-IGNORE-001` | `REQ-R10` | **需新建**（**2026-09-25 `TAIL-101`**：集采**不纳入名单** —— "
    "命中即剔除 / 名单空逐字节一致 / 反例不许放行 / 同名幂等可复活。规则主人 =《说明书》§6.5.4） |",
    "| `ACC-UI-SHELL-001` | — | **登记既有判据**（**2026-09-28 `TAIL-123`**：按《前端设计守则》把**已存在**的"
    "机器判据登记进基线 —— 离线 10 件 ＋ 真机段） |",
]
NEW_IDS = {r.split("`")[1] for r in NEW_ROWS}


def md5_bytes(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def load(path: pathlib.Path) -> tuple[list[str], str]:
    raw = path.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    return raw.replace("\r\n", "\n").split("\n"), nl


def dump(lines: list[str], nl: str) -> str:
    return nl.join(lines)


def one(hits: list[int], where: str) -> int:
    assert len(hits) == 1, f"{where}：命中 {len(hits)} 处（要 1 处）—— ⛔ 先核原文，别猜"
    return hits[0]


def plan_mods() -> list[tuple[pathlib.Path, list[str], str, list[str]]]:
    """⇒ [(路径, 改后行, 落点, 逐条改动说明)]"""
    out = []
    by_file: dict[str, list[str]] = {}
    for fname, prefix in BAD_ROWS:
        by_file.setdefault(fname, []).append(prefix)
    for fname, prefixes in by_file.items():
        path = MOD_DIR / fname
        lines, nl = load(path)
        notes = []
        for prefix in prefixes:
            hits = [i for i, ln in enumerate(lines) if ln.startswith(prefix)]
            if not hits:
                already = [i for i, ln in enumerate(lines) if ln.startswith(prefix[1:])]
                one(already, f"{fname} 已修形态 `{prefix[1:]}`")   # 幂等：已在就跳过
                notes.append(f"已是修好的形态 ⇒ 跳过（幂等）")
                continue
            i = one(hits, f"{fname} `{prefix}`")
            before = lines[i]
            lines[i] = before[1:]                    # ⛔ **删**行首多出的竖线（不是加）
            assert lines[i] == prefix[1:] + before[len(prefix):], "改动超出「只删行首一个竖线」"
            assert lines[i].count("|") == before.count("|") - 1, "竖线数没减一个"
            notes.append(f":{i + 1} 行首多一个竖线 ⇒ 已删")
        out.append((path, lines, nl, notes))
    return out


def plan_orphan() -> tuple[pathlib.Path, list[str], str, list[str]]:
    path = MOD_DIR / "MOD-14.md"
    lines, nl = load(path)
    if ORPHAN_LINE not in lines:
        return path, lines, nl, ["页脚孤儿行不在 ⇒ 跳过（幂等）"]
    oi = one([i for i, ln in enumerate(lines) if ln == ORPHAN_LINE], "MOD-14 孤儿行")
    # 页脚之后才叫孤儿；否则是「已在清单里」
    foot = one([i for i, ln in enumerate(lines) if ln.startswith("> **本文件性质**")], "MOD-14 页脚")
    assert oi > foot, "那条不在页脚之后 ⇒ 锚点变了，先核原文"
    ai = one([i for i, ln in enumerate(lines) if ln == ORPHAN_ANCHOR], "MOD-14 §四 锚行")
    assert ai < foot, "锚行不在§四 里，先核原文"
    del lines[oi]
    lines.insert(ai + 1, ORPHAN_LINE)
    assert lines[lines.index(ORPHAN_LINE)] == ORPHAN_LINE
    return path, lines, nl, [f":{oi + 1} 页脚之后的孤儿行 ⇒ 已归位到 §四 清单（挪位，一字未改）"]


def plan_index() -> tuple[pathlib.Path, list[str], str, list[str]]:
    path = INDEX
    raw = path.read_text(encoding="utf-8", newline="")
    lines, nl = load(path)
    # ⭐ 幂等按 **ACC 号**判（不是整行文本 —— 措辞要能就地更新）：
    # 每个号最多一行；有就替换成当前措辞；没有就插。
    at = one([i for i, ln in enumerate(lines) if ln.startswith(LAST_ROW_PREFIX)], "用例索引末行锚点")
    notes = []
    for row in NEW_ROWS:
        acc = row.split("`")[1]
        hits = [i for i, ln in enumerate(lines) if ln.startswith(f"| `{acc}` |")]
        assert len(hits) <= 1, f"用例索引里 `{acc}` 有 {len(hits)} 行 —— ⛔ 先核原文"
        if hits:
            i = hits[0]
            if lines[i] == row:
                notes.append(f"`{acc}` 行已在且措辞一致 ⇒ 跳过（幂等）")
            else:
                lines[i] = row
                notes.append(f"`{acc}` 行已在 ⇒ **就地更新措辞**")
            continue
        assert lines[at + 1].strip() == "", f"末行之后不是空行（{lines[at + 1]!r}）—— ⛔ 先核原文"
        nxt = next(ln for ln in lines[at + 1:] if ln.strip())
        assert not nxt.startswith("| `ACC-"), f"末行之后还有表格行（{nxt[:40]!r}）—— ⛔ 先核原文"
        at += 1
        lines.insert(at, row)
        notes.append(f"补登记 `{acc}` ⇒ 末行之后")
    # 有意义的不变式：**基线里缺的登记 == 本次要补的这两条**（集合精确相等）
    #   ⚠️ 不能拿「行数差」当判据：索引里有 2 条「不建用例」（`ACC-X-ATT-001/002`）**按规矩不在基线**
    #   ⇒ 行数会正好抵消（66 − 66 = 0），那是巧合，不是判据。
    idx_ids = set(ACC_HEAD_RE.findall(dump(lines, nl)))
    cases = set(json.loads((FACE / "PRD" / "验收" / "验收基线.json").read_text(encoding="utf-8"))["cases"])
    assert cases - idx_ids == set(), f"基线里还缺登记 = {sorted(cases - idx_ids)} —— ⛔ 先核原文"
    assert idx_ids - cases == {"ACC-X-ATT-001", "ACC-X-ATT-002"}, (
        f"索引里多出 {sorted(idx_ids - cases)}（只允许两条「不建用例」）—— ⛔ 先核原文")
    return path, lines, nl, notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="真写（默认干跑）")
    args = ap.parse_args()

    plans = plan_mods() + [plan_orphan()] + [plan_index()]
    before = {p: md5_bytes(p.read_bytes()) for p, _l, _n, _t in plans}

    print("改前 MD5：")
    for p in sorted(before, key=lambda x: x.name):
        print(f"  {p.name:<16} {before[p]}")

    print("\n逐件判定：")
    changed: list[tuple[pathlib.Path, str]] = []
    for path, lines, nl, notes in plans:
        for note in notes:
            print(f"  {path.name:<14} {note}")
        new = dump(lines, nl)
        old = path.read_text(encoding="utf-8", newline="")
        o = old.replace("\r\n", "\n").split("\n")
        n = new.replace("\r\n", "\n").split("\n")
        # ⚠️ **按多重集判**而不是按下标 —— 「挪位」会让后面每行都错位，下标比法全红。
        #   挪位 ⇒ 差集为空；改字/插行 ⇒ 差集里只剩那几行 ⇒ 逐行核对它们确实是「目标行」。
        removed = list((Counter(o) - Counter(n)).elements())
        added = list((Counter(n) - Counter(o)).elements())
        bad = [ln for ln in removed + added
               if not ln.startswith(("||", "| `ACC-", "- `ACC-", "| ", "- ℹ️"))]
        assert not bad, f"{path.name}：动到了非目标行（{[b[:40] for b in bad]}）—— ⛔ 先核原文"
        assert len(removed) <= len(BAD_ROWS) + len(NEW_ROWS), f"{path.name}：改动行数超预算"
        if new != old:
            changed.append((path, new))
            print(f"{'':16}（多重集差：删 {len(removed)} 行 / 增 {len(added)} 行"
                  f"{'·纯挪位' if not removed and not added else ''}）")

    if not args.write:
        print(f"\n（干跑：{len(changed)}/{len(plans)} 件会有变化；跑 `--write` 才落盘）")
        return 0

    print(f"\n落盘 {len(changed)} 件：")
    ledger = []
    for path, new in changed:
        # ⚠️ 坏字符（U+FFFD）会静默落盘 ⇒ 写前先扫（`MEMORY.md §四` 坑 ④）
        assert "\ufffd" not in new, f"{path.name}：文本里有U+FFFD ⇒ ⛔ 拒绝写"
        path.write_text(new, encoding="utf-8", newline="")
        back = path.read_bytes()
        assert "\ufffd" not in back.decode("utf-8"), f"{path.name}：写回后有 U+FFFD ⇒ ⛔ 已写坏"
        assert back == new.encode("utf-8"), f"{path.name}：写回与预期不一致"
        md5 = md5_bytes(back)
        ledger.append(f"{path.name}\t{before[path]}\t{md5}")
        print(f"  {path.name:<16} {before[path]} → {md5}")
    for path, _l, _n, _t in plans:
        if path not in dict(changed):
            print(f"  {path.name:<16} 未变（幂等跳过，没碰 WPS 同步树）")

    # 改后 MD5 **落盘对账**（票面 L12/L43 要求「改后再核一次」；不留纸面 = 下轮无从核）
    out = BACKUP_DIR / "_MD5-改后.tsv"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("件\t改前\t改后\n" + "\n".join(ledger) + "\n", encoding="utf-8", newline="\n")
    print(f"\nMD5 对账落盘 = {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())