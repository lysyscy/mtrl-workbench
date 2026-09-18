"""`TAIL-40` 实施记录落账（2026-09-18）：

1. `TAIL-40` 状态 → **进行中**（后端已落 ＋ 数据侧已收口；余壳侧接线 ＋ 绑判据）。
2. `TAIL-41` **新增**：`latest_unresolved` 会回溯 20 条 ⇒ 抓取成功后「未命中清单」不清空（今天无害，将来会显陈旧）。
3. §14.3 索引表同步（TAIL-40 已批、补 TAIL-41 行）。
4. §15 计数行：A 类 10 → 11。
5. §16 追加「实施记录」。
"""

from __future__ import annotations

import pathlib
import sys
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"

lines = PLAN.read_text(encoding="utf-8").split("\n")
done: list[str] = []


def sub1(old: str, new: str, tag: str) -> None:
    global lines
    joined = "\n".join(lines)
    n = joined.count(old)
    if n != 1:
        raise SystemExit(f"⛔ {tag}：命中 {n} 次（期望 1）\n{old[:130]}")
    lines = joined.replace(old, new).split("\n")
    done.append(tag)
    print(f"  ✅ {tag}")


def insert_after(prefix: str, block: str, tag: str) -> None:
    hits = [i for i, ln in enumerate(lines) if ln.startswith(prefix)]
    if len(hits) != 1:
        raise SystemExit(f"⛔ {tag}：锚命中 {len(hits)} 次")
    lines.insert(hits[0] + 1, block)
    done.append(tag)
    print(f"  ✅ {tag}")


# ---- ① §14.3 索引：TAIL-40 已批 + 补 TAIL-41
sub1(
    " | 用户 2026-09-18 裁定「加入剔除规则」；口径主人在《说明书》§4.2.2，见 §15 新行 |",
    " | 用户 2026-09-18 裁定「加入剔除规则」，**同日批准方案**；口径主人在《说明书》§4.2.2，见 §15 新行 |",
    "§14.3 · TAIL-40 标注已批准",
)
insert_after(
    "| `TAIL-40` **`m14` 规则配置接线 ＋ 剔除规则落库**",
    "| `TAIL-41` ⚠️ **「未命中清单」在抓取成功后不清空**（`latest_unresolved` 回溯 20 条）"
    " | **随时** | ① 它是「手动查看未命中」这类入口的**前置**；② 越晚改，越多地方按「清单会自己过期」的假设写 | "
    "本轮接 `TAIL-40` 时核对发现，见 §15 新行 |",
    "§14.3 · 新增 TAIL-41",
)

# ---- ② §15 A 类：TAIL-40 状态 + 新增 TAIL-41
sub1(
    "（规则**从库读**，不得分叉成第二份） | 立刻 | 待做（**方案先行**：用户要求先看方案再动） |",
    "（规则**从库读**，不得分叉成第二份） | 立刻 | **进行中**（2026-09-18）：**方案已批（§16）** · **后端已落**"
    "（`exclude_rule` 表 ＋ `rules_repository` ＋ `/api/m14/rules` 4 端点，真机验证：幂等初始化 / 写入 / "
    "三条拒绝路径 / 判定真的生效）· **数据侧已收口**（新增「付款项目名＝四分公司2019年小微项目」⇒ **再抓一次后 "
    "2026-09 整批 62 行落库**，剔除 15 行、其中那条 2019 行 `excluded=True`／来源 `rule`／归属为空）· "
    "断言 9 条 ＋ 反向灵敏度 **8/8** · ⏭️ **余 = 壳侧接线 ＋ 绑 `ACC-CFG-RULE-001` 5 点** |",
    "§15 A 类 · TAIL-40 状态 → 进行中",
)
insert_after(
    "| `TAIL-39` |",
    "| `TAIL-41` | ⚠️ **「未命中清单」在抓取成功后不清空** —— `mod03_notice/repository.latest_unresolved` "
    "**回溯最近 20 条** `run_type=fetch` 记录、取最新一条 `reason=ownership_unsettled` 的 ⇒ 那条记录"
    "（含 `detail.unresolved`）会**长期留着** | 接 `TAIL-40` 时核对发现（2026-09-18）：此刻库里还躺着 "
    "**已解决**的那条 2019 未命中项 | 用户可能对着**已经解决**的清单去补词 / 建小微 ⇒ 白干一场，"
    "**且会往档案里塞错行** | `latest_unresolved` 改成**只看最近一次抓取**（成功 ⇒ 无清单）；"
    "或在抓取成功时清掉旧记录的 `unresolved` —— 两种都要补断言 | **随时**"
    "（等有「手动查看未命中」入口时**必做**；**现在改也行且更省事**） | 待做 |",
    "§15 A 类 · 新增 TAIL-41",
)

