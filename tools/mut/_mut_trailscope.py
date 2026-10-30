"""守什么：`TAIL-21` 的**留痕范围判据**（`tests/test_trail_scope.py`）—— 证明它**真会红**，不是纸面清单。

**为什么单开一件**：本仓纪律 = 「新增 / 收紧判据 ⇒ 同批证明它**改坏了会红**」。
这条判据的形状特别容易变成哑的：它断的是**有无留痕**（`session.added` 里有没有 `ProjectFieldLog`）
⇒ 只要"写留痕"那几行走不到，断言可能**静默成立**（那就成了"永远不红"的假绿）。

三靶（一次只碰一处、改完**立刻按 bytes 复原** ＋ 收尾 MD5 总校验）：

- `M1` 往 `set_disp` 里塞一条留痕 ⇒ 「改展示名不写留痕」**必红**（展示名是显示别名，§9.3 只管全名/状态/类型）。
- `M2` 摘掉 `rename_full` 的 `log_field` 调用 ⇒ 「改全名必留一条」**必红**（留痕是"是否手改"的唯一事实来源）。
- `M3` 在**别的件**里直造 `ProjectFieldLog` ⇒ 「构造点只许一处」**必红**（绕过唯一出口 = 范围失控）。

跑法：`backend\\.venv\\Scripts\\python.exe tools\\mut\\_mut_trailscope.py`（rc=0 = 三靶全按预期）
"""
from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir, finish_run as _finish_run

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
PY = str(BACKEND / ".venv" / "Scripts" / "python.exe")
REPO_PY = BACKEND / "app" / "mod01_projects" / "repository.py"
DOMAIN_PY = BACKEND / "app" / "mod01_projects" / "domain.py"

NODE_NO_TRAIL = "test_trail_scope.py::test_改展示名与关键词不写留痕"
NODE_MUST_TRAIL = "test_trail_scope.py::test_改全名与状态各写一条留痕且字段名在白名单里"
NODE_WRITER = "test_trail_scope.py::test_ProjectFieldLog只许在唯一出口里构造"

#: (说明, 靶件, 被替换的原文（"" ⇒ 追加到件尾）, 替换成, 判据节点, 期望变红?)
MUTATIONS: list[tuple[str, Path, str, str, str, bool]] = [
    (
        "M1 往 `set_disp` 里塞一条留痕（展示名本该**不留痕**）",
        REPO_PY,
        '    project.disp = (disp or "").strip()',
        '    project.disp = (disp or "").strip()\n'
        '    log_field(session, project, field="disp", old_value="",\n'
        '              new_value=project.disp, changed_by="mut")',
        NODE_NO_TRAIL,
        True,
    ),
    (
        "M2 摘掉 `rename_full` 的留痕（全名本该**留痕**）",
        REPO_PY,
        '    log_field(\n'
        '        session, project, field="name_full", old_value=old, new_value=new_full,'
        ' changed_by=changed_by\n'
        '    )\n',
        "    pass\n",
        NODE_MUST_TRAIL,
        True,
    ),
    (
        "M3 在别的件里**直造** `ProjectFieldLog`（绕过唯一出口）",
        DOMAIN_PY,
        "",
        # ⚠️ 第一版这里写成 `return ProjectFieldLog`（**没有括号**）⇒ 判据扫的是 `ProjectFieldLog(` ⇒
        #    扫描面里根本没出现 ⇒ 「改坏了却全绿」**看起来像判据没牙**。⭐ 老课：变异没命中先怀疑靶。
        'def _mut_direct_log():\n'
        '    from app.mod01_projects.models import ProjectFieldLog\n'
        '    return ProjectFieldLog(project_id=0, field="", old_value="", new_value="", changed_by="")\n',
        NODE_WRITER,
        True,
    ),
]


def run_one(node: str) -> bool:
    '跑一条判据 ⇒ True = **通过**（⚠️ "没跑起来"另判 —— 那正是"假绿"的一种）。'
    import os
    env = {**os.environ,
           "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run(
        [PY, "-m", "pytest", "-q", f"tests/{node}"],
        cwd=str(BACKEND), capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env,
    )
    out = (r.stdout or "") + (r.stderr or "")
    assert "no tests ran" not in out, f"判据节点没跑起来（名字写错了？）：{node}"
    return r.returncode == 0


def _apply(path: Path, old: str, new: str) -> None:
    """把变异落地 —— 原文为空 ⇒ **追加到件尾**；否则**替换恰好一处**（⛔ 别用 count=0 的锚点）。"""
    text = path.read_text(encoding="utf-8")
    if not old:
        path.write_text(text.rstrip("\n") + "\n\n\n" + new, encoding="utf-8", newline="\n")
        return
    n = text.count(old)
    assert n == 1, f"锚点在 {path.name} 里命中 {n} 次（期望 1）⇒ **未验证**：{old[:60]!r}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def main() -> int:
    before = {p: p.read_bytes() for _, p, _, _, _, _ in MUTATIONS}
    hits = 0
    for name, target, old, new, node, expect_red in MUTATIONS:
        raw = target.read_bytes()                     # ⭐ 每靶**写前重读盘**
        try:
            _apply(target, old, new)
            passed = run_one(node)
        finally:
            target.write_bytes(raw)                   # ⭐ 每条改完立刻复原
        if expect_red and not passed:
            print(f"✅ {name}：对应断言**变红**（有区分力）")
            hits += 1
        else:
            print(f"❌ {name}：改坏了却**仍然全绿** ⇒ 该断言没有区分力")
    ok = all(
        hashlib.md5(p.read_bytes()).hexdigest() == hashlib.md5(b).hexdigest() for p, b in before.items()
    )
    print("\n  复原校验（MD5 逐字节）：", "✅ 已复原" if ok else "❌ 没复原！")
    print(f"\n结论：{hits}/{len(MUTATIONS)} 命中" + ("（rc=0）" if ok and hits == len(MUTATIONS) else "（需处理）"))
    return 0 if (ok and hits == len(MUTATIONS)) else 1


if __name__ == "__main__":
    sys.exit(_finish_run(main()))
