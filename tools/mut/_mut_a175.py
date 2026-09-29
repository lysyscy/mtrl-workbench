"""守什么：**月度会大表的「首列区固定」**（守则 §5.9 核心数据一眼可见 / §4.2 别让人做错事）——
`tests/test_ux_pages.py::test_大表的首列区固定_序号与项目名称两列一起钉`（`001-55`）到底有没有区分力。

**为什么单开一件**：本批（`TAIL-175`）新写的这条判据守的是"20 列横表往右填时看得见自己在给哪个项目填"，
它在真机上由 **㉜**（`tools/probe/_shell_bigpin.py`）量**几何**；离线这条只钉**源码形态** ——
两者的"牙齿"必须各自证明 ⇒ 本件打**离线**那条（真机的反向灵敏度由 ㉜ 自己判红，见文件头）。

四靶（一次只碰一处、改完**立刻按 bytes 复原** ＋ 收尾 MD5）：
- `M1` **表头**首列摘掉 `fl`（`<th rowspan="2" class="fl">序号</th>` 退回无类）⇒ 首列跟着滚走。
- `M2` **数据行**第 2 格摘掉 `fl` ⇒ 表头浮着、行里那两格滚走（`001-52` 同款错位）。
- `M3` 那条**偏移规则**从 `calc(39px * var(--fscale))` 改成 `left:0`（"两列都贴左缘"是个很容易犯的
  想当然改法）⇒ 第 2 列会**叠住**首列的字。
- `M4` **合计行**退回不给 `leadCls`（`{leadSpan:2, leadCls:'fl'}` → `{leadSpan:2}`）⇒ 横滚时
  「合计」两个字被滚走（那一行只剩右半截数字）。

跑法：`backend\\.venv\\Scripts\\python.exe tools\\mut\\_mut_a175.py`（rc=0 = 四靶全部按预期变红且已复原）
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
NODE = "test_ux_pages.py::test_大表的首列区固定_序号与项目名称两列一起钉"

MUTATIONS: list[tuple[str, str, str, str]] = [
    (
        "M1 表头首列摘掉 `fl`（往右填时「序号」跟着滚走）",
        '<th rowspan="2" class="fl">序号</th>',
        '<th rowspan="2">序号</th>',
        NODE,
    ),
    (
        "M2 数据行第 2 格摘掉 `fl`（表头钉着、行里那两格滚走 = `001-52` 同款错位）",
        '<td class="fl sm" title="${esc(r.wh)}">',
        '<td class="sm" title="${esc(r.wh)}">',
        NODE,
    ),
    (
        "M3 偏移规则改成 `left:0`（两列都贴左缘 ⇒ 第 2 列叠住首列的字）",
        "left:calc(39px * var(--fscale))}",
        "left:0}",
        NODE,
    ),
    (
        "M4 合计行退回不给 `leadCls`（横滚时「合计」两个字被滚走）",
        "{leadSpan:2, leadCls:'fl'}",
        "{leadSpan:2}",
        NODE,
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
