r"""`TAIL-234` 修复脚本 · **堆1b「页脚孤儿行归位」**（幂等 · 可复跑 · `--write` 才落盘）。

**病**：`PRD/02-功能规格/MOD-14.md` 的两条 §四 验收清单条目（`ACC-CFG-SETUP-001` ·
`ACC-JC-IGNORE-001`）**掉到了文件页脚之后** ⇒ 渲染出来是落款下面的孤行。

**处置**：**纯挪位，一字不改**（脚本整行搬运，不重写内容 ⇒「一字不改」由构造保证）。

⚠️⚠️ **锚点自己重选 —— 别照抄 `TAIL-232` 那个子串锚**（它锚的是
  `· 版式 ID 反直觉提示`，也就是**页脚后那一行本身**）⇒ **那正是当初把行加错位置的根因**：
  锚点必须落在**它该去的那一段里**（§四 的 `ACC-*` 清单末尾），⛔ 不能锚在"要搬的那一行"上。

**锚点** = §四 清单里**最后一条 `ACC-*` 行**（`ACC-X-DEL-001`），插在它**之后**、ℹ️ 那行**之前**。

⛔ 本脚本**只碰这一件**。同批的另两堆（`MOD-06`/`MOD-11`/`MOD-14` 能力表漏引用、用例索引漏登）
   不在此处 —— 前者是交付面回退的病（等网立起来再处置），后者 `TAIL-232` 已办。

用法：`python _tail234_fix.py`（默认干跑）/ `--write`（真写）
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools" / "audit"))
from audit_common import FOOTER_MARKER, delivery_root  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
FACE = delivery_root()
TARGET_REL = "PRD/02-功能规格/MOD-14.md"
#: ⚠️ **备份目录名 = `交付面-<日期>-<时分>`**（`README.md §四`「交付面改前备份」那一行的写法；本轮实测
#: `/code-review` 指出我漏了时分）。⚠️ **改名必须与本常量同批** —— 否则脚本会 `mkdir` 另建一个目录
#: ⇒ 备份分叉两处、而谁也不知道另一个在哪（"同一件事两处写"那族）。
BACKUP_DIR = ROOT / ".codebuddy" / "backups" / "交付面-2026-10-06-1911"
LEDGER = BACKUP_DIR / "_MD5-改后.tsv"

#: 要归位的两行 ——只认**行首前缀**（`ACC` 号），⛔ 不硬编码整行：搬运时按原样取，**一字不改**。
ORPHAN_PREFIXES: tuple[str, ...] = (
    "- `ACC-CFG-SETUP-001` —— ",
    "- `ACC-JC-IGNORE-001` —— ",
)
#: §四 清单的锚 = **最后一条 `ACC-*` 行**（⛔ 不是"要搬的那两行"里的任何一行 —— 见文件头）
ACC_ITEM = "- `ACC-"
ANCHOR_ACC = "ACC-X-DEL-001"
#: ℹ️ 那一行 = 清单的**收尾**（插在锚之后、它之前 ⇒ 两条 `ACC-*` 仍在清单段内）
NOTE_PREFIX = "- ℹ️ "


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="真写（默认干跑）")
    args = ap.parse_args()
    assert FACE and FACE.is_dir(), f"交付面根拿不到：{FACE}"
    path = FACE / TARGET_REL
    raw = path.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")

    foot = [i for i, ln in enumerate(lines) if ln.startswith(FOOTER_MARKER)]
    assert len(foot) == 1, f"页脚标记 {len(foot)} 处（要 1 处）—— ⛔ 先核原文"
    foot = foot[0]
    anchor = [i for i, ln in enumerate(lines) if ln.startswith(ACC_ITEM) and ANCHOR_ACC in ln]
    assert len(anchor) == 1, f"锚行（{ANCHOR_ACC}）{len(anchor)} 处 —— ⛔ 先核原文"
    anchor = anchor[0]
    assert anchor < foot, "锚行不在页脚之前 ⇒ §四 结构变了，先核原文"
    notes = [f"{TARGET_REL} · 页脚在第 {foot + 1} 行 · 锚行（{ANCHOR_ACC}）在第 {anchor + 1} 行"]

    moves: list[str] = []
    for pref in ORPHAN_PREFIXES:
        hits = [i for i, ln in enumerate(lines) if ln.startswith(pref)]
        assert len(hits) == 1, f"`{pref}` 命中 {len(hits)} 行（要 1 行）—— ⛔ 先核原文"
        i = hits[0]
        if i < foot:
            notes.append(f"{pref[:14]}… 已在页脚之前 ⇒ 跳过（幂等）")
            continue
        assert i > foot, f"{pref[:14]}… 既不在页脚前也不在页脚后 —— 先核原文"
        moves.append(f"{i + 1} → {anchor + 1 + len(moves) + 1}（{pref[:14]}…，一字不改）")
    lines = _apply(lines)
    new = nl.join(lines)
    note = next((i for i, ln in enumerate(lines) if ln.startswith(NOTE_PREFIX)), None)
    if note is not None:
        last_item = max(i for i, ln in enumerate(lines) if ln.startswith(ORPHAN_PREFIXES))
        assert last_item < note, "归位后落到 ℹ️ 那行**之后**了 ⇒ 仍在清单段外，先核原文"

    # 有意义的不变式：① 页脚之后**不再有非空行**（这正是网② 的判据，提前在这里断言一次）
    #② 多重集差 = 纯挪位（删的与加的是同一批行、一字不差）
    # ⚠️ **页脚行号必须在改后的行表上重算** —— 挪位把它往后顶了两行（拿改前的下标切 ⇒ 切出来的
    #   第一行就是页脚自己，本脚本第一版就这样自己撞上了：断言报错救了一次写坏的机会）。
    new_lines = new.replace("\r\n", "\n").split("\n")
    f2 = [i for i, ln in enumerate(new_lines) if ln.startswith(FOOTER_MARKER)]
    assert len(f2) == 1, f"改后页脚标记 {len(f2)} 处 —— ⛔ 先核原文"
    tail = [ln for ln in new_lines[f2[0] + 1:] if ln.strip()]
    assert not tail, f"页脚之后还有非空行：{tail[:1]} —— ⛔ 拒绝写"
    assert sorted(lines) == sorted(raw.replace("\r\n", "\n").split("\n")), "改动不只是挪位（行集合变了）"
    for m in moves:
        notes.append("归位 " + m)

    print("判定：")
    for n in notes:
        print(f"  {n}")
    if new == raw:
        print("\n（已是归位后的形态 ⇒ 无事可做 · 幂等）")
        return 0
    if not args.write:
        print(f"\n（干跑：{TARGET_REL} 会有变化；跑 `--write` 才落盘）")
        return 0

    assert "\ufffd" not in new, "文本里有 U+FFFD ⇒ ⛔ 拒绝写"
    before = hashlib.md5(path.read_bytes()).hexdigest()
    path.write_text(new, encoding="utf-8", newline="")
    back = path.read_bytes()
    assert back == new.encode("utf-8"), "写回与预期不一致"
    assert "\ufffd" not in back.decode("utf-8"), "写回后有 U+FFFD ⇒ ⛔ 已写坏"
    after = hashlib.md5(back).hexdigest()
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{TARGET_REL}\t{before}\t{after}\n")
    print(f"\n已落盘 {TARGET_REL}\n  MD5 {before} → {after}\n  对账追加 = {LEDGER}")
    return 0


def _apply(lines: list[str]) -> list[str]:
    """把页脚之后那两条搬到锚行之后（**按原样搬运**），返回新行表。

    ⚠️ **锚点在这里重算**（⛔ 别信调用方传进来的下标：挪位会把它顶掉 —— 当天第一版就是把
    `foot`/`anchor` 当参数传进来、结果内部又算一遍，两处算同一件事）。
    """
    out = [ln for ln in lines]
    picked = [ln for ln in out if ln.startswith(ORPHAN_PREFIXES)]
    assert len(picked) == len(ORPHAN_PREFIXES), "孤儿行数对不上"
    out = [ln for ln in out if not ln.startswith(ORPHAN_PREFIXES)]
    at = next(i for i, ln in enumerate(out) if ln.startswith(ACC_ITEM) and ANCHOR_ACC in ln)
    for k, ln in enumerate(picked):
        out.insert(at + 1 + k, ln)
    assert len(out) == len(lines), "挪位不该改行数"
    return out


if __name__ == "__main__":
    raise SystemExit(main())