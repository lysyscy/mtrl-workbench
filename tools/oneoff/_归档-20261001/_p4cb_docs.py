#!/usr/bin/env python
r"""`TAIL-64` **`P4-c-b`** 的同批文档落纸（2026-09-30）。

**三件事**（每处都断言"恰好命中 1 次 / 1 行" —— ⛔ 宁可不改，也不打偏）：
 1. **施工图**：§8.10 状态行改成「`P4-c` 收口」＋ **新增 §8.12**（`P4-c-b` 实况）。
 2. **计划**：`TAIL-64` **销号**（三处同批：§14.3 排期行改 ✅ / §15 §一 A 类表**删行** /
    §15 §四「已销号」**补行**）＋ 两处**计数**同批（文头 ＋ §15 顶部）＋ §0.4 那句同批。
 3. **计划**：**立 `TAIL-202`**（i8 凭证「未绑即拒」· 口径由 2026-09-30「全部按推荐」定）
    ⇒ §15 §一 补行 ＋ §14.3 补行；§13.6 里那两处"余 13 块"与"未决/641"同批订正。

⚠️ 为什么销号要动这么多处：`T6` 查「排期表里的编号必须能在台账里找到」，而计数是**人读的那一行**
（`doc_audit` 的 7 号条款查它）⇒ 少改一处就是一处**静默的假账**。

用法：`python tools/oneoff/_p4cb_docs.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DESIGN = ROOT / ".workbuddy" / "work" / "10-designs" / "设计-表格筛选配置化-20260924.md"
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"

# ── 施工图 ────────────────────────────────────────────────────────────────
D1_OLD = "余 **`P4-c-b`（13 块）** 未开工。"
D1_NEW = "⭐ **`P4-c-b` 也已办**（同日晚 · 余 13 块一次铺完 · 见 **§8.12**）⇒ **`P4-c` 整条收口**。"
D2_ANCHOR = "**⏭ 状态**：⭐ **`P4-c-a` 试点已办**"
D2_SEC = """
### 8.12 `P4-c-b` 实况（2026-09-30 · 余 13 块一次铺完 ⇒ **`P4-c` 收口**）

**做法**（脚本 `tools/oneoff/_p4cb_calib.py` · 干跑 ＋ `--write`）：
 ① 出口补一个参 **`post`（默认 `''`）** = 条数与灰色提示之间那一段（真例 = **`m03` 的 `&nbsp;`**；
    ⛔ **按原样传参、不许顺手统一** —— 为一个不换行空格降级"字节不变"这唯一的硬证据不划算）；
 ② 13 块逐块换成 `${CALIB({items:[…]})}`（`m03` 是 `${CALIB({post:'&nbsp;',items:[…]})}`）。

**自证（本批最强的一条）**：一侧是**原文**，⛔ 不是我在内存里"重建"的 —— **从 git 取**
（`6abd900:backend/app/web/index.html`）；另一侧是**将写入的真文本** ⇒
**14 页逐页 `node` 渲染 ＋ 逐字节比对**（含已转的 `m13` ⇒ 顺带回归"加参后它没变"）。
⇒ **14/14 全等** · `index.html` **1637 → 1624 行**（每块 -1）。

| 项 | 值 |
|---|---|
| 判据 | `test_ux_numbers.py` 两条：**条数一致**（已退化成**墓碑**：手抄形态不许再回来）＋ **走统一出口**（内核 ＋ 逐页） |
| 名单 | `tests/shell_src.py::CALIB_PAGES`（**唯一出处** —— `test_ux_brief` 也读它，⛔ 不在两个判据件里各写一份） |
| 切片出口 | `shell_src.page_seg(page)`（定义只有一处 = `ui_parity.slices()`） |
| 变异 | `tools/mut/_mut_uxnum.py` **6/6**（`M4` **换靶** = 又手抄一整块；`M6` 删 —— 与新 `M4` 是同一件事） |
| 原型 | ⛔ 未动（没有尺子比原型；「双边同步」已取消） |

