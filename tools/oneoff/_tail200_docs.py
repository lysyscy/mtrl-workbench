#!/usr/bin/env python
r"""`TAIL-200` `A` 案**落纸**（2026-09-30）：文档订正（交付面/部署/计划 §9.5③/D23）＋ `TAIL-200` 销号
＋ 账（A 4→3 · C 0→1 · 已销号 199→200）＋ 新尾巴 `TAIL-201`（C 类）＋ 口令。

⚠️ 规矩：逐处先断言命中数；计划的改动**全部在内存里做完、只写一次**（⛔ 别边读边写 —— 那样后写的
   会用**旧快照**覆盖先写的，本脚本第一版就是这么丢改动的）。
⚠️ 中文行文里的引号一律用「」。
用法：`python tools/oneoff/_tail200_docs.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
FACE = ROOT / "docs" / "delivery-surface.md"
DEPLOY = ROOT / "docs" / "deployment.md"
NL = "\r\n"

ROW4 = (
    "| `TAIL-200` | ⭐ **`U1`/`U5` 的基准从「原型」换成「壳快照」**（＝提前执行 `D23`） | "
    "**销号依据** = 用户 2026-09-30 选 `A` ⇒ 已办：① `ui_parity.py` **默认基准 = `.workbuddy/backups/` 里最新"
    "那份「壳单文件基线」**（`newest_snapshot()` 从 `shell_verify` **复用** · ⛔ 不复制一份）＋ **缺基准判红**"
    "（⛔ 不回落原型）＋ `--proto` 仍可**显式指**（历史对账 / 反向灵敏度）；② **漂移登记簿清零** —— "
    "630 条「原型基准期」历史条目归档 ⇒ `tools/oneoff/_归档-20260930/ui_parity_expected-原型基准期.txt`"
    "（⛔ 别删：那是 2026-09-20 以来几十批「零可见变化」改动的**原始理由**）；③ **量测**（换基准前先量）："
    "拿最新快照当基准 ⇒ **当场 rc=0**（`U1` 零漂移 · `U5` 44 件全逐字一致 · `U2/U3/U4` 无）＋ 拼法与 "
    "`shell_source.SHELL_PARTS` **同源** ⇒ 快照是可用基准；④ **判据** = `backend/tests/test_ui_parity_base.py`（已删 · 见 `_tail201_docs.py`）"
    "（2 条：默认基准是壳快照 / 缺基准要判红；⚠️ **刻意不绑契约面** ⇒ 四态仍 **644**）＋ **反向灵敏度** "
    "`tools/mut/_mut_uiparity.py` **2/2**；⑤ ⭐ **顺带复活一只僵尸**：`tools/mut/_mut_u5.py` 的 `_run` 没带 "
    "utf-8 ⇒ 子进程报告里的 `⚠️` 在 GBK 管道上**抛异常崩掉** ⇒ 基线**恒 rc=1**、三个靶**从来没跑过**，"
    "而 `mut_cover.py` 只查「文件在不在」查不出（同 `_mut_vs.py` · 今天第 2 只）⇒ 修好 ⇒ **3/3**；"
    "⑥ 同批订正 4 处过期口径（`shell_source.py` · `audit_common.py` ×2 · `delivery-surface.md` · "
    "`deployment.md`）；⑦ ⭐ **收益**：改壳**不必再「双边同步」**（⛔ 不用往原型抄同样的字节）＋ "
    "`ui_parity` **在目标机也能跑**（不再依赖交付面） | 2026-09-30 |"
)

ROW3 = (
    "| `TAIL-201` | ⭐ **`U1`/`U5` 与 `shell_verify` 的重叠要不要再收一次** —— 换了基准之后，"
    "`ui_parity`（逐行**对位 ＋ 登记理由**）与 `shell_verify`（逐行**多重集 ＋ 盖章**）**现在同一个基准** "
    "⇒ 同一件事**两套账** | 两边**都绿**、功能上没病 —— 只是**一事两写**：每批盖一次章 ＋ 每批登一次记"
    "（而登记条目**盖完章就成幽灵**） | 你说「退场」我就把 `U1`/`U5` 撤掉（职责全交 `shell_verify`）／"
    "说「留着」就这么过 | 随时 | ⏳ 待你一句话 |"
)

ROW3_143 = (
    "| `TAIL-201` ⭐ **`U1`/`U5` 与 `shell_verify` 重叠**（`TAIL-200` 换基准后的产物） | "
    "⏳ **待你一句话**（`C` 类 · 见 §三） | **落点** = `tools/audit/ui_parity.py`（退场 = 撤 `U1`/`U5` 两半 ＋ "
    "登记簿归档；⚠️ 代价 = 失去「逐行对位 ＋ 登记理由」那个粒度，只剩 `shell_verify` 的多重集） | "
    "触发 = 你回一句 |"
)


def _edit(t: str, pairs: list[tuple[str, str]], what: str) -> str:
    for old, new in pairs:
        n = t.count(old)
        assert n == 1, f"⛔ {what}：锚点命中 {n} 次（期望 1）—— {old[:70]!r}"
        t = t.replace(old, new, 1)
    return t


def _write(p: pathlib.Path, t: str) -> None:
    p.write_text(t.replace("\n", NL), encoding="utf-8", newline="")
    assert p.read_text(encoding="utf-8", newline="").replace("\r\n", "\n") == t, f"⛔ {p.name} 写回不一致"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    dry = not a.write

    face = _edit(FACE.read_text(encoding="utf-8", newline="").replace("\r\n", "\n"), [
        ("| `demo/材料报表自动化工作台-交互原型.html` | 文件 | **交互原型 = 规格留痕 ＋ `ui_parity` 的"
         "逐行对位基准** | ⭐ 权威（`U1` 守） |",
         "| `demo/材料报表自动化工作台-交互原型.html` | 文件 | **交互原型 = 规格留痕**（⭐ **2026-09-30** "
         "`TAIL-200` 起**不再是** `ui_parity` 的基准 —— 基准已换成**最新壳快照**） | 留痕（可作 `--proto` 的"
         "历史对账基准） |"),
        ("| 2026-09-22 | Agent | ✅ 路径可达 · 上面的目录清单与会话开始时实测一致 | "
         "结构整改期间未动交付面（除验收基线 `001-08/001-09` 两处判词纠正，已当场核对） |",
         "| 2026-09-22 | Agent | ✅ 路径可达 · 上面的目录清单与会话开始时实测一致 | "
         "结构整改期间未动交付面（除验收基线 `001-08/001-09` 两处判词纠正，已当场核对） |\n"
         "| 2026-09-30 | Agent | ⭐ **`TAIL-200`**：`ui_parity` 的基准**已换成壳快照** ⇒ 本树**不再是**它的"
         "基准（⛔ 改壳不必再往原型抄同样的字节）；本树仍要在：`验收基线.json`（完成度的机器答案）＋ "
         "《说明书》（口径原文）＋ 四检（`demo/_smoke.js`） | 本轮**未动交付面**（只读） |"),
    ], FACE.name)

    deploy = _edit(DEPLOY.read_text(encoding="utf-8", newline="").replace("\r\n", "\n"), [
        ("5. ⚠️ 交付面（WPS 那个文件夹）**不在目标机、也不在包里** ⇒ `doc_audit --ui` / `ui_parity` / "
         "`acc_report`（四态报表）**跑不了** —— 那是已知代价；要跑它们得把交付面一起弄来（另说）",
         "5. ⚠️ 交付面（WPS 那个文件夹）**不在目标机、也不在包里** ⇒ `doc_audit --ui` / `acc_report`"
         "（四态报表）**跑不了** —— 那是已知代价；要跑它们得把交付面一起弄来（另说）。\n"
         "   ⭐ **`ui_parity` 不在此列**（2026-09-30 `TAIL-200`）：它的基准 = **最新壳快照**，而那份"
         "**在包里**（`pack.ps1` ② 会带上）⇒ **目标机也能跑**（⛔ 不再需要交付面）。"),
        ("| **交付面定位** | 仓根 `.env`：`PRD_ACCEPTANCE_BASELINE=<交付面>/PRD/验收/验收基线.json`"
         "（**同一机制**：`doc_audit` 与 `_audit_face.py` 都读它） | 留空 ⇒ `doc_audit --ui` / `ui_parity` / "
         "`acc_report`（四态报表）**跑不了**（会打印「跳过 + 原因」） |",
         "| **交付面定位** | 仓根 `.env`：`PRD_ACCEPTANCE_BASELINE=<交付面>/PRD/验收/验收基线.json`"
         "（**同一机制**：`doc_audit` 与 `_audit_face.py` 都读它） | 留空 ⇒ `doc_audit --ui` / `acc_report`"
         "（四态报表）**跑不了**（会打印「跳过 + 原因」）；⚠️ **`ui_parity` 不受影响**"
         "（2026-09-30 `TAIL-200`：它的基准是**壳快照**，在包里） |"),
    ], DEPLOY.name)

    plan = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    plan = _edit(plan, [
        ('| `demo/` 原型 | `ui_parity` 的 `U1`（"壳没偷偷改交互"）无源可比 —— 按 `D23` 冻结时换基准即解 |',
         "| `demo/` 原型 | `ui_parity` 的 `U1`（「壳没偷偷改交互」）无源可比 —— ⭐ **2026-09-30 已办**"
         "（`TAIL-200` `A` 案 **提前**执行 `D23`：基准 = **最新壳快照**）⇒ 原型**不再是基准**、"
         "退成只读归档 ⇒ **这一行已解**；⚠️ 本表另两样（`验收基线.json` / 《说明书》）**照旧要在** |"),
        ('| **D23** | `demo/` 原型的退场 | **保留归档** ＋ **冻结那一刻**把 `ui_parity` 的 `U1` 基准换成'
         '"冻结版壳快照"、漂移登记簿清零（⛔ 现在不做） |',
         '| **D23** | `demo/` 原型的退场 | **保留归档** ＋ ⭐ **2026-09-30 已提前执行**（`TAIL-200` `A` 案 · '
         '用户裁定）：`ui_parity` 的 `U1`/`U5` 基准 = **`.workbuddy/backups/` 最新那份「壳单文件基线」**，'
         '原型退成只读归档；**漂移登记簿已清零**（630 条旧条目归档 ⇒ `tools/oneoff/_归档-20260930/`） |'),
        ("| `TAIL-200` ⭐ **`U1`/`U5` 基准：提前换成「壳快照」？** | ⭐ **已定裁 `A`（2026-09-30）· ⏳ 待开工**",
         "| `TAIL-200` ⭐ **`U1`/`U5` 基准：提前换成「壳快照」？** | ✅ **已办（2026-09-30 `A` 案）**"),
        ("| ✅ `TAIL-199` ⚠️ **`P5-d` 剩下的两条口径**",
         ROW3_143 + "\n| ✅ `TAIL-199` ⚠️ **`P5-d` 剩下的两条口径**"),
        ("A 类 **4** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **199** 条",
         "A 类 **3** 条 · B 类 **0** 条 · C 类 **1** 条 · 已销号 **200** 条"),
        ("A 类 **4** 条 · B 类 0 · C 类 **0** · 已销号 **199**",
         "A 类 **3** 条 · B 类 0 · C 类 **1** · 已销号 **200**"),
        ("＋ 新尾巴 **`TAIL-200`**（`U1`/`U5` 基准提前换成「壳快照」＝提前执行 `D23` —— ⭐ **已定裁 `A`"
         "（2026-09-30）· 待开工**，⭐ 建议**排在 `P4-c-a` 之前**））·",
         "—— ⭐ **`TAIL-200` 已办**（2026-09-30 `A` 案：`U1`/`U5` 基准**已换成壳快照**、登记簿已清零 · "
         "§15 §四）＋ 立 **`TAIL-201`**（C 类：`U1`/`U5` 与 `shell_verify` **重叠**，要不要索性退场 —— "
         "⚠️ 待你一句话））·"),
        ("② ⛔ **别动原型逻辑**（`D18`）—— 但 `TAIL-64` 的**双边同步**是既定例外",
         "② ⛔ **别动原型逻辑**（`D18`）—— ⭐⭐ **2026-09-30 起「双边同步」不是例外了**（`TAIL-200`："
         "`U1`/`U5` 的基准已换成**壳快照** ⇒ **改壳不用再往原型抄**；原型退成只读归档）；"
         "⚠️ 下面那条「项目按钮」例外**照旧有效**"),
    ], "计划（文本级）")

    # ── 行级：TAIL-200 从 §一 挪到 §四；§三 加一条 C 类
    lines = plan.split("\n")
    a200 = "| `TAIL-200` | ⭐ **`U1`/`U5` 的基准要不要提前从「原型」换成「壳快照」**"
    idx = next((i for i, l in enumerate(lines) if l.startswith(a200)), None)
    assert idx is not None, "⛔ §15 §一 里找不到 TAIL-200 行"
    lines.pop(idx)
    for k, ln in enumerate(lines):
        if ln.startswith("### 三、C 类"):
            for j in range(k, k + 6):
                if lines[j].startswith("| # | 事项 | 现状 | 你只需说 |"):
                    lines[j + 1:j + 1] = [ROW3]
                    break
            else:
                raise AssertionError("⛔ §三 里找不到表头行")
            break
    else:
        raise AssertionError("⛔ 找不到 §三 段")
    for k, ln in enumerate(lines):
        if ln.startswith("### 四、已销号"):
            for j in range(k, k + 6):
                if lines[j].startswith("| # | 事项 | 销号依据 | 日期 |"):
                    lines[j + 1:j + 1] = [ROW4]
                    break
            else:
                raise AssertionError("⛔ §四 里找不到表头行")
            break
    else:
        raise AssertionError("⛔ 找不到 §四 段")
    plan = "\n".join(lines)

    if dry:
        print("   ✅ 三份文本全部通过锚点断言（干跑：⛔ 未写）")
        return 0
    _write(FACE, face)
    _write(DEPLOY, deploy)
    _write(PLAN, plan)
    print("   ✅ docs/delivery-surface.md · 原型角色改「留痕」＋ 同步状态加一行")
    print("   ✅ docs/deployment.md · `ui_parity` 摘出「交付面跑不了」两处")
    print("   ✅ 计划 · §9.5③/`D23` 标「已提前执行」· TAIL-200 销号（§一→§四）· 新立 C 类 TAIL-201")
    print("   ✅ 计划 · 计数（A 3 · C 1 · 已销号 200）· 口令（余量行 ＋ 限制②「双边同步取消」）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
