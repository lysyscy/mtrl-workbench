#!/usr/bin/env python
"""`A4`（`m06` 过程资料逐页）· 把 1 条**新写**的守卫登记进契约面（一次性 · 2026-09-29）。

**规矩照旧**：`json.loads` → 改 dict → `json.dumps(indent=2, ensure_ascii=False)` ＋ 每行 CRLF ＋
末尾一个 CRLF；**改前先做 round-trip 逐字节比对**，不等就**拒写**。

**它做什么**：`ACC-UI-SHELL-001` 加 **1 点** `001-54`（注入的工具栏走变体类、⛔ 别在 JS 里重写静态外观）
＋ `用例索引.md` 该行补变更说明。

用法：`… _doc_a4_m06.py --check` / `--write`
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
BACKUP = REPO / ".workbuddy" / "backups" / "交付面-20260929-0930-A4"
CASE = "ACC-UI-SHELL-001"

POINTS = ((
    "001-54", "outcome",
    "**注入的 DOM 不许在 JS 里重写静态外观**：`BIND.m06` / `BIND.m09` 的页首工具栏原把 `.fbar` 的声明"
    "又写一遍、且 `margin-bottom:10px` **漏了 `--fscale`** ⇒ 界面调大时那一处不跟着变（§5.11 半成品相）"
    "⇒ 改走**变体类** `.fbar.plate`（逐像素等价、只差倍率）。判法：`cssText` 里不许出现 `border:` 这类"
    "静态外观；⛔ 定位类（`position:` / `z-index:`）不误伤",
    "守则 §5.11 · §5.9",
),)

COVER_ADD = ("守则 §5.11",)

NOTE = (
    "；⭐ **2026-09-29** 补判据点 `001-54`（`A4` 逐页 · `m06`）：查出**注入面**那两条页首工具栏"
    "（`BIND.m06` / `BIND.m09`）在 JS 里把 `.fbar` 的声明**又写了一遍**、且 `margin-bottom` **漏了 `--fscale`**"
    "⇒ 改走变体类 `.fbar.plate`（逐像素等价）；判据取一般式 =「`cssText` 里不许有静态外观声明，定位类不误伤」。"
    "⛔ 判词对既有 53 点一字未改，只是新增 ＋ 该用例 `cover` 补守则 §5.11"
)


def _dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"


def patch_index(write: bool) -> str:
    raw = INDEX.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")
    hits = [i for i, ln in enumerate(lines) if ln.startswith(f"| `{CASE}` |")]
    assert len(hits) == 1, f"用例索引里 `{CASE}` 命中 {len(hits)} 行"
    i = hits[0]
    assert NOTE not in lines[i], "变更说明已在 ⇒ 本脚本跑过了"
    row = lines[i].rstrip()
    assert row.endswith("|"), "该行不以 `|` 收尾 ⇒ 表结构变了"
    lines[i] = row[:-1].rstrip() + NOTE + " |"
    if write:
        INDEX.write_text(nl.join(lines), encoding="utf-8", newline="")
    return f"  用例索引.md `{CASE}` 行 ⇒ 已补变更说明（{len(NOTE)} 字）"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    raw = BASELINE.read_text(encoding="utf-8", newline="")
    obj = json.loads(raw)
    if _dump(obj) != raw:
        print("round-trip 逐字节比对：⛔ 不一致（⛔ 别写！）")
        return 1
    print("round-trip 逐字节比对：✅ 一致")
    print(f"交付面备份在位：{'✅' if BACKUP.exists() else '⛔ 先备份再改'} {BACKUP}")
    if not BACKUP.exists():
        return 1

    c = obj["cases"][CASE]
    ids = [p["id"] for p in c["points"]]
    assert ids == [f"001-{i:02d}" for i in range(1, len(ids) + 1)], f"编号不顺延：{ids}"
    assert len(ids) == 53, f"`{CASE}` 现有 {len(ids)} 点（期望 53）⇒ 基线已变，先核再改"
    before = sum(len(v.get("points") or []) for v in obj["cases"].values())
    print(f"现有用例 {len(obj['cases'])} 条 · 判据点合计 {before} · `{CASE}` 现 {len(ids)} 点")
    c["points"].extend({"id": p, "kind": k, "claim": cl, "cover": cv} for p, k, cl, cv in POINTS)
    for sec in COVER_ADD:
        if sec not in c["cover"]:
            c["cover"].append(sec)
    print(f"＋ `{CASE}` 加 {len(POINTS)} 点（001-54）")
    print(patch_index(args.write))

    if args.write:
        BASELINE.write_text(_dump(obj), encoding="utf-8", newline="")
        back = json.loads(BASELINE.read_text(encoding="utf-8"))
        after = sum(len(v.get("points") or []) for v in back["cases"].values())
        assert after == before + len(POINTS), f"点数不对：{before} ⇒ {after}"
        print(f"\n✅ 已写回：判据点合计 {before} ⇒ **{after}**")
    else:
        print(f"\n（`--check`：⛔ 未写；写的话 {before} ⇒ {before + len(POINTS)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
