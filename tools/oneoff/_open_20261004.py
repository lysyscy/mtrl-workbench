"""把「文档重构」这一轮的余下票**一次登进台账**（每张都走 `_tail_open.py`：三处同改 ＋ 收尾断言）。

⚠️ **本件不自己写台账** —— 只做**驱动**（拼参数、逐张调 `_tail_open.py`），
   台账的写法**只有一个主人**（`tools/oneoff/_tail_open.py` ＋ `audit_common.write_counts`）。
   理由：另写一套 = **第二套实现**（本仓最贵的病）。

用法：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_open_20261004.py          # 干跑（逐张 _tail_open 干跑）
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_open_20261004.py --apply  # 真写盘
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
OPEN = str(ROOT / "tools" / "oneoff" / "_tail_open.py")

# (id, what, src, not_doing, where, when, why, pre)
TICKETS = [
    ("224",
     "🧱 装「字墙」机器眼：活文档单行 >800 字 ⇒ 黄（＋反向灵敏度）",
     "用户 2026-10-04「①④按推荐」（文档重构方案 §六-4 丙案第一步）· 本轮量出：主文档 103 行 >800 字 / 36 行 >1500 字",
     "不装 ⇒ 字墙只能靠人眼撞见（已沉过 4 次、每次都长回来）",
     "tools/audit/audit_meta.py（新检查）＋ doc_audit 的 T 表 ＋ ops/阈值表.md（登记）＋ tools/mut/（配靶）",
     "立刻",
     "①不是任何东西的前置 ②成本不随时间变贵（一次） ③同域＝文档尺子那一层 ④前置已查清（方案 §一 已量真值）",
     "本轮随即开工"),
    ("225",
     "🎫 票体系：建票仓 `.codebuddy/work/50-tickets/` ＋ `T6` 换对象（票＝一个文件 · 索引＝一行）",
     "用户 2026-10-04「②按推荐」＋「走正式的 `ask-matt` 推荐技能」（方案 §十一 乙案）",
     "不做 ⇒ 尾巴继续挤在表里一格（现普遍 1000–2400 字，是字墙最大来源）",
     "audit_meta.check_tail_ledger（`T6`）＋ ledger_counts ＋ _tail_open/_tail_close ＋ tools/mut/ 靶 ＋ `T12` 白名单 ＋ work/README ＋ 根 README §三",
     "立刻",
     "①不是任何东西的前置 ②成本随票数增长（越晚改越多） ③同域＝台账那一层 ④前置已查清（形态见方案 §十一）",
     "`TAIL-224` 之后（先有字墙尺子再看效果）"),
    ("226",
     "🧱 主文档拆 3 份（规则 / 台账+状态 / 交接）：先只改机器件（T12 白名单 1→3 · 台账件换名 · 预算分 3 份）",
     "用户 2026-10-04「①按推荐」（方案 §六-1 丙案 · 批 2）",
     "不做 ⇒ 一份文件继续回答 6 个问题（谁都得读 1800 行）",
     "tools/audit/audit_common.py ＋ audit_meta.py ＋ _tail_open/_tail_close ＋ tools/mut/ 靶 ＋ 根 README ＋ 入场指针",
     "随时",
     "①不挡前置 ②成本不随时间变贵 ③同域＝台账与尺子那一层 ④前置已查清（方案 §六-1 已给三案）",
     "`TAIL-225` 之后（票体系先落地）"),
    ("227",
     "📦 主文档拆 3 份：逐块搬内容（人眼可读性收口）",
     "用户 2026-10-04「①按推荐」（方案 §六-1 丙案 · 批 3）",
     "不搬 ⇒ 骨架分了、内容还挤在旧处（等于没拆）",
     "计划 §13.6 / §15 / §0.2 的内容逐块迁 ＋ plans/archive/ 归档件",
     "随时",
     "①不挡前置 ②成本不随时间变贵 ③同域＝同一份文件 ④前置＝TAIL-226（机器件先改完，否则搬一步红一步）",
     "`TAIL-226` 之后"),
    ("228",
     "🔍 全仓规矩成色扫描 ＋ 逐条处置（留 / 改 / 撤）—— 不用用户标出处，由我判好坏与是否合今",
     "用户 2026-10-04「③按推荐」＋「本仓很多规矩都可能是 AGENT 自作主张」",
     "不做 ⇒ 自定规矩继续挡真诉求（已实测一例：根 AGENTS.md 被自家的 T12 挡了半个月）",
     "MEMORY.md §八 ＋ 细则.md ＋ work/40-decisions/ ＋ ops/前端设计守则 ＋ 入场指针 —— 逐条给留/改/撤＋落点；撤项进 audit_common.CANCELLED",
     "随时",
     "①不挡前置 ②成本不随时间变贵 ③同域＝纪律册那一层 ④前置已查清（已有 ≈167 条的盘点底子）",
     "谁空谁做（可与 225/226 并行）"),
]


def main(apply: bool) -> int:
    rc_all = 0
    for (tid, what, src, not_doing, where, when, why, pre) in TICKETS:
        args = [PY, "-X", "utf8", OPEN, "--id", tid,
                "--what", what, "--src", src, "--not-doing", not_doing,
                "--where", where, "--when", when, "--why", why, "--pre", pre]
        if apply:
            args.append("--apply")
        print(f"\n===== TAIL-{tid} =====")
        r = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        print((r.stdout or "").strip())
        if r.returncode != 0:
            print((r.stderr or "").strip())
            print(f"⛔ TAIL-{tid} 失败 ⇒ 停（先弄清再继续，⛔ 不带着半批往下走）")
            return 1
    return rc_all


if __name__ == "__main__":
    sys.exit(main("--apply" in sys.argv))
