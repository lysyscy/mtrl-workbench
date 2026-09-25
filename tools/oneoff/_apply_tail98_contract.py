"""一次性件（`TAIL-98` · 2026-09-25）：**契约面同批** —— 集采导入的**整批回滚 ＋ 覆盖语义**。

四处（缺一件就还是分叉）：
  ① 《说明书》**新建 §6.10**「台账 Excel 导入与整批回滚」（口径主人 —— 用户 2026-09-25 要求把
     **覆盖语义写进界面**，它的**出处**必须在这一节）；
  ② `MOD-11.md` 能力表 **#14**；
  ③ `验收基线.json`：`ACC-JC-IMPORT-001` 补 **`001-05`~`001-07`**（回滚还原 / 回执带批次号 / 文案在位）
     ＋ 该用例的 `cover` 补 `§6.10`；
  ④ 两份活文档的**判据点计数** 564 → **567**（`T4` 的四处锚）。

用法：
  `backend/.venv/Scripts/python.exe tools/oneoff/_apply_tail98_contract.py`          # 只报不写
  `backend/.venv/Scripts/python.exe tools/oneoff/_apply_tail98_contract.py --apply`  # 真写
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FACE = Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用")
DOC = FACE / "材料科业务全流程说明书.md"
MOD11 = FACE / "PRD" / "02-功能规格" / "MOD-11.md"
BASE = FACE / "PRD" / "验收" / "验收基线.json"
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
HAND = ROOT / ".workbuddy" / "plans" / "执行情况-主文档.md"
BACKUPS = ROOT / ".workbuddy" / "backups"

SECTION = """### 6.10 台账 Excel 导入与整批回滚

> ⚠️ **本节的「覆盖语义」是用户 2026-09-25 明确要求写进界面的**（原话：「界面没说清哪些列会被覆盖 ⇒ 易误操作」）。

**导入做什么**：把科室**原来的台账 Excel** 导进来**补信息**（流程 = **先抓 i8**（合同已在库里）→ **再导 Excel**）。
⭐ **锚点 = 含税合同价**，范围 = **单个项目内**：命中 **1** 条 ⇒ **更新那一条**；
命中 **0 条 / ≥2 条** ⇒ 列进「配不上」/「同价冲突」并报出来（⛔ **不静默新增、不猜**）。

**覆盖语义（导入前必读 · 界面必须写明）**：

| 类别 | 列 | 会被覆盖吗 |
|---|---|---|
| **Excel 的地盘（只动这 6 列）** | 材料名 · 付款方式 · 备注 · 存档情况 · 存档号 · 寄回日期 | ✅ **会被更新** |
| **i8 的事实列** | 合同价 · 供应商 · 合同日期 · 甲方单位 | ⛔ **一个字都不会被覆盖** |
| **系统自动算** | 结算金额 · 欠款金额 | ⛔ 不落库（现场算） |

> ⭐ **两边互不覆盖**：Excel 只动它自己的那 6 列；i8 抓取也**不碰**这 6 列。
> ⚠️ **发票金额 / 贸易公司发票金额**会往发票子表补一条；**同一合同已有同 kind 的发票行 ⇒ 跳过并报出来**（再导一次不会翻倍）。
> ⛔ **付款列不导**（它是派生的，导它会计重）。

**整批回滚**：

- 每次导入生成一个**批次号**（形如 `JC-YYYYMMDDHHMMSS`），**随回执带出来** ⇒ 界面上出现「**整批回滚**」；
- 回滚 = 那 **6 列逐列还原到导入前** ＋ **摘掉本批新加的汇总发票行**；批次置「**已回滚**」（⛔ 不物理删）；
- ⛔ **一个批次只许回滚一次**（第二遍会把"回滚后的值"再改一次）；
- ⚠️ 若某条在**导入之后又被人工改过** ⇒ **照还原，但必须逐条报出来**（⛔ 禁静默抹掉人工的改动）。

---

