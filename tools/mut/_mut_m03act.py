"""**反向灵敏度**：证明 `test_wired_m03_action.py`（`§19` 批 4 小轮③ 搬的 8 条壳侧断言）**真有区分力**。

做法：逐条把实现**改坏** → 确认**对应的那条断言变红** → 全部复原（**MD5 逐字节校验**）。
⚠️ 若某条变异**没能让断言变红** ⇒ 那条断言是**假绿** ⇒ 脚本报错退出。
⚠️ 子进程必须设 `ACC_RESULTS_PATH`（否则每处变异把权威 `acc_results.json` 冲成单条）
   与 `PYTHONIOENCODING=utf-8`（否则 Windows 上 GBK 解码假红）—— 见 `_mut_m03list.py` 的说明。
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))  # ⭐ `TAIL-58` 分目录：shell_source 在 audit/
from shell_source import SHELL_PATH as SHELL, pick  # noqa: F401  ← `P4`① 读取点收敛
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
TEST = "tests/test_wired_m03_action.py"

# (说明, 文件, 原文, 改成, 应变红的断言名)
MUTS: list[tuple[str, Path, str, str, str]] = [
    (
        "M1 编辑/删除不再绑「手动行」（i8 抓取行会拿到写入口）",
        SHELL,
        "if(n.manual) L.push(",
        "if(true) L.push(",
        "test_壳里操作列_i8行无编辑删除_手动行才有",
    ),
    (
        "M2 撤销付款不再要求「有生效流水」（没有流水的行也能撤）",
        SHELL,
        "if(ntHasFlow(n)) L.push(",
        "if(true) L.push(",
        "test_壳里有生效流水才出撤销付款且单条就地开窗",
    ),
    (
        "M3 多条流水跳到错的页（不再收敛到这一单）",
        SHELL,
        "go('m05');",
        "go('m03');",
        "test_壳里多条生效流水跳流水页且只筛这一单",
    ),
    (
        "M4 查看关联不再列「已撤销」流水（去向看不全）",
        SHELL,
        "const live=flows.filter(f=>!f.voided), voided=flows.filter(f=>f.voided);",
        "const live=flows.filter(f=>!f.voided), voided=[];",
        "test_壳里查看关联是纯只读且流水含已撤销",
    ),
    (
        "M5 集采实际供应商不再分岔（空值也当有值渲染）",
        SHELL,
        "['集采实际供应商',n.sup?",
        "['集采实际供应商',n.sup||'',",
        "test_壳里查看关联不臆造集采取值",
    ),
    (
        "M6 草稿行「录入人」变成可手填（不再取当前登录用户）",
        SHELL,
        # ⚠️ 锚点必须**带上下文**：`${esc(CUR.name)}` 全文命中 5 次（别的页也在用），
        #    只带它会被脚本按"未验证"正确地拒掉（2026-09-19 实测）。
        "readonly'}></td>\n    <td class=\"sm\">${esc(CUR.name)}</td>",
        "readonly'}></td>\n    <td class=\"sm\">手填</td>",
        "test_壳里草稿行统计结算只读且录入人不由手填",
    ),
    (
        "M7 统计结算格永远黄底（不按留痕判）",
        SHELL,
        "hasT(n,'统计结算金额')?'ed':''",
        "'ed'",
        "test_壳里统计两列是行内可改格且未手改不黄底",
    ),
    (
        "M8 留痕读口恒假（手改过的格子不再黄底）",
        SHELL,
        "const impManSS=n=>hasT(n,'统计结算金额');",
        "const impManSS=n=>false;",
        "test_壳里手改过的统计格黄底且判据是留痕",
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
        cwd=str(ROOT / "backend"), capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env,
    )
    return r.returncode == 0


def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in {m[1] for m in MUTS}}
    hit = 0
    for desc, path, old, new, case in MUTS:
        # ⚠️ 2026-09-19（性能 `P4`② 三刀真拆）：壳已拆成多件（`web/shell/*.js`）⇒ 锚点在哪件就改哪件。
        path = pick(path, old, new)
        before.setdefault(path, (path.read_bytes(), hashlib.md5(path.read_bytes()).hexdigest()))
        t = path.read_text(encoding="utf-8")
        if t.count(old) != 1:
            print(f"  ⛔ {desc} —— 锚点命中 {t.count(old)} 次（期望 1）⇒ **未验证**")
            continue
        path.write_text(t.replace(old, new), encoding="utf-8", newline="\n")
        red = not run_one(case)
        path.write_text(before[path][0].decode("utf-8"), encoding="utf-8", newline="\n")
        print(("  ✅ " if red else "  ⛔ 未命中 ") + desc + f"  → `{case}` " + ("变红" if red else "**仍是绿的**"))
        hit += red

    print()
    ok = all(md5(p) == h for p, (_, h) in before.items())
    print(f"  命中 {hit}/{len(MUTS)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 全部复原' if ok else '❌ 有文件没复原'}")
    return 0 if (hit == len(MUTS) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
