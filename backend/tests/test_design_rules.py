"""《前端设计守则》的**结构 · 引用 · 可执行性**守卫（`2026-09-26` 立 · `2026-09-27` 随 `v3` 更新）。

⭐ 为什么要有本件：守则是**前端口径的唯一主人**，而代码里到处用 `（守则 §4.2 状态必须真实）` 这种方式
**引用**它。守则一改版（或有人手滑写成 `§11` / `§4.11`），引用就**悬空** —— 而悬空引用在界面上
看不出任何毛病：下一个人照着 §11 去查，查不到，只好自己编一套口径（本仓最忌"同一件事两个主人"）。
⇒ 四半都由机器守：
  ① **引用落得住**：壳 / 尺子 / 测试里出现的每一个 `守则 §X`，X 必须在守则里**真有那一条**；
  ② **栏位齐全**：§1–§5 的每一条，**每一栏都不许空**（判据栏空 = "还没兜住" ⇒ 必须写「人眼 · 未挂」，
     ⛔ 假装有判据比没有更坏）；
  ③ **一条只在一处定义**：§5（执行层）**只写执行形态 ＋ 触点**，定义一栏必须**指回 §1–§4** 的某一条
     （原文里 §1↔§5.1 · §2.1↔§5.4 · §2.3↔§5.7 · §2.5↔§5.2 · §3.1↔§5.8 · §3.7↔§5.3 · §4.3↔§5.6
     是**七组重复**；`v3` 起收成"一处定义 ＋ 一处执行"）；
  ④ **原话可追溯**：附录 A 是**原始口述对照**（改条目前能回看原意）——⚠️ 它**不作口径**，
     且用户说过的话（改了口径的依据）必须还能在那儿找到。

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


def _rule_rows(text: str) -> list[tuple[str, list[str]]]:
    """**正文**的条目表：`[(条号, [各栏文本]), …]`（`| §2.1 | … |`）。

    ⚠️ **必须先切掉附录 A**：那儿的「原始口述对照」也是一张 `| §2.7 | 「…」 |` 形状的表，
       不切就会被当成条目行（栏位自然不全 ⇒ 判据**假红**，第一版就是这么红的）。
    """
    body = text.split("## 附录 A")[0]
    out = []
    for m in re.finditer(r"^\|\s*§(\d+(?:\.\d+)?)\s*\|.*$", body, flags=re.M):
        cells = [c.strip() for c in m.group(0).strip().strip("|").split("|")]
        out.append((m.group(1), cells))
    return out


def _rule_ids(text: str) -> set[str]:
    """守则里**真有的条目号** = 表格首格（`| §3.1 | …`）＋ 节标题（`## §3 …`）。"""
    ids = {rid for rid, _ in _rule_rows(text)}
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
def test_守则每条栏位齐全_判据不许空():
    """⭐ §1–§5 的每一条，**每一栏都不许空** —— 尤其 `判据` 栏：空 = "还没兜住"，那就得写「人眼 · 未挂」。

    ⚠️ 守则开篇自己写着"能机器判的必须挂判据"（本仓铁律：能机器判的别靠自觉）——
       这一条就是**让那句自我要求可检查**，而不是靠下次谁记得。
    ⚠️ **能证伪**：把某条的判据栏清空 / 删掉某一栏 ⇒ 本件必红。
    """
    rows = _rule_rows(_doc())
    assert rows, "规则正文没有可检查的条目；完整性由实际引用核对，不按旧条目数量判断"
    bad = [f"§{rid} 有栏位空着：{cells}" for rid, cells in rows if len(cells) < 4 or not all(cells)]
    assert not bad, "\n".join(bad)


@acc()
def test_守则的执行层只写执行形态_定义指回前面():
    """⭐ `v3` 起：**一条只在一处定义** —— §5（执行层）的「定义」栏必须指回 §1–§4 的某一条。

    ⚠️ 用户原话给的那份守则里，§5 那 10 条与 §1–§4 有**七组重复**（§1↔§5.1 · §2.1↔§5.4 ·
       §2.3↔§5.7 · §2.5↔§5.2 · §3.1↔§5.8 · §3.7↔§5.3 · §4.3↔§5.6）。两处各写一遍 =
       改一处漏一处（而**漏的那处**会变成"另一套口径"）。⇒ §5 退成"执行形态 ＋ 触点"。
    ⚠️ **能证伪**：把 §5 某条的「定义」栏改成又抄一遍规则（去掉 `§` 指向）⇒ 本件必红。
    """
    text = _doc()
    rows = [(rid, cells) for rid, cells in _rule_rows(text) if rid.startswith("5.")]
    assert rows, "执行层没有可检查的条目；数量不是规则质量或完整性的证明"
    have = _rule_ids(text)
    bad = []
    for rid, cells in rows:
        refs = re.findall(r"§(\d+(?:\.\d+)?)", cells[2]) if len(cells) > 2 else []
        if not refs:
            bad.append(f"§{rid} 的「定义」栏没有指回 §1–§4（它自己又写了一遍规则 = 第二套口径）：{cells[2]}")
        for r in refs:
            if r not in have:
                bad.append(f"§{rid} 的「定义」指向 §{r}，而守则里没有这一条")
    assert not bad, "\n".join(bad)


@acc()
def test_守则的原话可追溯_附录不作口径():
    """⭐ 守则由用户口述演化而来（且用户 2026-09-27 授权"尽可能优化原文"）⇒ 两件事必须成立：

    ① **附录 A 只是追溯**（改条目前能回看原意），且**明说"不作口径"**（⛔ 免得有人拿它当第二套规则）；
    ② ⭐ **改了哪条，依据还在**：用户说过的那几句（口径的来源）必须能在守则里找到 ——
       否则下一个人无法判断"这条是谁定的、凭什么"。
    ⚠️ **能证伪**：删掉附录 A / 去掉"不作口径"字样 / 删掉用户那几句话 ⇒ 本件必红。
    """
    text = _doc()
    assert "## 附录 A · 原始口述对照" in text, "附录 A（原始口述对照）不见了"
    assert "不作口径" in text, "附录 A 没写明「⛔ 不作口径」—— 它会被当成第二套规则"
    for quote in (
        "你是替\"使用用户\"把关的人，不是替开发自己方便的人。",       # 核心一句（正文明写）
        "抬头去看文字说明",                                          # §2.7 的来源（用户报障原话）
        "尽可能优化原文",                                             # 用户授权改原文的原话
        "重构为更标准的",                                             # 守则由来的原话
    ):
        assert quote in text, f"用户口述的关键句不见了（改了哪条就说不清依据）：{quote!r}"
    # ⭐ 本仓补充的条目必须标明「这是后加的」，别混成用户原话
    assert re.search(r"\[补·\d{4}-\d{2}-\d{2}\]", text), \
        "补充条目丢了来源标记（`[补·日期]`）—— 要让下一个人一眼看出哪些是用户口径、哪些是本仓补充"