# ---- ③ 计数行
_hdr = [i for i, ln in enumerate(lines) if ln.startswith("> **当前状态（2026-09-18")]
if len(_hdr) != 1:
    raise SystemExit(f"⛔ 计数行命中 {len(_hdr)} 次")
now = datetime.now().strftime("%Y-%m-%d %H:%M")
lines[_hdr[0]] = f"> **当前状态（{now}）**：A 类 **11** 条 · B 类 **0** 条 · C 类 **1** 条 · 已销号 **32** 条。"
done.append("§15 计数行 → A 11 · B 0 · C 1 · 已销号 32")
print("  ✅ §15 计数行 → A 11 · B 0 · C 1 · 已销号 32")

# ---- ④ §16 追加实施记录
lines.append("")
lines.append("### 16.6 实施记录（2026-09-18 · **进行中**）")
lines.append("")
lines.append("| 段 | 状态 | 证据 |")
lines.append("|---|---|---|")
lines.append("| ① 迁移 ＋ 表 ＋ 仓储 ＋ loader | ✅ 已落 | `exclude_rule` 表（`11b991b4e7bf`）· "
             "`mod03_notice/rules_repository.py` · 迁移**验证三连**（`current` = head · `upgrade` 成功 · "
             "`check` 无待生成）＋ **downgrade/upgrade 往返** |")
lines.append("| ② 判定侧接通（抓取管线读生效规则集） | ✅ 已落 | `rows_needing_ownership(rows, rules)` 与 "
             "`apply_fetched_row(..., rules=rules)` **同一份**（⛔ 抓取路径**不**调写库的初始化）|")
lines.append("| ③ 端点 ＋ 真机验证 | ✅ 已落 | `GET/POST /api/m14/rules` · `PUT/DELETE /api/m14/rules/{id}`；"
             "真机：幂等初始化（库空 ⇒ 4 行、带 id）· 新增 · **三条拒绝路径**（按收款单位 / 命中值空 / 未知类别）|")
lines.append("| ④ 用户那条规则 ＋ 整批落库 | ✅ 已收口 | 新增「**付款项目名 ＝ 四分公司2019年小微项目**」⇒ "
             "**再抓一次 2026-09：`fetched 62 · upserted 62`**（剔除 15 行；那条 2019 行 `excluded=True`／"
             "来源 `rule`／归属为空）|")
lines.append("| ⑤ 断言 ＋ 反向灵敏度 | ✅ 已落（后端）| `tests/test_rules_store.py` **9 条** · 反向灵敏度 **8/8** · "
             "MD5 逐字节复原 · 四态 **487 不变** |")
lines.append("| ⑥ 壳侧接线 ＋ 绑 `ACC-CFG-RULE-001` 5 点 | ⏭️ **待做** | 壳里 `RULE_EX` 仍读演示常量；"
             "`ruleAdd/ruleEdit/ruleDel` 只改内存 ⇒ 页面尚不可用（**后端已可用**，规则由 API 管理）|")
lines.append("")

PLAN.write_text("\n".join(lines), encoding="utf-8")
print(f"\n共 {len(done)} 处")
sys.exit(0)
