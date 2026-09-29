#!/usr/bin/env python
"""`TAIL-167`：把 `m03` 那 4 条「用户看得见」的判据**登记**进交付面契约（**一次性契约面改动脚本** · 2026-09-29）。

**为什么有它**（本仓规矩：动交付面 `.json` **绝不文本替换**）：
  `PRD/验收/验收基线.json` 是**只读快照式**的机读基线（工程内不留副本）⇒
  ① `json.loads` → 改 dict → `json.dumps(indent=2, ensure_ascii=False)` ＋ 每行 CRLF ＋ 末尾一个 CRLF；
  ② **改前先做 round-trip 逐字节比对**（证明"我这份 dumps 参数就是它原来的排版"，不等就**拒写**）。

**它做什么**（三件 —— 用户 2026-09-29 裁定 `A`：只登记那 4 条，⛔ 不新写判据）：
  1. `验收基线.json`：`ACC-PAY-LIST-001` 加 **4 个判据点** `001-11`…`001-14`
     （把 `backend/tests/test_wired_m03_list.py` 里**早已存在**、却挂 `@acc()`（= 显式"不绑定"）的 4 条
     **按测试名**绑定 —— 它们测的都是**用户看得见**的行为）；顺手把该用例 `cover` 补 `§4.2.2` / `§4.2.7`
     （它自己的判据点早就在引这两节，而 cover 里一直没有）；
  2. `backend/tests/test_wired_m03_list.py`：4 条测试的 `@acc()` ⇒ `@acc("ACC-PAY-LIST-001", "001-NN")`
     （⚠️ **按 `def test_<名字>` 定位**，⛔ 不用"顺序对齐"—— 本件里还有 4 条**故意不登记**的 `@acc()`）；
  3. `PRD/验收/用例索引.md`：该用例那行的「来源」栏补一条**变更说明**（日期 ＋ 判据点号 ＋ 用户裁定代号）。

用法（工程根）：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_doc_tail167.py --check   # 只自检，不写
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_doc_tail167.py --write   # 真写（交付面已备份）
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
FACE = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用")
BASELINE = FACE / "PRD" / "验收" / "验收基线.json"
INDEX = FACE / "PRD" / "验收" / "用例索引.md"
TESTS = REPO / "backend" / "tests"
TESTFILE = TESTS / "test_wired_m03_list.py"
BACKUP = REPO / ".workbuddy" / "backups" / "交付面-20260929-0840"

CASE = "ACC-PAY-LIST-001"

#: 4 个新判据点：`(id, kind, claim, cover)` —— ⚠️ `claim` 一律写**用户看得见的后果**（守则 §0：判据要钉会上屏的东西）
NEW_POINTS: tuple[tuple[str, str, str, str], ...] = (
    (
        "001-11", "outcome",
        "汇总 pill 把「**i8 已撤单但有牵涉**」（已挂付款流水 / 集采关联）的行**单独报一档**（带悬停说明与去处）"
        "—— 这类行按 §4.2.7 **仍参与统计**，只报总数用户看不出「还有几笔要自己处理」",
        "§4.2.7",
    ),
    (
        "001-12", "outcome",
        "**空态行**：跨列数**由表头派生**（表头改列数不会错位），且明确告诉用户**剔除了的行去哪儿看**"
        "（切「分类 = 剔除」）—— ⛔ 不接受只留一片空白",
        "§4.2.2",
    ),
    (
        "001-13", "outcome",
        "**金额列点列头排序按数值**（不是字符串 —— 按字符串排会出现 `10,000.00 < 900.00` ⇒ 用户**看错数**）；"
        "合计行与草稿行**钉在表尾**、不参与排序（改完排序也还在最后一排）",
        "§4.2.5",
    ),
    (
        "001-14", "outcome",
        "行内**勾选框与标签由渲染层注入**（数据里带的勾选态一律不认）—— 保证「能勾 / 不能勾」只由本系统的口径"
        "（**付款候选 ∪ 剔除行**：剔除行必须能勾，否则「恢复剔除」这条路走不通）决定",
        "§4.2.2",
    ),
)

#: 『测试名 → 判据点号』（⚠️ **按名字**绑定；本件里另有 4 条 `@acc()` 是**故意不登记**的）
BINDINGS: dict[str, str] = {
    "test_汇总pill把撤单里有牵涉的单独报一档": "001-11",
    "test_壳里空态行跨列数由表头派生且指出剔除行去哪看": "001-12",
    "test_壳里金额列按数值排序而不是按字符串": "001-13",
    "test_壳里勾选框与标签由渲染注入而不是数据带的": "001-14",
}

#: 该用例 `cover` 要补的两节（它自己的判据点早就在引，cover 一直没写）
COVER_ADD = ("§4.2.2", "§4.2.7")

#: 用例索引那行「来源」栏要补的变更说明（⚠️ 照该表既有写法：⭐ **日期** ＋ 判据点号 ＋ 裁定代号）
INDEX_NOTE = (
    "；⭐ **2026-09-29** 补判据点 `001-11`…`001-14`：把 `backend/tests/test_wired_m03_list.py` 里 4 条"
    "**早就存在**、却挂 `@acc()`（= 显式「不绑定」⇒ 四态报表里看不见）的「用户看得见」判据**登记**进来"
    "（撤单有牵涉单独报一档 / 空态跨列与指路 / 金额列按数值排序 / 勾选框与标签由渲染注入）"
    "—— ⛔ 不新写断言、⛔ 不为涨绿数硬绑（用户 2026-09-29 裁定 `A`；同批该用例 `cover` 补 `§4.2.2` / `§4.2.7`）"
)


def _dump(obj: dict) -> str:
    """基线实测格式（`_doc_tail123.py` 用 **round-trip 逐字节比对**实测过，⛔ 别凭记忆改参数）：
    `indent=2` · `ensure_ascii=False` · 每行 CRLF · 末尾**一个** CRLF。"""
    return json.dumps(obj, indent=2, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"


def patch_tests(write: bool) -> list[str]:
    """按**测试名**把那 4 条 `@acc()` 换成带判据点的装饰器。→ 报告行。"""
    raw = TESTFILE.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    for name, pid in BINDINGS.items():
        defs = [i for i, ln in enumerate(lines) if ln.startswith(f"def {name}(")]
        assert len(defs) == 1, f"{name}：找到 {len(defs)} 个定义（要 1 个）"
        j = defs[0] - 1
        while j >= 0 and not lines[j].strip():
            j -= 1
        assert lines[j].strip() == "@acc()", f"{name}：它上面那行不是裸 `@acc()`（是 {lines[j].strip()!r}）⇒ 别改"
        lines[j] = lines[j].replace("@acc()", f'@acc("{CASE}", "{pid}")')
        out.append(f"  {name:<44} ⇒ {pid}")
    if write:
        TESTFILE.write_text(nl.join(lines), encoding="utf-8", newline="")
    return out


def patch_index(write: bool) -> str:
    """给 `用例索引.md` 里该用例那行的「来源」栏补变更说明（⚠️ 保持原换行风格）。"""
    raw = INDEX.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")
    hits = [i for i, ln in enumerate(lines) if ln.startswith(f"| `{CASE}` |")]
    assert len(hits) == 1, f"用例索引里 `{CASE}` 命中 {len(hits)} 行（要 1 行）"
    i = hits[0]
    assert INDEX_NOTE not in lines[i], "变更说明已在 ⇒ 本脚本跑过了"
    row = lines[i].rstrip()
    assert row.endswith("|"), f"该行不以 `|` 收尾 ⇒ 表结构变了：{row[-40:]!r}"
    lines[i] = row[:-1].rstrip() + INDEX_NOTE + " |"
    if write:
        INDEX.write_text(nl.join(lines), encoding="utf-8", newline="")
    return f"  用例索引.md `{CASE}` 行 ⇒ 已补变更说明（{len(INDEX_NOTE)} 字）"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    # ⚠️ 必须 `newline=""`：默认（universal newlines）会把 `\r\n` 折成 `\n` ⇒ round-trip 永远不等。
    raw = BASELINE.read_text(encoding="utf-8", newline="")
    obj = json.loads(raw)
    rt = _dump(obj)
    same = rt == raw
    print(f"round-trip 逐字节比对：{'✅ 一致' if same else '⛔ 不一致（⛔ 别写！）'}")
    if not same:
        for i, (a, b) in enumerate(zip(raw, rt)):
            if a != b:
                print(f"   首个差异 @{i}：原 {a!r} vs 我的 {b!r}")
                break
        print(f"   长度：原 {len(raw)} vs 我的 {len(rt)}")
        return 1
    print(f"交付面备份在位：{'✅' if BACKUP.exists() else '⛔ 先备份再改'} {BACKUP}")
    if not BACKUP.exists():
        return 1

    case = obj["cases"][CASE]
    ids = [p["id"] for p in case["points"]]
    assert ids == [f"001-{i:02d}" for i in range(1, len(ids) + 1)], f"编号不顺延：{ids}"
    assert len(ids) == 10, f"`{CASE}` 现有 {len(ids)} 个点（期望 10）⇒ 基线已变，先核再改"
    before = sum(len(v.get("points") or []) for v in obj["cases"].values())
    print(f"现有用例 {len(obj['cases'])} 条 · 判据点合计 {before} · `{CASE}` 现 {len(ids)} 点（{ids[0]}…{ids[-1]}）")

    case["points"].extend({"id": pid, "kind": kind, "claim": claim, "cover": cover}
                          for pid, kind, claim, cover in NEW_POINTS)
    for sec in COVER_ADD:
        if sec not in case["cover"]:
            case["cover"].append(sec)
    print(f"＋ `{CASE}` 加 {len(NEW_POINTS)} 点（001-11…001-14）· cover 补 {list(COVER_ADD)}")

    print("\n绑定（按测试名）：")
    print("\n".join(patch_tests(args.write)))
    print(patch_index(args.write))

    if args.write:
        BASELINE.write_text(_dump(obj), encoding="utf-8", newline="")
        back = json.loads(BASELINE.read_text(encoding="utf-8"))
        after = sum(len(v.get("points") or []) for v in back["cases"].values())
        assert after == before + len(NEW_POINTS), f"点数不对：{before} ⇒ {after}"
        print(f"\n✅ 已写回：判据点合计 {before} ⇒ **{after}**")
        print("   ⚠️ 接下来必做：全套 pytest（带 `ACC_RESULTS_PATH`）⇒ `acc_report` ⇒ 改四态计数锚点 ⇒ 全闸门")
    else:
        print(f"\n（`--check` 模式：⛔ 未写任何文件；写的话判据点会变成 {before + len(NEW_POINTS)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
