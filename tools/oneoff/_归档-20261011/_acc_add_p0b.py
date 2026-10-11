"""一次性：`P0-b` 把 13 条**页级**判据点登记进 `ACC-UI-SHELL-001`（交付面 · `验收基线.json`）。

⭐ 口径（用户 2026-09-28 回「A」）：**登记既有判据**（照 `TAIL-123` 的做法），⛔ 不新写判据、
   ⛔ 不为涨绿数硬绑 —— 新写的只有 `set` 页那 3 条（它们此前**没有任何判据**盯着）。

⛔ JSON 绝不文本替换（`MEMORY.md §四` 坑 1）：`json.loads` → 改 dict → `json.dumps(indent=2, ensure_ascii=False)`
   并把 `\n` 还原成 `\r\n`（该件实测格式）⇒ 先做 **round-trip 逐字节比对**，不等就**拒绝写**。
   读它做比对必须 `read_text(newline="")`（否则 universal newlines 把 CRLF 折成 LF ⇒ 假差异）。

用法：`python tools/oneoff/_acc_add_p0b.py --check`（dry-run：只做 round-trip 校验与预览）
      `python tools/oneoff/_acc_add_p0b.py`（真写：**先备份交付面**，再改 `验收基线.json`）
⚠️ **不回读**（`tools/oneoff/` 的惯例）；实跑于 2026-09-28（`TAIL-147` · `P0-b` 页级判据登记）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
from pathlib import Path

ROOT = Path(r"D:\dev\mtrl-workbench")
FACE = Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用")
BASELINE = FACE / "PRD" / "验收" / "验收基线.json"
INDEX = FACE / "PRD" / "验收" / "用例索引.md"

CASE = "ACC-UI-SHELL-001"
NEW_SOURCE = ("守则驱动的**既有**机器判据（离线 10 件：`backend/tests/test_ux_errors.py` · `test_ux_feedback.py` · "
              "`test_ux_text.py` · `test_ux_brief.py` · `test_ux_states.py` · `test_ux_colors.py` · "
              "`test_ux_buttons.py` · `test_ux_numbers.py` · `test_ux_deadcode.py` · `test_ux_pages.py` "
              "＋ `test_imp_shell.py`（页级登记））＋ 真机段 ㉔/㉕/㉖/㉗/㉙（`tools/probe/_shell_*`）")

NEW_POINTS: list[tuple[str, str, str]] = [
    ("001-37", "系统设置页不再摆连接参数（旧「整页交全部键」写法不许回来），且通往「i8 接入层」「付款通知书」的指路卡两条都在", "守则 §5.8"),
    ("001-38", "系统设置页只剩三张卡：外观主题 / 界面大小 / 变更留痕", "守则 §5.9"),
    ("001-39", "搬走的三个连接参数入口真的在那边（`i8 连接设置` 动作 ＋ 两个打印版式 ID 字段）", "守则 §5.8"),
    ("001-40", "数据导入页：面板三件是全局共用件（写成 `IMP.` 的方法 ⇒ 点下去才报错）", "守则 §5.5"),
    ("001-41", "数据导入页：范围栏画在第 ① 步，且没选项目不许落库", "守则 §4.3"),
    ("001-42", "数据导入页：项目候选与选完之后的名字只走一个出口", "守则 §4.7"),
    ("001-43", "数据导入页：落库结果卡给人话，原始键名进「技术明细」", "守则 §5.8"),
    ("001-44", "数据导入页：不会落库的行在行上直接标（⛔ 不是只在卡片底下写一句总数）", "守则 §2.7"),
    ("001-45", "数据导入页：截止核算月写清格式要求（`YYYY-MM`）", "守则 §2.4"),
    ("001-46", "数据导入页：落库期间不许重复提交（按钮禁用）", "守则 §5.5"),
    ("001-47", "数据导入页：列映射的「去向」只许三个词，字段清单要列全", "守则 §5.9"),
    ("001-48", "数据导入页：预览的行能对得上号（不静默截断、不藏行号）", "守则 §2.6"),
    ("001-49", "数据导入页：截止核算月要说清它是什么，不只给一个名字", "守则 §2.5"),
]


def load_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", newline="")          # ⚠️ newline="" ⇒ 保住 CRLF


def dumps_crlf(obj) -> str:
    # ⚠️ 实测格式 = `indent=2` ＋ CRLF ＋ **末尾一个 CRLF**（少了它 round-trip 差 2 字节）
    return json.dumps(obj, ensure_ascii=False, indent=2).replace("\n", "\r\n") + "\r\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="dry-run：只做 round-trip 校验与预览")
    args = ap.parse_args()

    text = load_text(BASELINE)
    obj = json.loads(text)
    for ind in (1, 2, 4):
        for rep in ("\n", "\r\n"):
            s = json.dumps(obj, ensure_ascii=False, indent=ind).replace("\n", rep)
            print(f"  indent={ind} newline={rep!r}  len {len(s)} vs {len(text)}  equal={s == text}")
    s = dumps_crlf(obj)
    if s != text:
        print("⛔ round-trip 不等 ⇒ 本件格式假设有误，拒绝继续（先核 indent / 换行 / 结尾）")
        for i, (a, b) in enumerate(zip(s, text)):
            if a != b:
                print(f"  first diff @ {i}")
                print("  new:", repr(s[max(0, i - 80):i + 80]))
                print("  old:", repr(text[max(0, i - 80):i + 80]))
                break
        else:
            print(f"  前缀一致，长度不同（{len(s)} vs {len(text)}）")
            print("  old tail:", repr(text[-80:]))
            print("  new tail:", repr(s[-80:]))
        return 1
    print("✅ round-trip 逐字节一致（indent=2 · CRLF · 末尾一个 CRLF）")

    case = obj["cases"][CASE]
    have = [p["id"] for p in case["points"]]
    print(f"现有判据点 {len(have)} 条（{have[0]} … {have[-1]}）")
    plan = [pid for pid, _, _ in NEW_POINTS]
    assert not (set(plan) & set(have)), f"这些号已经存在：{sorted(set(plan) & set(have))}"
    print(f"将新增 {len(NEW_POINTS)} 条：{plan[0]} … {plan[-1]} ⇒ 合计 {len(have) + len(NEW_POINTS)}")

    if args.check:
        print("（dry-run：未写）")
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bk = ROOT / ".workbuddy" / "backups" / f"_归档-交付面-验收-{stamp}"
    bk.mkdir(parents=True, exist_ok=True)
    for f in (BASELINE, INDEX):
        shutil.copy2(f, bk / f.name)
    print(f"已备份 → {bk}")

    for pid, claim, cover in NEW_POINTS:
        case["points"].append({"id": pid, "kind": "outcome", "claim": claim, "cover": cover})
    case["source"] = NEW_SOURCE
    BASELINE.write_text(dumps_crlf(obj), encoding="utf-8", newline="")
    print("✅ 已写 验收基线.json")

    # ---- 用例索引：把那一行的说明改成现状（⛔ 只改说明文字，不动编号/定义）----
    itext = load_text(INDEX)
    old_line = [ln for ln in itext.split("\r\n") if ln.startswith(f"| `{CASE}` |")]
    assert len(old_line) == 1, f"用例索引里这一行不唯一：{len(old_line)}"
    print("原行（摘要）：", old_line[0][:120], "…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
