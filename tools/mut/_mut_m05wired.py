"""反向灵敏度自检 —— `tests/test_wired_m05.py` 那批断言**到底有没有区分力**。

把实现故意改坏（5 处），确认**对应的**断言真的变红；随后**逐字节复原**（MD5 校验）。
⚠️ 只信「改坏后变红」这一件事：跑一遍全绿证明不了判据有效。

跑法：`backend/.venv/Scripts/python.exe tools/_mut_m05wired.py`（rc=0 = 全部按预期变红且已复原）
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))  # ⭐ `TAIL-58` 分目录：shell_source 在 audit/
from shell_source import SHELL_PATH as SHELL, pick  # noqa: F401  ← `P4`① 读取点收敛
PY = str(BACKEND / ".venv" / "Scripts" / "python.exe")

MUTATIONS: list[tuple[str, str, str, str]] = [
    (
        "M1 欠款又回到「前端自算」",
        "  const d = M05.debt || {};",
        "  const d = {}; const 辅材=N2(NO.filter(n=>ntLive(n)&&n.cat==='辅材').reduce((a,n)=>a+(n.ss-n.sp),0));",
        "test_欠款台账统计不再由前端自算",
    ),
    (
        "M2 台账行又回前端按月拼",
        "const ledRows=(sc,proj)=>{ const side=m05Side(sc); if(!side) return [];",
        "const ledRows=(sc,proj)=>{ const side=null; const ms=NO.filter(n=>ntLive(n)&&n.cat===sc&&ntProjKey(n)===proj).map(ntYm); if(!side) return [];",
        "test_欠款台账统计不再由前端自算",
    ),
    (
        "M3 撤销又变成「只改内存」",
        "    m05Act(()=>API.flowRevoke(f.id, rs),",
        "    f.voided=true; f.reason=rs; render(); m05Act(()=>API.flowRevoke(f.id, rs),",
        "test_写动作不許用本地赋值冒充落库",
    ),
    (
        "M4 机械结算项**又退回取零出口**（接线后必须读真源）",
        ": N2(machSettleOf(k)",
        ": N2(m05MechSettle(k)",
        "test_机械结算源已接线_读真源",
    ),
    # ⭐ 2026-09-28（`TAIL-141` · 方案 `B`）台账**显示层**重设计的三处高危回退（都能"看着更整齐"地改回去）
    (
        "M5 表尾又退回「合计：」（「现在欠多少」又变成一个没人读得懂的格子）",
        "截至 ${esc(upto)}",
        "'<b>合计：</b>'",
        "test_台账的现状数_截至行与入口名都钉住",
    ),
    (
        "M6 两个期初录入按钮又变成**同名并排**（§4.4：点错就录到错口径）",
        ">＋ 录入${sc}期初</button>",
        ">＋ 录入期初占位行</button>",
        "test_台账的现状数_截至行与入口名都钉住",
    ),
    (
        "M7 空月压暗被摘掉（台账空月也出行 ⇒ 哪个月真发生过事看不出来）",
        "const z=!r.open&&!N2(r.s)&&!N2(r.p)&&!String(r.note||'').trim();",
        "const z=false;",
        "test_台账的现状数_截至行与入口名都钉住",
    ),
    # ⭐ 2026-09-28（`TAIL-142`）卡头按钮：两条最容易被"顺手简化"掉的
    (
        "M8 点开不变样（`on` 态被摘掉 ⇒ 用户看不出点上没有）",
        """class="btn${pjIsOpen('ledPj')?' on':''}\"""",
        """class="btn\"""",
        "test_台账卡头按钮分组与点开有反馈都钉住",
    ),
    (
        "M9 「导出总欠款」的范围按钮被挪出面板（又变成「点按钮后跑别处选项目」）",
        'data-act="debtPick"',
        'data-act="debtPickMoved"',
        "test_台账卡头按钮分组与点开有反馈都钉住",
    ),
    (
        "M10 「看哪个项目」那条从表格上方被拿掉（控件又离开了它管的那两张表）",
        '<span class="mut sm">看哪个项目（两侧共用）</span>',
        '<span class="mut sm">看项目</span>',
        "test_台账卡头按钮分组与点开有反馈都钉住",
    ),
    # ⭐ 2026-09-29（`A1` 逐页 · 用户「你自己排个计划一页一页的看吧」）
    (
        "M11 台账当前欠款数值丢失",
        "${MONEY(cur)}",
        "${MONEY(0)}",
        "test_台账的现状数_截至行与入口名都钉住",
    ),
    (
        "M12 卡头按钮又掉出右侧工具区（`.sp` 提前闭合 ⇒ 同一条守则的第二种形态）",
        "撤销必须填原因</span>",
        "撤销必须填原因</span></span>",
        "test_ux_pages.py::test_卡头里的按钮都在右侧工具区",
    ),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one(test_name: str) -> tuple[bool, str]:
    """跑**一条**判据。入参可以只给判据名（默认落在本件），也可以给 `文件.py::判据名`
    （⭐ 2026-09-29 起支持 —— 卡头形态那条判据在 `test_ux_pages.py` 里，但它是本页的高危回退点）。"""
    node = test_name if "::" in test_name else f"test_wired_m05.py::{test_name}"
    r = subprocess.run(
        [PY, "-m", "pytest", "-q", f"tests/{node}"],
        cwd=str(BACKEND), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return r.returncode == 0, (r.stdout or "")[-260:]


def main() -> int:
    before = SHELL.read_bytes()
    hits = 0
    for name, old, new, test_name in MUTATIONS:
        # ⚠️ 2026-09-19（性能 `P4`② 三刀真拆）：壳已拆成多件（`web/shell/*.js`）⇒ **锚点在哪件就改哪件**。
        #    ⛔ 复原必须用**那一件的**原字节（拿 `index.html` 的字节写进 js 件会把件写坏）。
        sh = pick(SHELL, old, new)
        sh0 = sh.read_bytes()
        text = sh.read_text(encoding="utf-8")
        if old not in text:
            print(f"⛔ {name}：**变异串没找到**（实现已改？）—— 本项作废")
            sh.write_bytes(sh0)
            continue
        sh.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
        passed, tail = run_one(test_name)
        sh.write_bytes(sh0)                          # 每条改完立刻复原，避免互相污染
        if passed:
            print(f"❌ {name}：改坏了却**仍然全绿** ⇒ 该断言是假绿\n{tail}")
        else:
            print(f"✅ {name}：对应断言**变红**（有区分力）")
            hits += 1

    ok = md5(SHELL) == hashlib.md5(before).hexdigest()
    print("\n  复原校验（MD5 逐字节）：", "✅ 已复原" if ok else "❌ 没复原！")
    print(f"\n结论：{hits}/{len(MUTATIONS)} 命中" + ("（rc=0）" if ok and hits == len(MUTATIONS) else "（需处理）"))
    return 0 if (ok and hits == len(MUTATIONS)) else 1


if __name__ == "__main__":
    sys.exit(main())
