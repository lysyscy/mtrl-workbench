"""**反向灵敏度**：证明 `test_wired_m03_pay.py`（`§19` 批 4 · S4⑤ 搬的 9 条壳侧断言）**真有区分力**。

做法：逐条把实现**改坏** → 确认**对应的那条断言变红** → 全部复原（**MD5 逐字节校验**）。
⚠️ 若某条变异**没能让断言变红** ⇒ 那条断言是**假绿** ⇒ 脚本报错退出。

⚠️ 一律走 **bytes**（`index.html` = **CRLF**；`notice_actions.py` = **LF**）：按目标文件行尾归一后再替换，
   还原也用**原 bytes** —— 用 `write_text(newline=…)` 会把 CRLF 静默换成 LF ⇒ MD5 假 BAD。
⚠️ 子进程必须设 `ACC_RESULTS_PATH`（否则每处变异把权威 `acc_results.json` 冲成单条）
   与 `PYTHONIOENCODING=utf-8`（否则 Windows 上 GBK 解码假红）—— 见 `_mut_m03list.py` 的说明。
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BE = ROOT / "backend"
SHELL = BE / "app" / "web" / "index.html"
ACTIONS = BE / "app" / "mod03_notice" / "notice_actions.py"
PY = BE / ".venv" / "Scripts" / "python.exe"
TEST = "tests/test_wired_m03_pay.py"


def _b(s: str) -> bytes:
    """把源码片段编成 **LF** bytes（脚本里一律按 LF 写片段，匹配前再按目标文件归一）。"""
    return s.replace("\r\n", "\n").encode("utf-8")


def _fit(fragment: bytes, sample: bytes) -> bytes:
    """把 LF 片段转成**与目标文件一致**的行尾（目标含 CRLF ⇒ 转 CRLF，否则原样）。"""
    if b"\r\n" in sample:
        return fragment.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return fragment.replace(b"\r\n", b"\n")


# (说明, 文件, 原文（LF）, 改成（LF）, 应变红的用例名)
MUTS: list[tuple[str, Path, bytes, bytes, str]] = [
    (
        "M1 不可付行不再算「bad」（「确认付款」永远可点）",
        SHELL,
        _b("const bad=rows.filter(n=>!(n.astat==='已批'&&payEff(n)>0));"),
        _b("const bad=[];"),
        "test_壳里存在不可付行则确认付款禁用并给原因与解决路径",
    ),
    (
        "M2 提交时不再兜底拦「本次应付为 0」",
        SHELL,
        _b("if(can<=0){ errs.push("),
        _b("if(false){ errs.push("),
        "test_壳里本次应付为0也不可付",
    ),
    (
        "M3 付款方式取不到不再兜底「现汇」",
        ACTIONS,
        _b('    return str((plan_methods or {}).get(str(bill_no or "").strip()) or "") or "现汇"'),
        _b('    return str((plan_methods or {}).get(str(bill_no or "").strip()) or "")'),
        "test_付款方式默认取付款计划取不到兜底现汇",
    ),
    (
        "M4 付款候选不再排除撤单行（准入出口被放宽）",
        SHELL,
        _b("const ntPayCand=n=>ntLive(n)&&!ntVoid(n);"),
        _b("const ntPayCand=n=>ntLive(n);"),
        "test_壳里撤单行与剔除行不得进入付款",
    ),
    (
        "M5 「移出本次付款」变成清空整批（不只去掉该行）",
        SHELL,
        # ⚠️ 锚点**必须带上下文**：`pickSet.delete(id); render();` 全文命中 2 次（勾选行也在用），
        #    只带它会被脚本按"未验证"正确拒掉（2026-09-19 实测）。
        _b("batchPayDel:t=>{ const id=t.dataset.id, n=NO.find(x=>x.id===id);\n   pickSet.delete(id); render();"),
        _b("batchPayDel:t=>{ const id=t.dataset.id, n=NO.find(x=>x.id===id);\n   pickSet.clear(); render();"),
        "test_壳里移出本次付款只去掉该行",
    ),
    (
        "M6 重建窗口时把草稿全清（其它行已填值丢失）",
        SHELL,
        _b("Object.keys(payDraft).forEach(id=>{ if(!pickSet.has(id)) delete payDraft[id]; });"),
        _b("payDraft={};"),
        "test_壳里移出后其它行已填值仍在",
    ),
    (
        "M7 提交时不再拦「超出本次应付」",
        SHELL,
        _b("if(amt>can){ errs.push("),
        _b("if(false){ errs.push("),
        "test_壳里付款金额超过本次应付被拦",
    ),
    (
        "M8 付款方式选「其他」不再要求备注",
        SHELL,
        _b("if(m==='其他'&&!rm){ errs.push("),
        _b("if(false){ errs.push("),
        "test_壳里付款方式选其他必须填备注",
    ),
    (
        "M9 「取消」里偷偷调了接口（零副作用被破坏）",
        SHELL,
        _b("batchPayCancel:()=>{ payDraft={}; closeModal(); },"),
        _b("batchPayCancel:()=>{ payDraft={}; closeModal(); API.batchPay({ids:[]}); },"),
        "test_壳里取消批量付款不调接口也不产生流水",
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
