#!/usr/bin/env python
"""`TAIL-64` P2④ 收尾：把 `m05` 那批「**用户看得见**」的壳判据**登记进交付面契约**（一次性契约面改动脚本 · 2026-09-29）。

**为什么有它**（照 `_doc_tail167.py` 的规程；本仓规矩：动交付面 `.json` **绝不文本替换**）：
  ① `json.loads` → 改 dict → `json.dumps(indent=2, ensure_ascii=False)` ＋ 每行 CRLF ＋ 末尾一个 CRLF；
  ② **改前先做 round-trip 逐字节比对**（证明"我这份 dumps 参数就是它原来的排版"，不等就**拒写**）。

**它做什么**（用户 2026-09-29 裁定 `A` · ⛔ **不新写断言**、⛔ **不为涨绿数硬绑**）：
  1. `backend/tests/test_wired_m05.py`：**按测试名**把 6 条挂 `@acc()`（= 显式"不绑定"）的判据绑上：
     · **3 条绑到已有的判据点**（claim 早就写着同一件事，只是没人绑）⇒ **判据点不涨**：
       `test_台账两侧共用同一个项目选择器且无切换口径` → `ACC-FLOW-LED-001/001-05`
       `test_撤销入口只在生效行且必须填原因` → `ACC-FLOW-LIST-001/001-04`
       `test_流水空态跨列由表头派生且不分页` → `ACC-FLOW-LIST-001/001-06`
     · **3 条新建判据点**（很值钱的行为，此前 claim 里没有）⇒ `ACC-FLOW-LED-001` 加 `001-12`…`001-14`：
       现状数/表尾正名/入口名/空月压暗 · 卡头按钮分组与点开有反馈 · 两条"点了没反应"的静默失败被挡住。
  2. `验收基线.json`：`ACC-FLOW-LED-001` 加那 3 个判据点（合计 **641 → 644**）。
  3. `PRD/验收/用例索引.md`：两条用例那行的「来源」栏补**变更说明**（日期 ＋ 判据点号 ＋ 裁定代号）。

用法（工程根；⚠️ 先跑 `artifacts/_face_backup.py` 备份交付面）：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_doc_m05bind.py --check   # 只自检，不写
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_doc_m05bind.py --write   # 真写
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
TESTFILE = REPO / "backend" / "tests" / "test_wired_m05.py"

CASE_LED = "ACC-FLOW-LED-001"
CASE_LIST = "ACC-FLOW-LIST-001"

#: 3 个**新**判据点：`(id, kind, claim, cover)`（⚠️ `cover` 用**说明书**节号，且都用本用例里已有的节）
NEW_POINTS: tuple[tuple[str, str, str, str], ...] = (
    (
        "001-12", "outcome",
        "逐月台账每栏**标题行先给「现状」**（「本项目当前欠款（含期初）」＋「最近一月新增」，且与**表尾那一格同源**"
        "—— ⛔ 两处各算一份迟早打架）；表尾写明「截至 YYYY-MM · 自期初起累计」并把「欠款」格标成「当前欠款」"
        "（⛔ 不退回旧形「合计：」—— 那会被读成各月数字相加）；两个期初录入入口**带分类名**"
        "（⛔ 不同名并排 ⇒ 认错就录错池子）；**空月压暗**（台账空月也出行 ⇒ 不压暗就看不出哪个月真发生过事）；"
        "备注可改要**提前说**（「点这一格就能改」）",
        "§4.5.4",
    ),
    (
        "001-13", "outcome",
        "台账卡头：**「看哪个项目」贴在它所管的那两栏表格之前**（⛔ 不挂卡头右上角 —— 用户报过「要在右上角选、离那么远」）·"
        " 卡头**只留一个**导出入口且按钮名写明「要先选项目」· 两个导出在**同一条面板**里、各自的项目范围挨着自己的动作 ·"
        " 两个 toggle **点开自己带 `.on`**（⛔ 不是写死）· 说明贴在面板里（⛔ 不用长 toast 顶替）",
        "§4.5.4",
    ),
    (
        "001-14", "outcome",
        "两条「点了没反应」的**静默失败**必须被挡住：**「导出总欠款」**真走后端导出端点（带 `projects=` = 所选与顺序），"
        "且 `url` 在**本动作体内声明**并走统一下载出口（⛔ 未声明标识符 ＋ `async` ⇒ 未捕获 rejection ⇒ 界面毫无反应）；"
        "**「删除期初行」**的行 id 不许写死假值、比较要归一成字符串",
        "§7.1",
    ),
)

#: 「`@acc()` 那条测试名 → （用例, 判据点号）」—— 绑到**已有**判据点（claim 早写着同一件事）
BIND_EXISTING: dict[str, tuple[str, str]] = {
    "test_台账两侧共用同一个项目选择器且无切换口径": (CASE_LED, "001-05"),
    "test_撤销入口只在生效行且必须填原因": (CASE_LIST, "001-04"),
    "test_流水空态跨列由表头派生且不分页": (CASE_LIST, "001-06"),
}

#: 「测试名 → 新判据点号」（都挂到 `ACC-FLOW-LED-001`）
BIND_NEW: dict[str, str] = {
    "test_台账的现状数_截至行与入口名都钉住": "001-12",
    "test_台账卡头按钮分组与点开有反馈都钉住": "001-13",
    "test_总欠款导出与期初删除都不许静默失败": "001-14",
}

#: 用例索引两行的「来源」栏要补的变更说明
INDEX_NOTES: dict[str, str] = {
    CASE_LED: (
        "；⭐ **2026-09-29** 补判据点 `001-12`…`001-14`：把 `backend/tests/test_wired_m05.py` 里 3 条**早就存在**、"
        "却挂 `@acc()`（= 显式「不绑定」⇒ 四态报表里看不见）的「用户看得见」判据**登记**进来"
        "（台账现状数/表尾正名/入口名/空月压暗 · 卡头按钮分组与点开有反馈 · 两条「点了没反应」的静默失败被挡住），"
        "另把「两侧共用同一个项目选择器」那条绑到**已有**的 `001-05` —— ⛔ 不新写断言、⛔ 不为涨绿数硬绑"
        "（用户 2026-09-29 裁定 `A`）"
    ),
    CASE_LIST: (
        "；⭐ **2026-09-29** 把 `backend/tests/test_wired_m05.py` 里 2 条挂 `@acc()`（= 显式「不绑定」）的判据"
        "绑到**已有**判据点（`001-04` 撤销必填原因 · `001-06` 空态跨列 = 表头列数）⇒ **判据点不涨**，"
        "只是让它们在四态报表里**看得见**（用户 2026-09-29 裁定 `A`）"
    ),
}


def _dump(obj: dict) -> str:
    """基线实测格式（`_doc_tail123.py` / `_doc_tail167.py` 都用 round-trip 逐字节比对实测过，⛔ 别凭记忆改参数）：
    `indent=2` · `ensure_ascii=False` · 每行 CRLF · 末尾**一个** CRLF。"""
    return json.dumps(obj, indent=2, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"


def patch_tests(write: bool) -> list[str]:
    """按**测试名**把那 6 条裸 `@acc()` 换成带判据点的装饰器。→ 报告行。"""
    raw = TESTFILE.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    binds = {**{k: v for k, v in BIND_EXISTING.items()},
             **{k: (CASE_LED, v) for k, v in BIND_NEW.items()}}
    for name, (case, pid) in binds.items():
        defs = [i for i, ln in enumerate(lines) if ln.startswith(f"def {name}(")]
        assert len(defs) == 1, f"{name}：找到 {len(defs)} 个定义（要 1 个）"
        j = defs[0] - 1
        while j >= 0 and not lines[j].strip():
            j -= 1
        assert lines[j].strip() == "@acc()", \
            f"{name}：它上面那行不是裸 `@acc()`（是 {lines[j].strip()!r}）⇒ 别改"
        lines[j] = lines[j].replace("@acc()", f'@acc("{case}", "{pid}")')
        out.append(f"  {name:<44} ⇒ {case}/{pid}")
    if write:
        TESTFILE.write_text(nl.join(lines), encoding="utf-8", newline="")
    return out


def patch_index(write: bool) -> list[str]:
    """给 `用例索引.md` 里两条用例那行的「来源」栏补变更说明（⚠️ 保持原换行风格）。"""
    raw = INDEX.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    for case, note in INDEX_NOTES.items():
        hits = [i for i, ln in enumerate(lines) if ln.startswith(f"| `{case}` |")]
        assert len(hits) == 1, f"用例索引里 `{case}` 命中 {len(hits)} 行（要 1 行）"
        i = hits[0]
        assert note not in lines[i], f"`{case}` 的变更说明已在 ⇒ 本脚本跑过了"
        row = lines[i].rstrip()
        assert row.endswith("|"), f"`{case}` 那行不以 `|` 收尾 ⇒ 表结构变了：{row[-40:]!r}"
        lines[i] = row[:-1].rstrip() + note + " |"
        out.append(f"  用例索引.md `{case}` 行 ⇒ 已补变更说明（{len(note)} 字）")
    if write:
        INDEX.write_text(nl.join(lines), encoding="utf-8", newline="")
    return out


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

    led = obj["cases"][CASE_LED]
    ids = [p["id"] for p in led["points"]]
    assert ids == [f"001-{i:02d}" for i in range(1, len(ids) + 1)], f"编号不顺延：{ids}"
    assert len(ids) == 11, f"`{CASE_LED}` 现有 {len(ids)} 个点（期望 11）⇒ 基线已变，先核再改"
    before = sum(len(v.get("points") or []) for v in obj["cases"].values())
    print(f"现有用例 {len(obj['cases'])} 条 · 判据点合计 {before} · `{CASE_LED}` 现 {len(ids)} 点（{ids[0]}…{ids[-1]}）")

    led["points"].extend({"id": pid, "kind": kind, "claim": claim, "cover": cover}
                         for pid, kind, claim, cover in NEW_POINTS)
    print(f"＋ `{CASE_LED}` 加 {len(NEW_POINTS)} 点（001-12…001-14）")

    print("\n绑定（按测试名）：")
    print("\n".join(patch_tests(args.write)))
    print("\n".join(patch_index(args.write)))

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
