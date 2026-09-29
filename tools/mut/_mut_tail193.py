"""守什么：`TAIL-193` 的**防扩散墓碑**（`tests/test_dup_guards.py`）—— 证明它**真会红**，不是一张清单。

**为什么单开一件**：本仓纪律 = 「新增/收紧判据 ⇒ 同批证明它**改坏了会红**」。
这条判据的形状特别容易变成哑的：它靠 `pattern` 匹配函数定义行 —— 正则写错（少个捕获组 / 少个转义）
就会**安静地什么都扫不到**（那就成了"清单永远对"的假绿）。

五靶（一次只碰一处、改完**立刻按 bytes 复原** ＋ 收尾 MD5 总校验）：
- `M1` `mod06_proc/importer.py` 末尾加一个 `def parse_amount` ⇒ 金额·解析族 必红。
- `M2` `mod07_setl/domain.py` 末尾加一个 `def _money`      ⇒ 金额·格式化族 必红。
- `M3` `mod04_plan/domain.py` 末尾加一个 `def match_projects` ⇒ 项目·匹配族 必红。
- `M4` `mod01_projects/domain.py` 末尾加一个 `def ym_of`   ⇒ 时间·年月族 必红。
- `M5` ⭐ **反向的反向**：`core/money.py`（= 金额族的**唯一出口**）末尾加 `def parse_amount`
  ⇒ 必须**仍然全绿**（`owner_files` 就是干这个的：在出口里改/加**不算副本**）
  ⇒ 若 M5 变红，说明 `owner_files` 形同虚设（把出口自己也当成副本了）。

跑法：`backend\\.venv\\Scripts\\python.exe tools\\mut\\_mut_tail193.py`（rc=0 = 五靶全按预期）
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
PY = str(BACKEND / ".venv" / "Scripts" / "python.exe")

NODE_NEW = "test_dup_guards.py::test_不许再长第N加1份实现"
NODE_SYNC = "test_dup_guards.py::test_登记册与现实同步_消掉副本要销号"

#: (说明, 靶件, 追加的代码, 判据节点, 期望变红?)
MUTATIONS: list[tuple[str, Path, str, str, bool]] = [
    (
        "M1 又长一份金额解析（`parse_amount`）",
        BACKEND / "app" / "mod06_proc" / "importer.py",
        "def parse_amount(raw):\n    return raw\n",
        NODE_NEW,
        True,
    ),
    (
        "M2 又长一份金额格式化（`_money`）",
        BACKEND / "app" / "mod07_setl" / "domain.py",
        "def _money(v):\n    return v\n",
        NODE_NEW,
        True,
    ),
    (
        "M3 又长一份项目匹配（`match_projects`）",
        BACKEND / "app" / "mod04_plan" / "domain.py",
        "def match_projects(rows, projects):\n    return {}\n",
        NODE_NEW,
        True,
    ),
    (
        "M4 又长一份年月（`ym_of`）",
        BACKEND / "app" / "mod01_projects" / "domain.py",
        "def ym_of(d):\n    return d\n",
        NODE_NEW,
        True,
    ),
    (
        "M5 在**唯一出口**（`core/money.py`）里加同名函数 ⇒ 必须仍绿（owner_files 生效）",
        BACKEND / "app" / "core" / "money.py",
        "def parse_amount(raw):\n    return raw\n",
        NODE_NEW,
        False,
    ),
]


def run_one(node: str) -> bool:
    """跑一条判据 ⇒ True = **通过**（⚠️ "没跑起来"另判 —— 那正是"假绿"的一种）。"""
    r = subprocess.run(
        [PY, "-m", "pytest", "-q", f"tests/{node}"],
        cwd=str(BACKEND), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    assert "no tests ran" not in out, f"判据节点没跑起来（名字写错了？）：{node}"
    return r.returncode == 0


def main() -> int:
    before = {p: p.read_bytes() for _, p, _, _, _ in MUTATIONS}
    hits = 0
    for name, target, code, node, expect_red in MUTATIONS:
        raw = target.read_bytes()                     # ⭐ 每靶**写前重读盘**
        text = target.read_text(encoding="utf-8")
        target.write_text(text.rstrip("\n") + "\n\n\n" + code, encoding="utf-8", newline="\n")
        passed = run_one(node)
        target.write_bytes(raw)                       # ⭐ 每条改完立刻复原
        want_red = expect_red
        if want_red and not passed:
            print(f"✅ {name}：对应断言**变红**（有区分力）")
            hits += 1
        elif (not want_red) and passed:
            print(f"✅ {name}：**仍绿**（出口里加东西不算副本 —— owner_files 真的在起作用）")
            hits += 1
        else:
            verdict = "改坏了却**仍然全绿**" if want_red else "**不该红却红了**（owner_files 形同虚设）"
            print(f"❌ {name}：{verdict} ⇒ 该断言有问题")
    ok = all(
        hashlib.md5(p.read_bytes()).hexdigest() == hashlib.md5(b).hexdigest() for p, b in before.items()
    )
    print("\n  复原校验（MD5 逐字节）：", "✅ 已复原" if ok else "❌ 没复原！")
    print(f"\n结论：{hits}/{len(MUTATIONS)} 命中" + ("（rc=0）" if ok and hits == len(MUTATIONS) else "（需处理）"))
    return 0 if (ok and hits == len(MUTATIONS)) else 1


if __name__ == "__main__":
    sys.exit(main())
