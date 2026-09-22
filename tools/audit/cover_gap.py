"""判据覆盖检查（`T7`）—— **有登记的能力、口径却没人 cover**。

**为什么单独成件**：`tools/doc_audit.py` 已逼近「>600 行禁合入」线（拆分前 650 行）⇒
按工程纪律把本检查抽出；`doc_audit` 只调用、不内联。

⚠️ **只登记、不判红**（与 `T5` 同款理由）：某条能力**该不该有判据需要人判断**
（有些是叙述 / 索引 / 已取消 / 备查），门禁只留给机器能定对错的事
（幽灵用例号 / 路径 / 术语 / 状态数字）。⇒ 本模块的产物是**给人看的清单**。

判法（**两档，各自独立**）：
- **`T7a` 无判据承载**：能力行末列**没写 `ACC-*`** ⇒ 这条能力**没有任何用例认领**（最硬的一档）。
- **`T7b` 口径无人 cover**：末列虽写了 `ACC-*`（或为空），但「覆盖口径」列的每个 `§x.y(.z)`
  一个都没被任何用例的 `cover`（含判据点级 `cover`）命中 ⇒ 口径悬空。

⚠️ **`T7a` 是 2026-09-16 补的洞**（原实现只有 `T7b`）：原来只查"口径节有没有人管"，
而**口径节常被别的用例以「祖先/后代」关系命中** ⇒ 于是「**口径有人管、但这条能力本身没有判据**」
的行被**静默吞掉**。实测：`MOD-03` 18 行能力里 **9 行无用例号**，原实现只报 2 条；
全局 **42 行无用例号**，原实现只报 10 条 —— **差 32 条**正是被祖先匹配吃掉的。
⭐ 教训：**"口径被引用" ≠ "这条能力有判据"** —— 两件事必须分开查。

⚠️ **仍然查不出的一类（只能人核）**：能力行**标了 `ACC-*`，而那条用例其实没覆盖它**。
实测例：`MOD-01` 能力 2「建档向导（三类项目 · 三条链路）」标着 `ACC-PRJ-OWN-001`，
但那条只覆盖**归属判定**、**不覆盖"建档"本身**（阶段 2–4 全未实现）。
⇒ 这一类要读能力表声明 vs 用例 `points` 实际断言了什么，机器判不了。

⚠️ **`T7a` 清单会随主线推进而变短** ⇒ 输出不能是"每次都一样的一坨"（人会当噪音忽略）。
清掉的条目登记在 `tools/t7_expected.txt`（`x ` 开头 = 已清，行首两空格 = 未清），
本模块**按该文件决定每条要不要输出** —— 登记的条目从清单里消失，但**仍是显式在册**的。
⚠️ 读数文件**失败一律降级为"全部未清"**（宁可多报，不可静默少报 —— 本项目最贵的一类假绿）。
"""

from __future__ import annotations

import re
from pathlib import Path

#: 「已清」登记（**与代码同目录**）：行首 `x ` = 该条已补上判据 ⇒ 不再输出；
#: 行首两空格 / 无前缀 = 未清；`#` 开头 = 注释。
#: ⚠️ 读不到 ⇒ 视为**全部未清**（宁多报不少报）。
CLEARED_REGISTRY: Path = Path(__file__).resolve().parent / "t7_expected.txt"

#: 显式豁免：这些能力**本来就不该有判据**，理由必须写在这里（可追溯）。
#: ⚠️ 只收「文档里明写不做 / 取消 / 备查」的，**不收"暂时没做"**（那属真缺口，要留着被看见）。
#: ⚠️ 键是**能力文字的片段**（匹配前会去掉 `*` 与反引号）—— 取够长、能唯一定位那一行为准。
T7_EXEMPT: tuple[tuple[str, str], ...] = (
    ("备查 · 暂不实现", "`MOD-10` 能力 4：§5.6.2 / §5.6.3 明写「备查 · 暂不实现」"),
    ("整条取消", "`MOD-13` §7.4「提醒与督办」整条取消（`NG-04`）"),
    # ⭐ `TAIL-20`（2026-09-22）：以下四行是**指路 / 说明 / 口径声明**，无系统能力可断言。
    #    ⛔ 豁免 ≠ 缺判据——各行**含判据的话**早被认领了（同日已认领 4 行：MOD-03 L39 ·
    #    MOD-04 L36 · MOD-10 L27/L28）。新说明类行出现时照这里登记。
    ("本页只留指路", "`MOD-04` §4.3.5 第 7 项：「按计划勾选」按钮落在 `MOD-03` 页，"
                    "能力的主人 = `MOD-03` 执行侧判据；本行不含新判据"),
    ("历史保留", "`MOD-04` §4.3.6 第 8 项：标注「历史保留」—— 无系统能力可断言"),
    ("不单独建功能页", "`MOD-10` 行 1：`NG-09` 明写近期不做机械费核对，本页只做说明"),
    ("机械费仍上报", "`MOD-10` 行 4：`NG-09` 近期不做 ⇒ 口径声明；待机械费页立项时建判据"),
    ("补正机制的触发时点",
     "`MOD-12` §5.8.1：补正是**半年度对账驱动的偶发人工动作**，且 `DEV-R-05` 明写「**不设月度提醒**」"
     "（提醒整条已取消，`REQ-R15`）⇒ 系统侧**没有任何对应动作**可断言 ⇒ 属业务事实陈述，不是缺判据"),
    ("与其他补正规则的分工",
     "`MOD-12` §5.8.4：**分工对照表** —— 四行的主人分别在 §5.8.3/§5.4 · §5.7（大表「不做补正」的口径主人是 §5.7，"
     "不是本节）· §4.2.5 · §4.2.4；本节只做分工说明、**不含新判据**"),
)


