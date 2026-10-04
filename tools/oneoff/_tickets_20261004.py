"""一次性：把 `§15 §一` 在办的尾巴迁成**票文件**（`TAIL-225` 票体系 · 2026-10-04）。

读者：接手 `TAIL-225` 的会话｜回答什么：票仓那 8 张票是怎么建出来的｜何时读：只在核对票仓来源时。
状态：一次性件（跑完即留痕，⛔ 不要再跑 —— 会覆盖票文件正文）。依据 = `ops/agents/issue-tracker.md` §二 的票模板。

⚠️ **只建 8 张在办票**（`§一` 那一批）；`§四` 已销号 223 条**不追改**（留痕口径，见方案 §十一-3）。
⚠️ 每张票的文头必须齐 `读者 / 回答 / 何时读 / 状态`（`T15` 机核这四个词）。
"""
from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
TDIR = REPO / ".codebuddy" / "work" / "50-tickets"

#: 编号 → (短名, 状态, 事项一句话, 阶段/时机, 来源, 不做会怎样, 落点, Blocked by, 验收, 正文)
TICKETS: dict[str, tuple] = {
    "188": (
        "交付包与迁移", "ready-for-agent",
        "交付包与迁移：本机 ⇒ 办公室电脑（包 = 可继续开发的可运行系统，开发链全带）",
        "`M8`",
        "用户 2026-09-29 口述（出处 = `.codebuddy/memory/2026-09-29.md` §㉓/㉓之二）",
        "目标机上装不起来 / 落地无自检 ⇒ 系统交不出去",
        "`work/10-designs/设计-交付包与迁移-20260929.md` ＋ `ops/pack.ps1` / `ops/deploy_restore.ps1` / `ops/selfcheck.ps1` / `ops/deployment.md`",
        "None（可以立刻开始）· ⚠️ 硬约束 = 赶在**产包（去办公室的前一天）**之前",
        ["包能在目标机装起来（`selfcheck` rc=0）", "恢复演练：对空库还原成功才算数", "`MANIFEST.txt` 的 HEAD 与本机 `git log -1` 对得上"],
        "包要带的：tests / tools / demo / 验收面 / 计划台账 / 记忆 ＋ `ops/{pack,deploy_restore,selfcheck}.ps1` ＋ `ops/deployment.md`。\n"
        "✅ 路径可配置改造已办（node 三级回退；交付面定位走 `.env` 的 `PRD_ACCEPTANCE_BASELINE`；`_audit_face.py` 改走同一机制；Playwright 目录写进 `ops/deployment.md`）。\n"
        "⭐ 2026-09-30 用户指示：《材料科业务全流程说明书.md》＋ `PRD/验收/验收基线.json` **放进包里**（包内留一份快照 ⇒ `.env` 默认指包内；⚠️ 云那份仍是真源）。\n"
        "⚠️ 记账：`requirements.lock`（`D10` 加固② 后半）**仍未做**，挂在线上。",
    ),
    "221": (
        "shell_source-被绕过", "ready-for-agent",
        "`tools/audit/shell_source.py` 被 8 处绕过（架构走查候选④）",
        "`随时`",
        "架构走查（出处 = `work/10-designs/设计-壳界面口径接口面-20261003.md` 同批候选）",
        "不改 ⇒ 壳的「件清单 / 加载顺序」口径会长出第二、第三份（本仓最贵的病）",
        "先只读量：8 处**逐处点名** ＋ 判「该收编还是该登记例外」",
        "None（可以立刻开始）",
        ["8 处逐处给出结论（收编 / 登记例外）", "若收编 ⇒ 同批改判据与变异靶"],
        "`shell_source.py` 本该是「读壳」的唯一出口 ⇒ 绕过 = 每处各写一套拆件 / 拼接口径。\n"
        "⚠️ 先量再定：⛔ 不许直接动刀（同 `TAIL-219` 的打法：先只读出施工图）。",
    ),
    "222": (
        "data-act-无归属", "needs-triage",
        "`data-act` 无归属（架构走查候选⑤ · **推测性**）",
        "`随时`",
        "架构走查（候选⑤ · 推测性）",
        "不改 ⇒ 判据与变异只能**按字符串字面钉锚点**（本仓已有多次「钉实现形态 ⇒ 假红」的亏）",
        "先只读量：全站 `data-act` **取值清单** ＋ 有没有**重复 / 无人认领**",
        "None（可以立刻开始）",
        ["全站 `data-act` 取值清单量出来", "量完可能判定「不值得做」⇒ 那就写一句「为什么不做」收口（同 `TAIL-196` 的写法）"],
        "`data-act` 是壳的动作锚点，却**没有一处登记**「谁拥有它 / 合法取值有哪些」。\n"
        "⚠️ 状态 = `needs-triage`（还没定要不要做）；量完再升 / 收口。",
    ),
    "223": (
        "落地流程顺序坑", "ready-for-agent",
        "落地流程的顺序坑：`ops/init_db.sql` 的 `<PASSWORD>` 与建库落在同一次 `deploy_restore` 调用里",
        "`随时`",
        "用户 2026-10-04「甲」（检查产包流程时量出 · 出处 = `memory/journal/2026-10-04.md` §4）",
        "照 `ops/deployment.md` 手工落地的人必踩：第一次跑就用字面 `<PASSWORD>` 建出角色，而 `CREATE ROLE` **不可重跑** ⇒ 库口令永远改不过来（`selfcheck` 第③项红，原因不明显）",
        "`ops/init_db.sql` 改成可重跑（`CREATE ROLE` 加 `IF NOT EXISTS` ＋ `ALTER ROLE … PASSWORD`）＋ 同批改 `ops/deployment.md` §一/§二 与 `ops/deploy_restore.ps1` 第 5 步的措辞",
        "None（可以立刻开始）· ⚠️ 修它要动**交付关键件** ⇒ ⛔ 别赶在产包前动",
        ["`init_db.sql` 可重跑（跑两次不报「角色已存在」）", "文档顺序与脚本实际顺序一致", "过 `_ps_bom.py` ＋ `_ps_parse_check.ps1`"],
        "落地向导（`.codebuddy/work/00-scratch/tmp-20261004-deploy-wizard.ps1`）已按正确顺序**绕开**：第 2 步先 `git clone` ⇒ 第 3 步改口令 ⇒ 第 5 步才跑 `deploy_restore`。\n"
        "⚠️ 本轮（建票时）**没动** `ops/init_db.sql`（产包前不碰交付关键件）。",
    ),
    "225": (
        "票体系", "claimed",
        "票体系：建票仓 `.codebuddy/work/50-tickets/` ＋ `T6` 换对象（票 = 一个文件 · 索引 = 一行）",
        "`立刻`",
        "用户 2026-10-04「②按推荐」＋「走正式的 `ask-matt` 推荐技能」（方案 §十一 乙案）",
        "不做 ⇒ 尾巴继续挤在表里一格（现普遍 1000–2400 字，是字墙最大来源）",
        "`audit_meta.check_tail_ledger`（`T6`）＋ `ledger_counts` ＋ `_tail_open`/`_tail_close` ＋ `tools/mut/` 靶 ＋ `T12` 白名单 ＋ `work/README` ＋ 根 `README` §三",
        "None（可以立刻开始）· ⚠️ **票仓与 `T6` 换对象必须同批**（只建票仓不改尺子 = 台账行与票文件双份）",
        ["8 张在办票迁成文件（本批）", "`T6` 认票文件（在位 / 幽灵 / 栏位 / 状态受控词）", "`_tail_open` 建票文件、`_tail_close` 标 `done`", "反向灵敏度同批", "闸门全绿"],
        "## 决定\n"
        "- 票 = **一个文件**（`TAIL-<编号>-<短名>.md`）；索引 = 计划 §15 **一行一票**。\n"
        "- ⚠️ **存量 223 条已销号行不追改**（留痕）；`T6` 的四条新查**只对 `§一/§二/§三`（在办）** 生效。\n"
        "- ⭐ 形态 = **新增票文件层，不放松任何现有判据**（本仓「先立门禁 ＋ 老账记账」那套打法）。\n"
        "- ⚠️ 下一步（本条之后另开票）：`§一` 索引行**收成薄索引**（一句话 ＋ 指针），细节全留票文件。",
    ),
    "226": (
        "主文档拆3份-改机器件", "ready-for-agent",
        "主文档拆 3 份（规则 / 台账+状态 / 交接）：**先只改机器件**",
        "`随时`",
        "用户 2026-10-04「①按推荐」（方案 §六-1 丙案 · 批 2）",
        "不做 ⇒ 一份文件继续回答 6 个问题（谁都得读 1800 行）",
        "`tools/audit/audit_common.py` ＋ `audit_meta.py` ＋ `_tail_open`/`_tail_close` ＋ `tools/mut/` 靶 ＋ 根 `README` ＋ 入场指针",
        "TAIL-225（票体系先落地 —— 否则同一批字墙要碰两次）",
        ["`T12` 白名单 1 → 3（`plans/` 三份活文档）", "台账件换名（`LEDGER_REL`）", "预算分 3 份（`DOC_BUDGETS` ＋ `PLAN_LINE_BUDGET`）", "同批改变异靶", "闸门全绿"],
        "⚠️ 批 2 那一步**必须一口气做完才绿**（机器件改一半 = 尺子红）。实况与分批见方案 §六-1 丙案。",
    ),
    "227": (
        "主文档拆3份-搬内容", "ready-for-agent",
        "主文档拆 3 份：**逐块搬内容**（人眼可读性收口）",
        "`随时`",
        "用户 2026-10-04「①按推荐」（方案 §六-1 丙案 · 批 3）",
        "不搬 ⇒ 骨架分了、内容还挤在旧处（等于没拆）",
        "计划 `§13.6` / `§15` / `§0.2` 的内容逐块迁 ＋ `plans/archive/` 归档件",
        "TAIL-226（机器件先改完，否则搬一步红一步）",
        ["三份骨架各自装着该装的内容（一份文件只回答一个问题）", "原处留指针", "闸门全绿"],
        "⚠️ 搬的时候**先减后加**（`T10` 预算按件算）。",
    ),
    "228": (
        "规矩成色扫描", "ready-for-agent",
        "全仓规矩成色扫描 ＋ 逐条处置（留 / 改 / 撤）—— 不用用户标出处，由我判好坏与是否合今",
        "`随时`",
        "用户 2026-10-04「③按推荐」＋「本仓很多规矩都可能是 AGENT 自作主张」",
        "不做 ⇒ 自定规矩继续挡真诉求（已实测一例：根 `AGENTS.md` 被自家的 `T12` 挡了半个月）",
        "`MEMORY.md` §八 ＋ `细则.md` ＋ `work/40-decisions/` ＋ `ops/前端设计守则` ＋ 入场指针 —— 逐条给留/改/撤＋落点；撤项进 `audit_common.CANCELLED`",
        "None（可以立刻开始）· 可与 225/226 并行",
        ["≈167 条逐条给成色与处置", "撤项走 `CANCELLED` 登记（⛔ 不静默删）", "机器眼：`T8` 拦「撤了又长回来」"],
        "已有底子 = 「规矩成色复审」那两批（`TAIL-216` 等）的 ≈167 条盘点。\n"
        "⚠️ 判效力看标记：`[用户·原话]` = 铁律 · `[助手自定]` = **默认可质疑、可撤**。",
    ),
}