⭐⭐ **同批修掉两处"抽通用件必然碰掉的老判据"**（都属**钉源码形态** ⇒ 改钉**意图**，⛔ 不是退回钉字面）：
 ① `test_ux_brief.py` 的「折叠出口 ≥ 8 处」—— 字面 `<details class="tip"` 从 **16 掉到 3**
    （内核 1 ＋ 两处非口径说明）⇒ 照旧数会**假红** ⇒ 改成 **字面数 ＋ `CALIB(` 调用点数**
    （⛔ **别把下限调低** —— 那等于承认"说明可以少"，而这条判据的**目的**正是"不许删光说明"）。
 ② `test_wired_m03_list.py` 的 `'<details class="tip">' in SHELL` —— 收件后它**退化成真空断言**
    （内核里那一份也能让它过，哪怕 m03 自己的块被整段删掉）⇒ 改钉**本页真的委托了出口**
    （`page_seg("m03")` ＋ 两种开局都收 —— ⚠️ `m03` 是**唯一**带 `post` 的页，第一版就漏了它、当场假红）。

⚠️ **一处口径分歧留痕**：`m03` 的 `&nbsp;` 是 14 块里**唯一**一处（其余 13 块没有）——
本批**原样保留**；要不要统一掉属**排版细节**，⛔ 不在"字节不变"的批里顺手做。
"""

# ── 计划 · 计数与 §0.4 ───────────────────────────────────────────────────
P1_OLD = "A 类 **3** 条 · B 类 0 · C 类 **0** · 已销号 **201**"
P1_NEW = "A 类 **3** 条 · B 类 0 · C 类 **0** · 已销号 **202**"
P2_OLD = "A 类 **3** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **201** 条"
P2_NEW = ("A 类 **3** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **202** 条\n"
          "> ⭐ **2026-09-30**：`TAIL-64` 收口**销号**（⇒ §四）＋ **新立 `TAIL-202`**（i8 凭证「未绑即拒」）"
          "⇒ A 类**仍是 3 条**（`TAIL-188` / `TAIL-195` / `TAIL-202`）。")
P3_OLD = "② **尾巴 A 类剩 3 条**：`TAIL-188` / `TAIL-195` / `TAIL-64`（M8 / 持续档）"
P3_NEW = ("② **尾巴 A 类剩 3 条**：`TAIL-188` / `TAIL-195` / **`TAIL-202`**（i8 凭证「未绑即拒」· M8）"
          "—— ⭐ `TAIL-64` 已于 **2026-09-30 收口销号**（⇒ §15 §四）")

# ── 计划 · §15 §一（删 TAIL-64 行 / 补 TAIL-202 行）────────────────────────
DEL_ROW_64 = "| `TAIL-64` | "
INS_AFTER_188 = "| `TAIL-188` | "
TAIL_202_ROW = (
    "| `TAIL-202` | ⚠️ **i8 凭证「未绑即拒」**：**有身份**但没绑 i8 ⇒ 拒绝抓取并给**人话提示**"
    "（⛔ 不再回落 `.env` —— 那会拿别人的账号去登录、**顶掉同事的 i8 会话**，且执行记录记错人）；"
    "**无身份**（命令行脚本 / 测试进程）**仍回落** `.env` | 交付面《说明书》**§7.8**"
    "（「登录体系落地后…**未填即拒绝抓取、不回落**」）⇄ 实现 `core/identity.py`（仍回落） | "
    "同事一点抓取 ⇒ 拿 `.env` 那个账号登录（i8 含**强踢**）⇒ 把别人的会话顶掉、执行记录还记错人 | "
    "落点 = `backend/app/core/identity.py`（一个分支 ＋ 一处人话提示）＋ 壳上「留空 = 解绑」那句文案 "
    "＋ **契约面同批**（`验收基线.json` 的 `001-13/②`：把「查无此人 / 未登录 ⇒ 回落」改成"
    "「**无身份 ⇒ 回落**；**有身份但未绑 ⇒ 拒绝**」＋ `用例索引.md`） | M8 | "
    "⏳ **待做**（口径已定 · 2026-09-30「全部按推荐」⇒ ⭐ **赶在产包（去办公室前一天）之前**） |")

# ── 计划 · §15 §四（补销号行）───────────────────────────────────────────
HDR_SOLD = "| # | 事项 | 销号依据 | 日期 |"
TAIL_64_SOLD = (
    "| `TAIL-64` | ⭐ **前端表格／筛选／行模板 配置化（伞）** —— `TBL` 表外壳（24 → 3 张裸表）· "
    "`FBAR` 筛选栏 22 处 · `PJB` 项目按钮 11 处 · **虚拟滚动下沉到表级** · `CALIB` 口径说明 **14 块** | "
    "**销号依据** = 2026-09-30 收口：`P4-c-a`（试点）＋ `P4-c-b`（铺余 13 块 · 逐块 **`node` 渲染字节自证**"
    "＝ 拿 git 里的原文比，14/14 全等）⇒ 施工图 **§8.10–§8.12**；判据 = `test_ux_numbers.py` 两条 ＋ "
    "`test_ux_brief.py`（计数改按意图）＋ 取件桩 `shell_src.calib_kernel`；反向灵敏度 "
    "`tools/mut/_mut_uxnum.py` **6/6**；闸门 = pytest 100% · 16 把尺子 `rc=0` · 四态 **644/0** · "
    "真机 `_shell_smoke` `rc=0`；⚠️ 余下两条口径（`TAIL-196` / `TAIL-199`）当日已裁「不动」 | 2026-09-30 |")

# ── 计划 · §14.3（TAIL-64 改 ✅ 留痕 ＋ 补 TAIL-202 行）────────────────────
P4_OLD = "| `TAIL-64` 表格/筛选配置化 | **M8** |"
P4_NEW = "| `TAIL-64` 表格/筛选配置化 | ✅ **已办（2026-09-30 · 收口销号）** ⇒ 见 §15 §四 |"
TAIL_202_SCHED = (
    "| `TAIL-202` i8 凭证「未绑即拒」 | M8（⭐ **必须在产包之前**） | **四问**：① **是前置**"
    "（不修就用别人的账号顶号 ⇒ 上线即错）；② **成本不随时间变贵**（一个分支 ＋ 一处提示 ＋ 契约面 2 处）；"
    "③ **同域 = i8 接入／身份层**（与 `TAIL-188` 产包同批走最省）；④ **前置已到位**"
    "（《说明书》§7.8 早就写了「未填即拒绝」⇒ 是**实现没跟上**，⛔ 不是口径没定） | "
    "**触发** = 产包前一并做；依据 = 用户 2026-09-30「全部按推荐」 |")

# ── 计划 · §13.6（订正那三处"余 13 块 / 未决 / 641"）──────────────────────
Q1_OLD = ("· ⭐ **`P4-c-a` 试点已办**（2026-09-30 · 出口 `CALIB` ＋ `m13` 一处 · 见 §8.11）"
          "⇒ **余 `P4-c-b` 13 块**）")
Q1_NEW = ("· ⭐⭐ **`P4-c` 整条已收口**（2026-09-30：`P4-c-a` 试点 ＋ `P4-c-b` 铺余 13 块 "
          "⇒ **14 块全走出口 `CALIB`** · 逐块 `node` 渲染字节自证 · 施工图 §8.11/§8.12）⇒ `TAIL-64` 收口**已销号**）")
Q2_OLD = ("· ⭐ **`P4-c-a` 试点已办**（出口 `CALIB` ＋ `m13` 一处 · §8.11）"
          "⇒ 余 `P4-c-b` 13 块）**")
Q2_NEW = ("· ⭐⭐ **`P4-c` 整条已收口**（14 块全走出口 · 施工图 §8.11/§8.12）⇒ `TAIL-64` 收口**已销号**）**")
Q3_OLD = "**2026-09-30 已办到 `P4-c-a`**（口径说明试点 · 施工图 §8.11）"
Q3_NEW = "**2026-09-30 已办到 `P4-c-b` ⇒ `TAIL-64` 收口**（口径说明 14 块全走出口 · 施工图 §8.11/§8.12）"
Q4_OLD = ("⚠️ **一条未决等你拍板**：`§9.5 ②` 的 **i8 回落**（文档写「未填即拒绝抓取、不回落」，"
          "实现仍回落 `.env`）；⚠️ 小尾巴：`ops/selfcheck.ps1` 注释里「四态 **641**」已过期（现值 **644**）。")
Q4_NEW = ("⭐ **口径已定（2026-09-30「全部按推荐」）**：i8 回落按 **A** 案 ⇒ 立 **`TAIL-202`**"
          "（**有身份但没绑 i8 ⇒ 拒绝抓取并提示**；**无身份**（脚本 / 测试）仍回落 `.env`）"
          "⇒ 已进 §15 §一 ＋ §14.3；✅ 小尾巴已修（`ops/selfcheck.ps1` 的注释**不再写条数** —— 免得再过期）。")


def rd(p: pathlib.Path) -> tuple[str, str]:
    raw = p.read_text(encoding="utf-8", newline="")
    return raw.replace("\r\n", "\n"), ("\r\n" if "\r\n" in raw else "\n")


def wr(p: pathlib.Path, text: str, nl: str) -> None:
    p.write_text(text if nl == "\n" else text.replace("\n", nl), encoding="utf-8", newline="")


def sub1(text: str, old: str, new: str, what: str) -> str:
    n = text.count(old)
    assert n == 1, f"⛔ {what}：命中 {n} 次（期望 1）—— 锚点过期了？"
    print(f"   ✅ {what}")
    return text.replace(old, new, 1)


def del_line(text: str, prefix: str, what: str) -> str:
    lines = text.split("\n")
    hit = [i for i, ln in enumerate(lines) if ln.startswith(prefix)]
    assert len(hit) == 1, f"⛔ {what}：命中 {len(hit)} 行（期望 1）"
    print(f"   ✅ {what}（删第 {hit[0] + 1} 行）")
    del lines[hit[0]]
    return "\n".join(lines)


def ins_after(text: str, prefix: str, new_line: str, what: str) -> str:
    lines = text.split("\n")
    hit = [i for i, ln in enumerate(lines) if ln.startswith(prefix)]
    assert len(hit) == 1, f"⛔ {what}：锚行命中 {len(hit)} 行（期望 1）"
    print(f"   ✅ {what}（插在第 {hit[0] + 1} 行之后）")
    lines.insert(hit[0] + 1, new_line)
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    design, nl_d = rd(DESIGN)
    plan, nl_p = rd(PLAN)

    # ── 施工图
    design = sub1(design, D1_OLD, D1_NEW, "施工图 §8.10 状态行 ⇒ P4-c 收口")
    assert design.count(D2_ANCHOR) == 1
    design = sub1(design, D2_ANCHOR, D2_ANCHOR + "\n" + D2_SEC.strip("\n") + "\n", "施工图 新增 §8.12")

    # ── 计划：计数 / §0.4
    plan = sub1(plan, P1_OLD, P1_NEW, "计划 文头计数（已销号 201 → 202）")
    plan = sub1(plan, P2_OLD, P2_NEW, "计划 §15 顶部计数（＋一句说明）")
    plan = sub1(plan, P3_OLD, P3_NEW, "计划 §0.4 的 A 类三条")

    # ── 计划：§15 §一（删 TAIL-64 / 补 TAIL-202）
    plan = del_line(plan, DEL_ROW_64, "§15 §一 删 `TAIL-64` 行（已移进 §四）")
    plan = ins_after(plan, INS_AFTER_188, TAIL_202_ROW, "§15 §一 补 `TAIL-202` 行")

    # ── 计划：§15 §四（补销号行）
    plan = ins_after(plan, HDR_SOLD, TAIL_64_SOLD, "§15 §四 补 `TAIL-64` 销号行")

    # ── 计划：§14.3
    plan = sub1(plan, P4_OLD, P4_NEW, "§14.3 `TAIL-64` 行 ⇒ ✅ 已办")
    plan = ins_after(plan, "| `TAIL-64` 表格/筛选配置化 |", TAIL_202_SCHED, "§14.3 补 `TAIL-202` 行")

    # ── 计划：§13.6（三处订正）
    plan = sub1(plan, Q1_OLD, Q1_NEW, "§13.6 口令里的 P4-c 余量")
    plan = sub1(plan, Q2_OLD, Q2_NEW, "§13.6 已确认的下一步里的 P4-c 余量")
    plan = sub1(plan, Q3_OLD, Q3_NEW, "§13.6 已办到 P4-c-b ⇒ TAIL-64 收口")
    plan = sub1(plan, Q4_OLD, Q4_NEW, "§13.6 那条未决（i8）与小尾巴（641）")

    assert "TAIL-64` | " not in plan.split("### 一、A 类")[1].split("### 二、")[0], \
        "⛔ §15 §一 里还留着 `TAIL-64` 行"
    if not args.write:
        print("\n（干跑：⛔ 未写）")
        return 0
    wr(DESIGN, design, nl_d)
    wr(PLAN, plan, nl_p)
    assert rd(DESIGN)[0] == design, "⛔ 施工图写回不一致"
    assert rd(PLAN)[0] == plan, "⛔ 计划写回不一致"
    print("\n✅ 已落盘：施工图（§8.10 状态行 ＋ §8.12）＋ 计划（计数×2 · §0.4 · §15 §一/§四 · §14.3 · §13.6×4）")
    print("⚠️ 接着必跑：`doc_audit.py`（T1–T20 · **T6 查排期↔台账**）＋ `doc_audit.py --ui`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
