"""《前端设计守则》与代码之间的**引用完整性**（`2026-09-26` 立 · 用户要求把守则"重构为更标准的"）。

⭐ 为什么要有本件：守则是**口径的唯一主人**，而代码里到处用 `（守则 §4.2 状态必须真实）` 这种方式
**引用**它。守则一改版（或有人手滑写成 `§11` / `§4.11`），引用就**悬空** —— 而悬空引用在界面上
看不出任何毛病：下一个人照着 §11 去查，查不到，只好自己编一套口径（本仓最忌"同一件事两个主人"）。
⇒ 三半都由机器守：
  ① **引用落得住**：壳 / 尺子 / 测试里出现的每一个 `守则 §X`，X 必须在守则里**真有那一条**；
  ② **条文有判据**：§2–§5 的每一条，`判据` 那一栏**不许空**（空 = "还没兜住"，必须写明
     「人眼 · 未挂」或判据名 —— ⛔ 假装有判据比没有更坏）；
  ③ **原文逐字**：附录 A 是用户原文存档，⛔ 不许在原文里改口径（要改就改正文 ＋ 记 §10）。

⚠️ 本件**不判**"守则本身对不对"（那是用户与 §10 变更记录的事）；它判的是**引用与结构**。
⚠️ 形态变了（换文件名 / 换表格列）⇒ 同批改本件，⛔ 别让判据静默失效。
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.acc_plugin import acc
from tests.shell_src import SHELL

#: 守则正文（`ops/` 在**仓根**下 —— 与 `shell_src` 取 `index.html` 同一个根）
DOC = Path(__file__).resolve().parents[2] / "ops" / "前端设计守则-以使用用户为中心.md"


def _doc() -> str:
    assert DOC.exists(), f"找不到守则正文：{DOC}（它是 `守则 §X` 这类引用的主人）"
    return DOC.read_text(encoding="utf-8")


def _rule_ids(text: str) -> set[str]:
    """守则里**真有的条目号** = 表格首格（`| §3.1 | …`）＋ 节标题（`## §3 …`）。"""
    ids = {m.group(1) for m in re.finditer(r"^\|\s*§(\d+(?:\.\d+)?)\s*\|", text, flags=re.M)}
    ids |= {m.group(1) for m in re.finditer(r"^#{2,3}\s*§(\d+(?:\.\d+)?)\b", text, flags=re.M)}
    return ids


def _cited_ids(text: str) -> set[str]:
    """文本里出现的 `守则 §X`（只看带"守则"二字的引用 —— 别的 `§` 是《说明书》的节号）。"""
    return {m.group(1) for m in re.finditer(r"守则\s*§(\d+(?:\.\d+)?)", text)}


@acc()
def test_守则的引用都落得住():
    """⭐ 每一个 `守则 §X` 都能在守则里找到那一条。

    ⚠️ 引用悬空 = 下一个人自己编一套口径（本仓最忌"同一件事两个主人"）。
    ⚠️ **能证伪**：把正文里某条删掉 / 把代码里的 `§4.2` 写成 `§4.11` ⇒ 本件必红。
    """
    text = _doc()
    have = _rule_ids(text)
    assert {"0", "3", "4", "5"} <= have, f"守则的节结构变了（只数到 {sorted(have)[:12]}）—— 形态变了就同批改本件"
    root = DOC.parents[1]
    sources = [("壳", SHELL)]
    for pat in ("tools/**/*.py", "backend/tests/*.py"):
        for p in root.glob(pat):
            sources.append((str(p.relative_to(root)).replace("\\", "/"),
                            p.read_text(encoding="utf-8", errors="ignore")))
    bad: list[str] = []
    seen: set[str] = set()
    for name, src in sources:
        for rid in _cited_ids(src):
            if rid not in have:
                bad.append(f"{name} 引用了 `守则 §{rid}`，而守则里没有这一条")
            seen.add(rid)
    assert not bad, "\n".join(bad)
    assert seen, (
        "**一处 `守则 §X` 引用都没找到** —— 要么引用被删光了（守则就成了没人读的文档），"
        "要么写法变了（那就同批改本件）")


@acc()
def test_守则每条都写了判据():
    """⭐ §2–§5 的每一条，`判据` 栏**不许空**：空 = "还没兜住"，那就得写明「人眼 · 未挂」。

    ⚠️ 守则开篇自己写着"能机器判的必须挂判据"（本仓铁律：能机器判的别靠自觉）——
       这一条就是**让那句自我要求可检查**，而不是靠下次谁记得。
    ⚠️ **能证伪**：把某条的判据栏清空 ⇒ 本件必红。
    """
    text = _doc()
    rows = [(m.group(1), m.group(0)) for m in
            re.finditer(r"^\|\s*§(\d+(?:\.\d+)?)\s*\|.*$", text, flags=re.M)]
    assert len(rows) >= 30, f"§2–§5 的条目表看起来不完整（只数到 {len(rows)} 条）"
    bad = []
    for rid, line in rows:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not cells[3]:
            bad.append(f"§{rid} 的「判据」栏空着（要么挂判据，要么写「人眼 · 未挂」）：{line[:70]}")
    assert not bad, "\n".join(bad)


@acc()
def test_守则的用户原文是逐字存档():
    """⚠️ 附录 A 是**逐字存档**（改口径要改**正文** ＋ 记 §10，⛔ 不许动原文）。

    这里只钉**哨兵**（首句 / 末行案例 / 三个节标题）—— 全文比对会让"补一个错别字"这种正当修正
    也报红，那不是本件要管的。
    """
    text = _doc()
    assert "## 附录 A · 用户原文（**逐字**存档" in text, "附录 A（用户原文）不见了"
    for must in (
        "你是替\"使用用户\"把关的人，不是替开发自己方便的人。",
        "## 0. 总纲",
        "## 5. 执行层硬规则（逐条可检查）",
        "## 7. 正反案例对照",
        "| 技术字段 | 列表显示 `task_id: 88213`",
    ):
        assert must in text, f"用户原文被改了（找不到：{must!r}）—— 附录 A 只许逐字存档"
    # ⭐ 本仓补充的条目必须**标明是补充**（别混进用户原文里，也别忘了"这谁加的"）
    assert "[补充·2026-09-26]" in text, \
        "新增条目丢了来源标记（`[补充·日期]`）—— 要让下一个人一眼看出哪些是用户原话、哪些是本仓补充"
    assert "§2.7" in text, "§2.7（结论要贴在被说的对象上）不见了 —— 它是用户 2026-09-26 报障的落点"
