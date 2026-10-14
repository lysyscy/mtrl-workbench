"""**反向灵敏度** —— `TAIL-282` / `TAIL-283` 本批**新增或改形**的判据**到底有没有区分力**。

## 为什么有这个件

2026-10-11 的双轴 `/code-review`（基点 `14d53aa`）**Standards 轴当场判红**：本批新增的 11 条用例
在 `tools/mut/` 里 **grep 0 命中** —— 违反 `docs/agents/workflow.md`「自证」与
`ops/前端设计守则-以使用用户为中心.md` §0「**新增／修改判据时按仓内流程补隔离反向灵敏度**」。
（本件就是那条硬违规的补件：⛔ 不是"为了绿而补"，而是"这些断言到底拦不拦得住退化"此前无人证明。）

## 做法（同 `_mut_m03pay.py`）

逐条把实现**改坏** → 跑**点名的那一条判据** → 必须变红 → 按**原 bytes**复原 → 末尾 MD5 逐字节校验。
⚠️ 锚点命中 0 次 ⇒ 报「**未验证**」并计入失败（⛔ 不许静默跳过 —— 静默失效是这套东西最大的坑）。

⚠️ 一律走 **bytes**（壳件 = **CRLF**）：按目标文件行尾归一后再替换，还原也用**原 bytes**。
⚠️ 子进程必须设 `ACC_RESULTS_PATH`（否则每处变异把权威 `acc_results.json` 冲成单条）
   与 `PYTHONIOENCODING=utf-8`（否则 Windows 上 GBK 解码假红）—— 同 `_mut_m03list.py` 的说明。
⚠️ 本件**不碰** `delivery/` 与凭据；壳是多件 ⇒ 锚点在哪件就改哪件（`pick`）。
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BE = ROOT / "backend"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))  # 读取点收敛：shell_source 在 audit/
from shell_source import SHELL_PATH as SHELL, pick  # noqa: E402,F401

PY = BE / ".venv" / "Scripts" / "python.exe"
APP = BE / "app"

#: 用例全名（`-k` 是子串匹配 ⇒ 一律写全节点，⛔ 别只写一半 —— 本仓踩过"只选中一半"的假绿）。
T282_DRAFT = "tests/test_tail282_pay_draft.py::test_手改拟付后重拉列表草稿不丢且按通知书记"
T282_FACT = "tests/test_tail282_pay_draft.py::test_审批额或已付额变化后旧草稿作废"
T282_PAYOK = "tests/test_tail282_pay_draft.py::test_付款成功后即使列表刷新失败也作废草稿"
T282_REVOKE = "tests/test_tail282_pay_draft.py::test_撤销成功后即使刷新失败也作废草稿且回执仍在"
T283_FIVE = "tests/test_tail283_flow.py::test_装配补五项且失联流水照常出行"
T283_EXPORT = "tests/test_tail283_flow.py::test_导出全量装配并逐格对上页面列"
T283_ZERO = "tests/test_tail283_flow.py::test_只有已撤销时导出仍写零合计且无伪数据行"
T283_COLS = "tests/test_shell_ui_workflow.py::test_付款流水补通知书五列并改对操作人与流水号"
T283_SUM = "tests/test_shell_ui_workflow.py::test_付款流水合计只加实付且导出按屏幕行序"
T283_SORT = "tests/test_shell_ui_workflow.py::test_通知书名含合计词的行不被排序钉到表尾"


def _b(s: str) -> bytes:
    """把源码片段编成 **LF** bytes（匹配前按目标文件行尾归一）。"""
    return s.replace("\r\n", "\n").encode("utf-8")


def _fit(fragment: bytes, sample: bytes) -> bytes:
    if b"\r\n" in sample:
        return fragment.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return fragment.replace(b"\r\n", b"\n")


# (说明, 文件, 原文（LF）, 改成（LF）, 应变红的用例)
MUTS: list[tuple[str, Path, bytes, bytes, str]] = [
    # ---------------------------------------------------------- TAIL-282 · 拟付草稿
    (
        "M1 覆盖又挂回行对象（供应商重拉即被冲掉 = 原故障）",
        SHELL,
        _b("const payOver=n=>payOvEntry(n)!==null;"),
        _b("const payOver=n=>n.payOv!==undefined;"),
        T282_DRAFT,
    ),
    (
        "M2 草稿不再比对金额事实（过期数照用）",
        SHELL,
        _b("if(e.approve!==f.approve||e.paid!==f.paid){ delete PAY_OV[id]; return null; }"),
        _b("if(false){ delete PAY_OV[id]; return null; }"),
        T282_FACT,
    ),
    (
        "M3 付款成功不再当瞬作废草稿（等重拉 —— 刷新失败就留着过期数）",
        SHELL,
        _b("      dropPayOv(rows.map(n=>n.id));\n"),
        _b(""),
        T282_PAYOK,
    ),
    (
        "M4 撤销成功不再作废草稿",
        SHELL,
        _b("   dropPayOv([f.nid]);\n"),
        _b(""),
        T282_REVOKE,
    ),
    # ---------------------------------------------------- TAIL-283 · 装配与导出
    (
        "M5 失联流水的审批额伪 0（「没有这个数」装成「是 0」）",
        APP / "mod05_flow" / "service.py",
        _b('"amount_approved": f"{to_money(n.amount_approved):.2f}" if n else None,'),
        _b('"amount_approved": f"{to_money(n.amount_approved):.2f}" if n else "0.00",'),
        T283_FIVE,
    ),
    (
        "M6 导出不再要全量（回到后端默认当月 ⇒ 历史月份导不出来）",
        APP / "mod05_flow" / "router.py",
        _b('load(year_month="")'),
        _b("load()"),
        T283_EXPORT,
    ),
    (
        "M7 合计又把「审批金额」并进去（每笔重复的对照数被加总）",
        APP / "report_export" / "fl_export.py",
        _b('TOTAL_KEYS: frozenset[str] = frozenset({"amount"})'),
        _b('TOTAL_KEYS: frozenset[str] = frozenset({"amount", "amount_approved"})'),
        T283_EXPORT,
    ),
    (
        "M8 全已撤销时不再写零合计行（与屏幕对不上号）",
        APP / "mod05_flow" / "router.py",
        # ⚠️ 锚点必须**带上调用那一行**：光写 `total_always=True` 会同时命中上面注释里那句说明
        #    （实测命中 2 次 ⇒ 脚本如实报「未验证」而不是硬改一处 —— 这条纪律本身要留住）。
        _b("FLOW_EFFECTIVE],\n                        total_always=True)"),
        _b("FLOW_EFFECTIVE],\n                        total_always=False)"),
        T283_ZERO,
    ),
    # ------------------------------------------- TAIL-283 · 页面列义 / 行序 / 排序
    (
        "M9 「操作人」又去取创建时间（那一列说错话的原样）",
        SHELL,
        _b("op: x.created_by || '',"),
        _b("op: x.created_at || '',"),
        T283_COLS,
    ),
    (
        "M10 关键词又拿数据库行号当流水号",
        SHELL,
        _b("(String(f.flowNo||'')+' '+flDocNo(f))"),
        _b("(String(f.id)+' '+flDocNo(f))"),
        T283_COLS,
    ),
    (
        "M11 单据编码又回 NO 缓存（没载入通知书列表就恒空）",
        SHELL,
        _b("const flDocNo=f=>f.doc||'';"),
        _b("const flDocNo=f=>'';"),
        T283_COLS,
    ),
    (
        "M12 合计行的金额列下标写回旧值 4（列序变了它还在加同一格）",
        SHELL,
        _b("sumRowOf(FL_THEAD, flOn, {9:"),
        _b("sumRowOf(FL_THEAD, flOn, {4:"),
        T283_SUM,
    ),
    (
        "M13 导出不再按屏幕行序（去掉「付款流水」那一路的 ids 出口）",
        SHELL,
        _b("ids: () => flDomIds(), "),
        _b(""),
        T283_SUM,
    ),
    (
        "M14 排序又扫整行文本认「合计行」（名称里带「合计」的普通行被钉表尾）",
        SHELL,
        _b("/合计|总计|小计/.test(_plain(firstTd))"),
        _b("/合计|总计|小计/.test(_plain(r))"),
        T283_SORT,
    ),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one(case: str) -> bool:
    env = {**os.environ,
           "ACC_RESULTS_PATH": "../artifacts/_mut_acc_results.json",
           "PYTHONIOENCODING": "utf-8",
           "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([str(PY), "-m", "pytest", "-q", case],
                       cwd=str(BE), capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    return r.returncode == 0


def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in {m[1] for m in MUTS}}
    hit = 0
    for desc, path, old_lf, new_lf, case in MUTS:
        path = pick(path, old_lf.decode("utf-8"), new_lf.decode("utf-8"))
        before.setdefault(path, (path.read_bytes(), md5(path)))
        src = path.read_bytes()
        old, new = _fit(old_lf, src), _fit(new_lf, src)
        n = src.count(old)
        if n != 1:
            print(f"  ⛔ {desc} —— 锚点命中 {n} 次（期望 1）⇒ **未验证**")
            continue
        path.write_bytes(src.replace(old, new, 1))
        red = not run_one(case)
        path.write_bytes(src)                      # 逐条按原 bytes 还原
        print(("  ✅ " if red else "  ⛔ 未命中 ") + desc
              + f"  → `{case.rsplit('::', 1)[-1]}` " + ("变红" if red else "**仍是绿的**"))
        hit += red

    print()
    ok = all(md5(p) == h for p, (_, h) in before.items())
    print(f"  命中 {hit}/{len(MUTS)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 全部复原' if ok else '❌ 有文件没复原'}")
    return 0 if (hit == len(MUTS) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
