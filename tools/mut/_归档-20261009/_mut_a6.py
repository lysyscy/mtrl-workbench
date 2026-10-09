"""守什么：**`m01` 项目档案那两条「会让人卡住 / 看不懂」的守卫**（守则 §2.1 §4.2 §1.1 §2.5 §2.4）——
`tests/test_ux_pages.py::test_空态指路的按钮名必须真实存在`（`001-56`）与
`::test_删除确认里不许把要求句甩给用户`（`001-57`）到底有没有区分力。

**为什么单开一件**：这两条都是 `A6`（2026-09-29 逐页 `m01`）**新写**的守卫；本仓纪律 = 新写/收紧判据
⇒ 同批证明它**改坏了会红**。⚠️ 两条判据各有**两半**（正向 ＋ 墓碑）⇒ 四靶把两半各自打一次。

九靶（一次只碰一处、改完**立刻按 bytes 复原** ＋ 收尾 MD5）：
- `M1` `m01` 空态指路改回**指向不存在的按钮**的旧句 ⇒ `001-56` 必红（墓碑那半）。
- `M2` 把「同步常用项目列表」这枚按钮的**标题文案**换掉 ⇒ `001-56` 必红（"指路点名的入口真的存在"那半）。
- `M3` 删除确认那句改回《说明书》的要求句 ⇒ `001-57` 必红（墓碑那半）。
- `M4` 删掉人话后果那半（「删除不可撤销」）⇒ `001-57` 必红（"必须留下人话后果"那半）。
- `M5` `m03` 手动行那处改回要求句 ⇒ `001-57` 必红（⭐ 专打"判据是不是**一般式**" —— 只钉 `m01` 的实现会漏它）。
- `M6` `m01` 的「确认删除」退回可点 ⇒ `001-58` 必红（"点不通的必须置灰"那半）。
- `M7` `m01` 把那句**可见的**理由删掉 ⇒ `001-58` 必红（"理由要看得见"那半）。
- `M8` `m05` 期初行改回「软删留痕」⇒ `001-59` 必红（假的安全感）。
- `M9` `m14`「硬规矩」表改回改判前的「按类别分」⇒ `001-59` 必红。

跑法：`backend\\.venv\\Scripts\\python.exe tools\\mut\\_mut_a6.py`（rc=0 = 四靶全部按预期变红且已复原）
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(ROOT / "tools" / "audit"))
from shell_source import SHELL_PATH as SHELL, pick  # noqa: E402

PY = str(BACKEND / ".venv" / "Scripts" / "python.exe")
N1 = "test_ux_pages.py::test_空态指路的按钮名必须真实存在"
N2 = "test_ux_pages.py::test_删除确认里不许把要求句甩给用户"
N3 = "test_ux_pages.py::test_点不通的按钮必须置灰而且理由要看得见"
N4 = "test_ux_pages.py::test_删除分档的界面说法必须与定案一致"

MUTATIONS: list[tuple[str, str, str, str]] = [
    (
        "M1 `m01` 空态指路改回**指向不存在的按钮**的旧句（用户按着它找不到东西）",
        "换个筛选条件；或点右上角「同步常用项目列表」「同步仓库名单」，从 i8 拉项目 / 仓库进来即自动建档",
        "换个筛选条件，或用右上角「＋ 新增项目」建档",
        N1,
    ),
    (
        "M2 把「同步常用项目列表」那枚按钮的标题换掉（指路点名的入口在壳里认不出来了）",
        'data-act="syncPj" title="从 i8 拉最新的常用项目列表',
        'data-act="syncPj" title="同步项目列表',
        N1,
    ),
    (
        "M3 删除确认改回《说明书》的要求句（把写给实现的话甩给用户）",
        "<b>⚠️ 删除不可撤销 —— 先看清它会影响到下面哪些地方</b>",
        "<b>⚠️ 必须列出删除影响范围</b>",
        N2,
    ),
    (
        "M4 删掉人话后果那半（用户不知道删了会怎样 ⇒ §2.4）",
        "<b>⚠️ 删除不可撤销 —— 先看清它会影响到下面哪些地方</b>",
        "<b>⚠️ 删了就不能恢复</b>",
        N2,
    ),
    (
        "M5 `m03` 手动行那处改回要求句（同族第 3 例 —— 证明判据是**一般式**、不是只钉 `m01`）",
        "<b>⚠️ 删除前先看清下面这些影响</b>（关联数据 · 统计影响）—— §7.2 / §9.4。<br>${imp.message}",
        "<b>⚠️ 删除前必须列出影响范围</b>（关联数据、统计影响）—— §7.2 / §9.4。<br>${imp.message}",
        N2,
    ),
    (
        "M6 `m01` 的「确认删除」退回**可点**（用户又会走完整套流程才发现没接通）",
        'data-id="${p.id}" disabled title="这一项还没打通',
        'data-id="${p.id}" title="这一项还没打通',
        N3,
    ),
    (
        "M7 `m01` 把那句**可见的**理由删掉（只剩 `title` ⇒ 键盘 / 触屏用户看不到理由）",
        "<b>删除这一项还没打通</b>",
        "<b>删除这一项还没法用</b>",
        N3,
    ),
    (
        "M8 `m05` 期初行改回「软删留痕」（假的安全感：用户以为删了还能恢复）",
        "⚠️ 这一行会被<b>真的删掉、删了不能恢复</b>",
        "该行按<b>软删留痕</b>处理、可恢复",
        N4,
    ),
    (
        "M9 `m14`「硬规矩」表改回 §9.4 改判前的「按类别分」说法",
        "删除分档（按「删了能不能复原」分）",
        "核心数据删除是「软删 + 留痕」",
        N4,
    ),
]


def run_one(node: str) -> bool:
    """跑一条判据 ⇒ True = **通过**（⛔ 把"没跑起来"也当通过 —— 那正是"假绿"的一种）。"""
    r = subprocess.run(
        [PY, "-m", "pytest", "-q", f"tests/{node}"],
        cwd=str(BACKEND), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    assert "no tests ran" not in out, f"判据节点没跑起来（名字写错了？）：{node}"
    return r.returncode == 0


def main() -> int:
    before = SHELL.read_bytes()
    hits = 0
    for name, old, new, node in MUTATIONS:
        sh = pick(SHELL, old, new)
        sh0 = sh.read_bytes()
        text = sh.read_text(encoding="utf-8")
        if old not in text:
            print(f"⛔ {name}：**变异串没找到**（实现已改？）—— 本项作废")
            continue
        assert text.count(old) == 1, f"{name}：变异锚点命中 {text.count(old)} 次（要恰好 1 次）"
        sh.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
        passed = run_one(node)
        sh.write_bytes(sh0)                                   # ⭐ 每条改完立刻复原
        if passed:
            print(f"❌ {name}：改坏了却**仍然全绿** ⇒ 该断言是假绿")
        else:
            print(f"✅ {name}：对应断言**变红**（有区分力）")
            hits += 1
    ok = hashlib.md5(SHELL.read_bytes()).hexdigest() == hashlib.md5(before).hexdigest()
    print("\n  复原校验（MD5 逐字节）：", "✅ 已复原" if ok else "❌ 没复原！")
    print(f"\n结论：{hits}/{len(MUTATIONS)} 命中" + ("（rc=0）" if ok and hits == len(MUTATIONS) else "（需处理）"))
    return 0 if (ok and hits == len(MUTATIONS)) else 1


if __name__ == "__main__":
    sys.exit(main())