def _render(tag: str, t: tuple) -> str:
    short, state, what, when, src, bad, where, blocked, accept, body = t
    checks = "\n".join(f"- [ ] {x}" for x in accept)
    return (
        f"# {tag}：{short}\n\n"
        f"> **读者**：要开工 / 收尾这张票的 agent｜**回答**：这条尾巴要做出什么、卡在哪、怎么算做完\n"
        f"> **何时读**：领这张票之前｜**状态**：`{state}`\n"
        f"> 创建 / 更新 2026-10-04｜关联 `{tag}`｜索引 = 计划 §15（**一行一票**）｜协议 = `ops/agents/issue-tracker.md`\n\n"
        f"**要做出什么（从用户视角说清）：** {what}\n\n"
        f"**来源：** {src}\n\n"
        f"**不做会怎样：** {bad}\n\n"
        f"**落点：** {where}\n\n"
        f"**阶段 / 时机：** {when}\n\n"
        f"**Blocked by：** {blocked}\n\n"
        f"**验收：**\n{checks}\n\n"
        f"## 正文（自由写 · 只追加）\n\n{body}\n"
    )


def main() -> int:
    TDIR.mkdir(parents=True, exist_ok=True)
    n = 0
    for num, t in sorted(TICKETS.items()):
        tag = f"TAIL-{num}"
        p = TDIR / f"{tag}-{t[0]}.md"
        p.write_text(_render(tag, t), encoding="utf-8", newline="")
        print(f"  ✅ {p.relative_to(REPO).as_posix()}")
        n += 1
    print(f"共 {n} 张 → {TDIR.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
