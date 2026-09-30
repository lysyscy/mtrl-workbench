"""一次性件（`TAIL-101` · 2026-09-25）：给**集采「不纳入名单」**补契约面。

**为什么**（`TAIL-96` 的遗留）：那条能力**全链早就落地**（表 / 过滤点 / 留痕 / API / M14 维护卡 / 真机判据 ⑫c），
但它**没进契约面** —— 《说明书》§6 里查不到、`MOD-14.md` 没有这一行、`验收基线.json` 里没有用例
（全库搜「剔除名单」/`jc-ignore` ⇒ 交付面 **0 命中**）⇒ **用户可见、却没有口径主人、也没有判据**。

本件做四件事（缺一件就还是分叉）：
  ① 《说明书》**新建 §6.5.4**「不纳入名单」（口径主人）；
  ② `MOD-14.md` 能力表 ＋ 一行（页面在 `MOD-14`）；
  ③ `验收基线.json` 新建用例 `ACC-JC-IGNORE-001`（**4 点**，判据早已在 `backend/tests/test_jc_ignore.py`）；
  ④ 两份活文档的**判据点计数** 560 → **564**（`T4` 的四处锚，一处不改就红）。

⚠️ `.json` 走**结构操作** ＋ 先 `round-trip`（实测参数 = `indent=1` · `ensure_ascii=False` · CRLF · 末尾一个 CRLF）。

用法：
  `backend/.venv/Scripts/python.exe tools/oneoff/_acc_add_jcignore.py`          # 只报不写
  `backend/.venv/Scripts/python.exe tools/oneoff/_acc_add_jcignore.py --apply`  # 真写
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
MOD14 = FACE / "PRD" / "02-功能规格" / "MOD-14.md"
BASE = FACE / "PRD" / "验收" / "验收基线.json"
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
HAND = ROOT / ".workbuddy" / "plans" / "执行情况-主文档.md"
BACKUPS = ROOT / ".workbuddy" / "backups"

SECTION = """#### 6.5.4 不纳入名单（集采侧 · 系统配置）

抓回来的集采合同里，有一部分是**这个项目根本不要**的（废数据 / 与本域无关 / 项目已废弃）。
⭐ 集采侧照付款侧（§4.2.2）的思路做一份**「不纳入名单」**：**按「项目全名」登记**，命中即**在抓取时直接剔除**。

| 项 | 口径 |
|---|---|
| **登记粒度** | **项目**（按**全名**）—— "这个项目的合同我一概不要"，⛔ 不是逐张合同挑 |
| **命中后的行为** | 该项目的合同**既不落库、也不再进「未落库」清单**（它是"**不要**"，不是"还没走完"） |
| **必须留痕** | 抓取回执列明**已剔除 N 条**（按项目分组）＋ 执行记录留清单 —— ⛔ **禁静默**（否则"抓回来怎么少了"说不清） |
| **停用 = 留在册** | 停用后**不再参与过滤**，但**记录留在册**、可随时**复活**（⛔ 不做物理删 —— 要能回答"这条为什么没了"） |
| **重复登记** | **同名幂等**：同名再登记 ⇒ **复用**那一条（⛔ 不重复插）；原先停用的 ⇒ **复活** |
| **维护入口** | 「规则配置」页（与付款侧的剔除规则**并列**） |
| ⛔ **与付款侧不共用** | **付款一份、集采一份，各管各的** —— 在付款侧登记不影响集采，反之亦然 |

> ⚠️ **与「不纳入」两态（§6.5.3）的分工**：名单是**抓取前**的**项目级**过滤（**压根不进来**）；
> 「不纳入」是**已经落库的合同**的**逐条**标记（**进来了、但不算它的账**）。
> ⇒ 前者的效果是"回执里看不见"，后者是"台账里看得见、只是不计入欠款 / 主材累计"。

> ⛔ **名单不许放宽任何判定**：命中名单只影响"**哪些行参与匹配**"，**不改变**归属判定本身 ——
> 未建档 / 壳全名归不下去的行，**该不落库还是不落库**（防"有名单就放行"）。

---

