"""只读取证：**「数据导入」页的「项目」候选是怎么来的、为什么会渲染成 `[object Object]`**。

**为什么有它**（产品 2026-09-26 报障 · 截图）：通用导入面「项目」下拉里有 3 条 `[object Object]`。

链路（读数全走现场出口，⛔ 本件不写库、不改任何东西）：
  · 集采域：壳 `impSetDomain` 的 m11 分支 → `API.m11List()`（= `GET /api/m11/list`）
    → `service.build_list()["projects"]` → `repository.project_choices()`
    → 壳做 `(p && p.key) || String(p)` ⇒ **`key` 为空串（falsy）时落到 `String(p)`** ⇒ `[object Object]`。
  · 过程资料域（对照）：走通用面 `GET /api/imp/m06_proc/options` → `projects_of()` ⇒ **纯字符串**，不会有这毛病。

用法：`backend\\.venv\\Scripts\\python.exe tools\\probe\\_probe_imp_options.py`
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.db import session_scope                     # noqa: E402
from app.mod06_proc import service as P6                  # noqa: E402
from app.mod11_jc import repository as R11                # noqa: E402
from app.mod11_jc import service as S11                   # noqa: E402


def _shell_render(p) -> str:
    """**照抄壳里那句**（`legacy.js` 的 `impSetDomain` m11 分支）—— 本件要证的就是它。"""
    return (p and p.get("key")) or str(p)


def main() -> int:
    with session_scope() as s:
        choices = R11.project_choices(s)
        m11_projects = S11.build_list(s)["projects"]
        p6_projects = P6.projects_of(P6.load_inv_rows(s), P6.load_history(s))

    print("=" * 78)
    print("通用导入面「项目」候选取证（只读）")
    print("=" * 78)
    print(f"\n【一】集采域：`repository.project_choices()` 共 {len(choices)} 条")
    empties = [c for c in choices if not str(c.get("key") or "").strip()]
    print(f"  ⚠️ 其中 `key`（仓库名）**为空**的 = {len(empties)} 条 —— 这**正好**对应截图里那几条坏选项：")
    for c in empties:
        print(f"     key={c['key']!r}  display={c['display']!r}")
        print(f"       壳渲染成 → <option>{_shell_render(c)}</option>   ⛔ 就是它")
    print("\n  正常条目抽样（前 5 条）：")
    for c in [x for x in choices if str(x.get("key") or "").strip()][:5]:
        print(f"     key={c['key']!r} → {_shell_render(c)}")

    print(f"\n【二】同一份数据的「正确出口」对照：`mod06_proc.projects_of()` = {len(p6_projects)} 条")
    print("  ⇒ 一律是**纯字符串**（仓库名）⇒ 壳那段 `(p && p.key) || String(p)` 对它天然无事 ✅")
    print(f"  抽样：{p6_projects[:5]}")

    print("\n【三】壳侧两处域号分支的差别（这就是根因）")
    print("  · m06_proc：`IMP.org = d.projects`                       ← 通用面 `options` 端点，给**字符串**")
    print("  · m11_jc ：`IMP.org = d.projects.map(p => p.key || String(p))` ← **域专属端点** `/api/m11/list`，给**对象**")
    print("    ⇒ 集采域**没有** `Hooks.options`（`imp_spec.HOOKS = Hooks(commit=…, rollback=…)`）")
    print(f"\n【四】`build_list()['projects']` 与 `project_choices()` 是**同一份**："
          f"{m11_projects == choices}（⛔ 所以问题不在数据，在**壳怎么用**）")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