"""

MOD11_ROW = ("| 14 | ⭐ **台账 Excel 导入 ＋ 整批回滚**（锚点 = **合同价** · 只更 **6 列** · "
             "**i8 的事实列不碰** · 回执带**批次号**（`JC-…`）⇒ 可**整批回滚**） | §6.10 | `REQ-R9` | "
             "`ACC-JC-IMPORT-001` |\n")

CASE = "ACC-JC-IMPORT-001"
NEW_POINTS = [
    {"id": "001-05", "kind": "outcome",
     "claim": ("⭐ **整批回滚**：导入后回滚 ⇒ 那 **6 列逐列回到导入前**（＋ 本批**新加**的汇总发票行"
               "被摘掉）；批次置「已回滚」、⛔ **不重复回滚**（第二遍会把回滚后的值再改一次）"),
     "cover": "§6.10"},
    {"id": "001-06", "kind": "outcome",
     "claim": ("**回执带批次号**（形如 `JC-YYYYMMDDHHMMSS`）—— ⭐ 界面上的「整批回滚」按钮"
               "**只认回执有没有 `batch`**（通用面已就绪；域不给 ⇒ 就没有按钮）"),
     "cover": "§6.10"},
    {"id": "001-07", "kind": "outcome",
     "claim": ("**覆盖语义必须写在导入页上**（⛔ 不是口头约定）：**只动这 6 列**（材料名 / 付款方式 / 备注 / "
               "存档情况 / 存档号 / 寄回日期），**i8 的列（合同价 / 供应商 / 合同日期 / 甲方单位）不会被覆盖**"
               " —— 依据 = 用户 2026-09-25「界面没说清哪些列会被覆盖 ⇒ 易误操作」"),
     "cover": "§6.10"},
]


def _sub(text: str, old: str, new: str, where: str, n: int = 1) -> str:
    got = text.count(old)
    assert got == n, f"{where}：命中 {got} 次（期望 {n}）—— ⛔ 先核对原文"
    return text.replace(old, new, n)


def _load(p: Path) -> tuple[str, bool]:
    raw = p.read_bytes()
    crlf = b"\r\n" in raw
    t = raw.decode("utf-8").replace("\r\n", "\n")
    assert (t.replace("\n", "\r\n") if crlf else t).encode("utf-8") == raw, f"{p.name}：行尾 round-trip 不一致"
    return t, crlf


def main() -> int:
    apply = "--apply" in sys.argv
    errs: list[str] = []
    out: dict[Path, str] = {}
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    for path, edits in (
        (DOC, [("新建 §6.10（插在第 7 章之前）",
                "\n---\n\n## 第 7 章",
                "\n" + SECTION + "## 第 7 章")]),
        (MOD11, [("能力表 ＋ 第 14 行",
                  "| 13 | 手工新增合同行（**默认「纳入台账」**，与抓取行一致） | §6.5.3 | — | `ACC-JC-UI-001` |\n",
                  "| 13 | 手工新增合同行（**默认「纳入台账」**，与抓取行一致） | §6.5.3 | — | `ACC-JC-UI-001` |\n"
                  + MOD11_ROW)]),
    ):
        try:
            t, crlf = _load(path)
            for desc, old, new in edits:
                t = _sub(t, old, new, f"{path.name}｜{desc}")
            out[path] = t.replace("\n", "\r\n") if crlf else t
        except AssertionError as exc:
            errs.append(str(exc))

    # ── 验收基线（结构操作）
    try:
        raw = BASE.read_bytes()
        data = json.loads(raw.decode("utf-8"))
        assert (json.dumps(data, indent=1, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"
                ).encode("utf-8") == raw, "验收基线 round-trip 不一致 ⇒ ⛔ 序列化参数变了"
        case = data["cases"][CASE]
        ids = [p["id"] for p in case["points"]]
        assert ids == [f"001-{i:02d}" for i in range(1, len(ids) + 1)], f"编号不顺延：{ids}"
        for p in NEW_POINTS:
            assert p["id"] not in ids, f"{p['id']} 已在册（幂等）"
        before = sum(len(c.get("points") or []) for c in data["cases"].values())
        case["points"].extend(NEW_POINTS)
        if "§6.10" not in case["cover"]:
            case["cover"].append("§6.10")
        case["criterion"] += ("⭐ `TAIL-98`（2026-09-25）补：**整批回滚**（那 6 列逐列还原 ＋ "
                              "摘掉本批新加的发票行）＋ **覆盖语义文案写在导入页上**。")
        case["source"] += "；⭐ 2026-09-25（`TAIL-98`）：补 `001-05`~`001-07`（整批回滚 ＋ 覆盖语义文案）"
        data["asof"] = date.today().isoformat()
        after = sum(len(c.get("points") or []) for c in data["cases"].values())
        assert after == before + 3, f"判据点应 +3：{before} → {after}"
        out[BASE] = json.dumps(data, indent=1, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"
    except AssertionError as exc:
        errs.append(str(exc))

    # ── 计数 564 → 567（T4 的四处锚）
    for path, edits in (
        (PLAN, [("§0.2", "**564 = 绿 564 · 红 0 · 待建   0 · 未绑定    0**", "**567 = 绿 567 · 红 0 · 待建   0 · 未绑定    0**"),
                ("§22.1", "- ⭐ **四态零丢失的基线（2026-09-25）：564 = 绿 564 · 红 0 · 待建 0 · 未绑定 0**",
                 "- ⭐ **四态零丢失的基线（2026-09-25）：567 = 绿 567 · 红 0 · 待建 0 · 未绑定 0**"),
                ("§22.2", "| ⭐ **564 = 绿 564 · 红 0 · 待建 0 · 未绑定 0**（2026-09-25） |",
                 "| ⭐ **567 = 绿 567 · 红 0 · 待建 0 · 未绑定 0**（2026-09-25） |")]),
        (HAND, [("顶部总账", "**564 = 绿 564 · 红 0 · 待建 0 · 未绑定 0**", "**567 = 绿 567 · 红 0 · 待建 0 · 未绑定 0**")]),
    ):
        try:
            t, crlf = _load(path)
            for desc, old, new in edits:
                t = _sub(t, old, new, f"{path.name}｜{desc}")
            out[path] = t.replace("\n", "\r\n") if crlf else t
        except AssertionError as exc:
            errs.append(str(exc))

    print("=" * 80)
    print(("  写入" if apply else "  DRY-RUN（只报不写）") + " ·  TAIL-98 契约面")
    print("=" * 80)
    for p in out:
        print(f"  {p.name}")
    print(f"  {CASE}：+3 点（001-05~001-07）· 判据点 564 → 567")
    if errs:
        print("\n⛔ 有断言没过 ⇒ **一个字节都没写**：")
        for e in errs:
            print("   " + e)
        return 1
    if not apply:
        print("\n  （加 --apply 才真写。）")
        return 0
    BACKUPS.mkdir(parents=True, exist_ok=True)
    for p, t in out.items():
        if FACE in p.parents:
            shutil.copy2(p, BACKUPS / f"face-{stamp}-{p.name}")
        p.write_bytes(t.encode("utf-8"))
    print("\n  ✅ 已写盘 ＋ 交付面三件已备份。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