"""

MOD14_ROW = ("| 11 | ⭐ **集采「不纳入名单」**（**集采侧独立一份**，⛔ 与付款侧的剔除规则**不共用**；"
             "按**项目全名**登记 ⇒ 抓取时**先剔除**：既不落库、也不进「未落库」清单；**必须留痕**；"
             "停用**留在册**可复活） | §6.5.4 | `REQ-R10` | `ACC-JC-IGNORE-001` |\n")

MOD14_VERIFY = ("- `ACC-JC-IGNORE-001` —— 集采不纳入名单：命中即剔除 / 名单空逐字节一致 / "
                "⛔ 不许放宽归属判定 / 同名幂等＋停用留册\n")

CASE = "ACC-JC-IGNORE-001"
CASE_BODY = {
    "req": "REQ-R10",
    "module": "MOD-11 · MOD-14（页面在「规则配置」、数据主人在集采域 —— 与付款侧「剔除规则」同构）",
    "cover": ["§6.5.4"],
    "source": ("**需新建**（2026-09-25 `TAIL-101`：`TAIL-96` 把这条能力**全链做完了**，"
               "但**契约面没跟** —— 判据早已在 `backend/tests/test_jc_ignore.py` 里，"
               "只是**没登记**（当时用 `@acc()` 自检））"),
    "criterion": ("集采侧有一份**独立的**「不纳入名单」（按**项目全名**登记）：命中的项目 ⇒ 抓取时"
                  "**既不落库、也不再进「未落库」清单**，且**必须留痕**；名单为空时与加名单之前"
                  "**行为逐字节一致**；⛔ 名单**不许放宽**归属判定；⛔ 与付款侧**不共用**"),
    "points": [
        {"id": "001-01", "kind": "outcome",
         "claim": "命中名单的项目 ⇒ 其合同在抓取时**被摘出**（既不落库、也不进「未落库」清单），"
                  "且**未命中的行一行不动**（⛔ 不连坐）",
         "cover": "§6.5.4"},
        {"id": "001-02", "kind": "outcome",
         "claim": "**名单为空 ⇒ 与加名单之前逐字节一致**（含**行序** —— 防回归）",
         "cover": "§6.5.4"},
        {"id": "001-03", "kind": "outcome",
         "claim": "⭐ **反例**：名单**不许**让「归属未走完」的行变得可落库（**有名单 ≠ 放行**）",
         "cover": "§6.5.4"},
        {"id": "001-04", "kind": "outcome",
         "claim": "名单写入**同名幂等**（同名 ⇒ 复用，⛔ 不重复插）＋ **停用后不再参与过滤但仍留在册**（可复活）",
         "cover": "§6.5.4"},
    ],
}


def _sub(text: str, old: str, new: str, where: str, n: int = 1) -> str:
    got = text.count(old)
    assert got == n, f"{where}：命中 {got} 次（期望 {n}）—— ⛔ 先核对原文"
    return text.replace(old, new, n)


def main() -> int:
    apply = "--apply" in sys.argv
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    errs: list[str] = []
    texts: dict[Path, str] = {}

    # ── 交付面：说明书 ＋ MOD-14（文本件）
    for path, edits in (
        (DOC, [
            ("新建 §6.5.4（插在 §6.6 之前）",
             "\n---\n\n### 6.6 场景二：付款引用与实际供应商",
             "\n" + SECTION + "### 6.6 场景二：付款引用与实际供应商"),
            ("§6.5.3 里那句指向新节（免得读的人找不到）",
             "不要的项目改用**集采剔除名单**（抓取时直接剔除、不落库）来管",
             "不要的项目改用**集采「不纳入名单」**（抓取时直接剔除、不落库，见 §6.5.4）来管"),
        ]),
        (MOD14, [
            ("能力表 ＋ 第 11 行",
             "| 10 | **i8 四个接口路径由「服务地址」＋ 常量路径推导**（不得各存一份） | §7.8 | — | `ACC-CFG-SETUP-001` |\n",
             "| 10 | **i8 四个接口路径由「服务地址」＋ 常量路径推导**（不得各存一份） | §7.8 | — | `ACC-CFG-SETUP-001` |\n"
             + MOD14_ROW),
            ("§四 验收清单 ＋ 一行（⚠️ 用**短锚**：那行是文件最后一行、措辞/空白不稳，长串锚命中 0）",
             "· 版式 ID 反直觉提示",
             "· 版式 ID 反直觉提示\n" + MOD14_VERIFY.rstrip("\n")),
        ]),
    ):
        raw = path.read_bytes()
        crlf = b"\r\n" in raw
        t = raw.decode("utf-8").replace("\r\n", "\n")
        if (t.replace("\n", "\r\n") if crlf else t).encode("utf-8") != raw:
            errs.append(f"{path.name}：行尾 round-trip 不一致")
            continue
        for desc, old, new in edits:
            try:
                t = _sub(t, old, new, f"{path.name}｜{desc}")
            except AssertionError as exc:
                errs.append(str(exc))
        texts[path] = t.replace("\n", "\r\n") if crlf else t

    # ── 验收基线（结构操作）
    base_raw = BASE.read_bytes()
    data = json.loads(base_raw.decode("utf-8"))
    base_out = json.dumps(data, indent=1, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"
    if base_out.encode("utf-8") != base_raw:
        errs.append("验收基线 round-trip 不一致 ⇒ ⛔ 序列化参数变了")
    else:
        assert CASE not in data["cases"], f"{CASE} 已经在册"
        before = sum(len(c.get("points") or []) for c in data["cases"].values())
        data["cases"][CASE] = CASE_BODY
        data["asof"] = date.today().isoformat()
        after = sum(len(c.get("points") or []) for c in data["cases"].values())
        assert after == before + 4, f"判据点应 +4：{before} → {after}"
        texts[BASE] = json.dumps(data, indent=1, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"

    # ── 两份活文档：判据点计数 560 → 564（T4 的四处锚）
    for path, edits in (
        (PLAN, [
            ("§0.2", "**560 = 绿 560 · 红 0 · 待建   0 · 未绑定    0**", "**564 = 绿 564 · 红 0 · 待建   0 · 未绑定    0**"),
            ("§22.1", "- ⭐ **四态零丢失的基线（2026-09-25）：560 = 绿 560 · 红 0 · 待建 0 · 未绑定 0**",
             "- ⭐ **四态零丢失的基线（2026-09-25）：564 = 绿 564 · 红 0 · 待建 0 · 未绑定 0**"),
            ("§22.2", "| ⭐ **560 = 绿 560 · 红 0 · 待建 0 · 未绑定 0**（2026-09-25） |",
             "| ⭐ **564 = 绿 564 · 红 0 · 待建 0 · 未绑定 0**（2026-09-25） |"),
        ]),
        (HAND, [("顶部总账", "**560 = 绿 560 · 红 0 · 待建 0 · 未绑定 0**", "**564 = 绿 564 · 红 0 · 待建 0 · 未绑定 0**")]),
    ):
        raw = path.read_bytes()
        crlf = b"\r\n" in raw
        t = raw.decode("utf-8").replace("\r\n", "\n")
        for desc, old, new in edits:
            try:
                t = _sub(t, old, new, f"{path.name}｜{desc}")
            except AssertionError as exc:
                errs.append(str(exc))
        texts[path] = t.replace("\n", "\r\n") if crlf else t

    print("=" * 80)
    print(("  写入" if apply else "  DRY-RUN（只报不写）") + " ·  TAIL-101 集采「不纳入名单」补契约面")
    print("=" * 80)
    for p in texts:
        print(f"  {p.name}")
    print("  验收基线：+" + CASE + "（4 点）· 判据点 560 → 564")
    if errs:
        print("\n⛔ 有断言没过 ⇒ **一个字节都没写**：")
        for e in errs:
            print("   " + e)
        return 1
    if not apply:
        print("\n  （加 --apply 才真写；交付面三件改前自动备份。）")
        return 0

    BACKUPS.mkdir(parents=True, exist_ok=True)
    for p, t in texts.items():
        if FACE in p.parents:
            shutil.copy2(p, BACKUPS / f"face-{stamp}-{p.name}")
        p.write_bytes(t.encode("utf-8"))
    print("\n  ✅ 已写盘 ＋ 交付面三件已备份。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
