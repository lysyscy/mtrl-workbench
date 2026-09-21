"""**反向灵敏度**：证明「看板接真数据」（`§19` 批 5）那批断言**真有区分力**。

做法：逐条把实现**改坏** → 确认**对应的那条断言变红** → 全部复原（**MD5 逐字节校验**）。
⚠️ 若某条变异**没能让断言变红** ⇒ 那条断言是**假绿** ⇒ 脚本报错退出。

⚠️ 一律走 **bytes**：`index.html` = **CRLF**，`core.js` / `service.py` = **LF**
   ⇒ 按目标文件行尾归一后再替换，还原也用**原 bytes**（用 `write_text` 会把 CRLF 静默换成 LF ⇒ MD5 假 BAD）。

⚠️ **本脚本覆盖不到的一处（如实记，⛔ 不假装有）**：`service.run_counts` 那句 SQL 的
   **月份条件**只有上面 `001-04` 的**结构断言**管着（认源码字符串），**没有行为级断言** ——
   因为库级断言会打在**共用的测试库**上，"本月已有 20 条成功抓取"是既有数据，
   插一行旧月份的记录**改变不了结论** ⇒ 那种用例**没有区分力**（这正是本脚本存在的意义：
   把"看着有断言"和"真有区分力"分开）。行为级的那一半由真机自检 `tools/_shell_home.py` 的 ⑦ 承担。

用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_mut_home_wired.py`
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BE = ROOT / "backend"
from shell_source import SHELL_PATH as SHELL, pick  # noqa: F401  ← `P4`① 读取点收敛
CORE = BE / "app" / "web" / "shell" / "core.js"
SVC = BE / "app" / "home" / "service.py"
PY = BE / ".venv" / "Scripts" / "python.exe"
TEST = "tests/test_acc_home_todo.py"


def _b(s: str) -> bytes:
    """把源码片段编成 **LF** bytes（匹配前再按目标文件归一）。"""
    return s.replace("\r\n", "\n").encode("utf-8")


def _fit(fragment: bytes, sample: bytes) -> bytes:
    """把 LF 片段转成**与目标文件一致**的行尾。"""
    if b"\r\n" in sample:
        return fragment.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return fragment.replace(b"\r\n", b"\n")


# (说明, 文件, 原文（LF）, 改成（LF）, 应变红的用例名)
MUTS: list[tuple[str, Path, bytes, bytes, str]] = [
    # ---------------------------------------------------------------- 壳侧（`V.home`）
    (
        "M1 ⑤ 的数改成**写死的字面量**（模拟「口径没接」的旧样子）",
        SHELL,
        _b("tile('ntUnapproved',nUn,"),
        _b("tile('ntUnapproved',3,"),
        "test_每项数字都来自数据源不得写死",
    ),
    (
        "M2 ⑤ 的去向改回**已撤页** `m12`（差异登记）",
        SHELL,
        _b("'差异一律落在库存单据的<b>调整单</b>上（差异表由系统按调整单算） · ','m08','去库存单据'"),
        _b("'差异状态 = 待核对 · ','m12','去差异登记'"),
        "test_九项都可点击跳到对应页",
    ),
    (
        "M3 ⑤ 又读起 `DFs`（已撤页的恒空残片 ⇒ 谎报「没有待办」）",
        SHELL,
        _b("const nAdj=IVs.filter(iv=>adjOf(iv)).length;"),
        _b("const nAdj=DFs.filter(x=>x.status==='待核对').length;"),
        "test_集采与差异各取本域出口且不臆造不隐藏",
    ),
    (
        "M4 ⑦⑬⑭ 退回**写死的演示记录数组**（本单元要根除的那件事）",
        SHELL,
        _b("const fDone=!hErr&&HC.fetchDue===0;"),
        _b("const fDone=RUNLOG.some(r=>r.result==='成功');"),
        "test_抓取到期与失败取自执行记录",
    ),
    (
        "M5 看板**没把记账这一路**加进取数表（页面永远拿不到那三个数）",
        CORE,
        _b("  '看板计数': reloadHome,"),
        _b("  '看板计数X': reloadHome,"),
        "test_抓取到期与失败取自执行记录",
    ),
    (
        "M6 失败记录的**标签出口被改名**（⑬ 会显示成一串单号 / 空）",
        CORE,
        _b("function runFailInfo(rec) {"),
        _b("function runFailInfoX(rec) {"),
        "test_打印失败取自打印执行记录",
    ),
    (
        "M7 看板改去问**记录窗口**端点（会漏、且漏了不报错）",
        CORE,
        _b("  homeRunCounts: () => API.get('/api/home/run-counts'),"),
        _b("  homeRunCounts: () => API.get('/api/m02/fetch/records?limit=50'),"),
        "test_抓取到期与失败取自执行记录",
    ),
    (
        "M6b 失败记录的**时间格式换了写法**（与本页其它时间/`m02` 日志卡不一致）",
        CORE,
        _b("           at: String(rec.started_at || '').replace('T', ' ') };"),
        _b("           at: String(rec.started_at || '') };"),
        "test_打印失败取自打印执行记录",
    ),
    # ---------------------------------------------------------------- 后端
    (
        "M8 两类记录**混用**（打印的失败记进抓取的账）",
        SVC,
        _b('for key, run_type in (("fetchFail", RUN_FETCH), ("printFail", RUN_PRINT)):'),
        _b('for key, run_type in (("fetchFail", RUN_FETCH), ("printFail", RUN_FETCH)):'),
        "test_打印失败取自打印执行记录",
    ),
    (
        "M9 「本月是否已抓」**恒报未抓**（用户会去白顶一次 i8）",
        SVC,
        _b('counts["fetchDue"] = _safe(fetch_due, 0, errors, "fetchDue")'),
        _b('counts["fetchDue"] = 0'),
        "test_抓取到期与失败取自执行记录",
    ),
    (
        "M10 失败记录**不带回来**（只剩 0/1 ⇒ 提示里没有「表名 ＋ 时间」）",
        SVC,
        _b("            latest[key] = run_record_out(rec)"),
        _b("            latest[key] = None"),
        "test_抓取到期与失败取自执行记录",
    ),
    (
        "M11 取数失败**被静默吞掉**（不记 errors ⇒ 看板把「取不到」说成「没有待办」）",
        SVC,
        _b('        errors[key] = f"{type(exc).__name__}: {exc}"'),
        _b("        pass"),
        "test_取数失败必须如实报错不许静默吞",
    ),
    (
        "M12 SQL 少掉**本月**那一句（旧月份的成功抓取会被当成「本月已抓」）",
        SVC,
        _b('                RunRecord.started_at >= datetime.strptime(ym + "-01", "%Y-%m-%d"),'),
        _b("                RunRecord.id > 0,"),
        "test_抓取到期与失败取自执行记录",
    ),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one(case: str) -> bool:
    env = {**os.environ,
           "ACC_RESULTS_PATH": "../artifacts/_mut_acc_results.json",
           "PYTHONIOENCODING": "utf-8",
           "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run(
        [str(PY), "-m", "pytest", "-q", f"{TEST}::{case}"],
        cwd=str(BE), capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env,
    )
    return r.returncode == 0


def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in {m[1] for m in MUTS}}
    hit = 0
    for desc, path, old_lf, new_lf, case in MUTS:
        # ⚠️ 壳已拆成多件（`web/shell/*.js`）⇒ 锚点在哪件就改哪件（`pick` 收 **str** 锚点）。
        path = pick(path, old_lf.decode("utf-8"), new_lf.decode("utf-8"))
        before.setdefault(path, (path.read_bytes(), hashlib.md5(path.read_bytes()).hexdigest()))
        src = path.read_bytes()
        old, new = _fit(old_lf, src), _fit(new_lf, src)
        n = src.count(old)
        if n != 1:
            print(f"  ⛔ {desc} —— 锚点命中 {n} 次（期望 1）⇒ **未验证**")
            continue
        path.write_bytes(src.replace(old, new, 1))
        red = not run_one(case)
        path.write_bytes(src)                      # 逐条按原 bytes 还原
        print(("  ✅ " if red else "  ⛔ 未命中 ") + desc + f"  → `{case}` " + ("变红" if red else "**仍是绿的**"))
        hit += red

    print()
    ok = all(md5(p) == h for p, (_, h) in before.items())
    print(f"  命中 {hit}/{len(MUTS)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 全部复原' if ok else '❌ 有文件没复原'}")
    return 0 if (hit == len(MUTS) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
