"""**反向灵敏度**：证明 `test_wired_m08.py` 的断言**真有区分力**。

做法：逐条把实现**改坏** → 确认**对应的那条断言变红** → 全部复原（**MD5 逐字节校验**）。

⚠️ 若某条变异**没能让断言变红** ⇒ 那条断言是**假绿**（它没钉住它声称钉的东西）⇒ 脚本报错退出。
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from shell_source import SHELL_PATH as SHELL  # noqa: F401  ← `P4`① 读取点收敛
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
TEST = "tests/test_wired_m08.py"

# (说明, 文件, 原文, 改成, 应变红的断言名)
MUTS: list[tuple[str, Path, str, str, str]] = [
    (
        "M1 适配层金额不过 `N0()`（后端出字符串 ⇒ 会拼进求和）",
        SHELL,
        "qty: N0(r.qty), px: N0(r.price_excl), pi: N0(r.price_incl), amt: N0(r.amount),",
        "qty: r.qty, px: r.price_excl, pi: r.price_incl, amt: r.amount,",
        "test_适配层把金额转成数字",
    ),
    (
        "M2 适配层 `id` 不转字符串（`===` 比较会静默找不到行）",
        SHELL,
        "    id: String(r.id),\n    docNo:",
        "    id: r.id,\n    docNo:",
        "test_适配层把id转成字符串",
    ),
    (
        "M3 `reloadInv()` 不再重算 `PROC_PJS`（候选会永远空）",
        SHELL,
        "  PROC_PJS = uniqBy(IVs, iv => iv.wh);\n",
        "",
        "test_加载时求值的两处已改为重算",
    ),
    (
        "M4 仓库候选退回演示主数据 `WHs`（选了也筛不出行）",
        SHELL,
        "projPanel({list:()=>pjSort(PROC_PJS),selected:()=>invWhs",
        "projPanel({list:()=>pjSort(WHs.map(w=>w.name)),selected:()=>invWhs",
        "test_仓库候选与数据源同源",
    ),
    (
        "M5 打调整单退回**本地假成功**（只改内存、没落库）",
        SHELL,
        "await ivAct(()=>API.m08Adjust(iv.id,{amount:v,remark:rs}),",
        "if(v||rs){ ADs.push({id:'X',ivid:iv.id,newAmt:Number(v),remark:rs,op:'',time:'',trail:[]});",
        "test_打调整单走后端且不在前端复写判据",
    ),
    (
        "M6 留痕退回**数组数组**（留痕卡会渲染一排 undefined）",
        SHELL,
        "trail: [{ field: '金额', before: N0(a.before_amount), after: N0(a.amount) }],",
        "trail: [['金额', a.before_amount, a.amount]],",
        "test_留痕转成对象数组",
    ),
    (
        "M7 演示数组 `IV` 复活（页面会渲染演示数据）",
        SHELL,
        "let IVs=[], ADs=[];",
        "const IV = [];\nlet IVs=[], ADs=[];",
        "test_演示数组已删",
    ),
    (
        "M8 抓取端点不再要 `confirm`（静默抓取 ⇒ 会顶号）",
        ROOT / "backend" / "app" / "mod08_inv" / "router.py",
        "confirmed=req.confirm",
        "confirmed=True",
        "test_抓取端点必须显式确认",
    ),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one(case: str) -> bool:
    """跑单条断言 ⇒ True = 通过，False = 变红。"""
    r = subprocess.run(
        [str(PY), "-m", "pytest", "-q", f"{TEST}::{case}"],
        cwd=str(ROOT / "backend"), capture_output=True, text=True, encoding="utf-8",
    )
    return r.returncode == 0


def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in {m[1] for m in MUTS}}
    hit = 0
    for desc, path, old, new, case in MUTS:
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