def load_cleared(path: Path | None = None) -> set[str]:
    """读「已清」登记 → {`MOD-xx.md Lnn`}。读不到 ⇒ 空集（= 全部未清，宁多报）。"""
    p = path or CLEARED_REGISTRY
    if not p.exists():
        return set()
    out: set[str] = set()
    for ln in p.read_text(encoding="utf-8").splitlines():
        if not ln.startswith("x "):
            continue
        m = re.match(r"x\s+(MOD-\d+\.md)\s+L(\d+)\b", ln)
        if m:
            out.add(f"{m.group(1)} L{m.group(2)}")
    return out


def _covered_set(baseline: dict) -> set[str]:
    """全部用例（含判据点级）的 `cover` 归一值：去 `§`、去空格。"""
    covered: set[str] = set()
    for c in (baseline.get("cases") or {}).values():
        for x in c.get("cover") or ():
            covered.add(str(x).strip().lstrip("§").replace(" ", ""))
        for pt in c.get("points") or ():
            for x in str(pt.get("cover") or "").split("·"):
                v = x.strip().lstrip("§").replace(" ", "")
                if v:
                    covered.add(v)
    return covered


def check_cover_gaps(root: Path | None, baseline: dict) -> list[dict]:
    """→ 登记清单（`[]` = 无缺口）。`root` = 交付面根（找不到就返回空，不猜）。

    返回项按 `code` 分两档：
    - `T7a` = 能力行**末列没有 `ACC-*`** ⇒ 这条能力没有任何用例认领；
    - `T7b` = 能力行**存在但口径节无人 cover**（仅对**已无用例号**的行判断 —— 已标用例的行
      由人核，见模块 docstring 末段）。
    """
    if root is None:
        return []
    covered = _covered_set(baseline)
    cleared = load_cleared()
    nums = {v for v in covered if re.fullmatch(r"\d+(?:\.\d+)*", v)}

    def covered_sec(sec: str) -> bool:
        """本级命中 / 有 cover 是它的祖先 / 有 cover 是它的后代（子节点被覆盖也算）。"""
        if sec in nums:
            return True
        return any(v.startswith(sec + ".") or sec.startswith(v + ".") for v in nums)

    out: list[dict] = []
    for p in sorted((root / "PRD" / "02-功能规格").glob("MOD-*.md")):
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, ln in enumerate(lines, 1):
            if not ln.startswith("|"):
                continue
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if len(cells) < 5 or not re.fullmatch(r"\d+", cells[0]):
                continue
            has_case = bool(re.search(r"ACC-[A-Z0-9\-]+", cells[-1]))
            cap = re.sub(r"[*`]", "", cells[1])
            if any(k in cap for k, _why in T7_EXEMPT):
                continue                                   # 显式豁免（理由见 T7_EXEMPT）
            rel = f"PRD/02-功能规格/{p.name}"
            cleared_key = f"{p.name} L{i + 1}"
            # ⭐ T7a：这条能力**自己没有判据**（与"口径有没有人管"是两件事）
            #    ⚠️ 已登记的条目**不再输出**（登记见 `tools/t7_expected.txt`，仍是显式在册的）
            if not has_case and cleared_key not in cleared:
                out.append({"code": "T7a", "rel": rel, "line": i + 1,
                            "what": f"{cap[:42]} ← 无用例认领（末列没有 `ACC-*`）"})
            secs = re.findall(r"§?(\d+(?:\.\d+)+)", cells[2])
            if not secs:
                continue
            bad = [s for s in secs if not covered_sec(s)]
            if bad:
                # T7b 只对**没写用例号**的行报 —— 已标用例的行"口径悬空"属另一类问题，
                # 若一并报会把清单噪音化（已标用例却口径不符 = 需人核，见模块 docstring）。
                if has_case:
                    continue
                out.append({"code": "T7b", "rel": rel, "line": i + 1,
                            "what": f"{cap[:42]} ← §{', §'.join(bad)} 无人 cover"})
    return out


__all__ = ["T7_EXEMPT", "CLEARED_REGISTRY", "load_cleared", "check_cover_gaps"]
