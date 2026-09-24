"""反向灵敏度（m04 强制通过 · 请求级断言）—— 证明那几条断言**真的有区分力**。

做法：逐个把实现故意改坏 ⇒ 断言**对应的那条测试确实变红** ⇒ 逐字节复原（MD5）。
    python tools/mut/_mut_m04forms.py

⚠️ 2026-09-24 订正（接手核验轮查出 · 本件此前**整支跑不了**）：
   ① 判据件原写 `test_page_m04_forms.py` —— 该件**已随旧服务端页删除**，claim 搬到了 `test_api_m04_force.py`
      （`ACC-PLAN-AUDIT-001`-09）；② 靶 `VIEW`（`mod04_plan/view.py`）**整个文件已删** ⇒ `before` 一读就
      `FileNotFoundError`。两条一并订正，并**撤掉 M1/M4 两条变异**（留痕见 CASES 上方注释）。
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
B = ROOT / "backend"
PY = B / ".venv" / "Scripts" / "python.exe"
# ⚠️ 2026-09-24 订正：旧件（test_page_m04_forms.py）已随旧页删除 ⇒ 改指两件**请求级**判据：
#    `…force.py` 管强制通过三条（M2/M3），`…manual.py` 管手动行（M5）。
TEST = "tests/test_api_m04_force.py tests/test_api_m04_manual.py"

ROUTER = B / "app" / "mod04_plan" / "router.py"
REPO = B / "app" / "mod04_plan" / "repository.py"
DOMAIN = B / "app" / "mod04_plan" / "domain.py"
MANUAL = B / "app" / "mod04_plan" / "plan_manual.py"
# ⚠️ 2026-09-24：原 `VIEW`（mod04_plan/view.py）已随旧渲染层整体删除 ⇒ 去掉该靶（连带撤掉 M4）。

CASES: list[tuple[str, Path, str, str]] = [
    # ⛔ **M1 已撤（2026-09-24）**：原 claim =「端点参数用 `Form`，否则回跳丢筛选」—— 它钉的是**旧 PRG 表单端点**
    #    （`POST /m04/force`）；该端点随旧页删除，新壳走 JSON 端点（`params=`）⇒ **变异点不存在了，不是丢守卫**。
    ("M2 强制通过不再落备注（留痕丢失）", REPO,
     '    row.forced_remark = str(remark or "").strip()',
     '    row.forced_remark = ""'),
    ("M3 空备注不再被拒（口径失守）", DOMAIN,
     '    if not text:\n        raise MustReportError("强制通过必须填写备注（说明为什么放行）—— 空备注不被接受")',
     "    if False:\n        pass"),
    # ⛔ **M4 已撤（2026-09-24）**：原 claim =「页面不再给出强制通过入口」—— 靶（mod04_plan/view.py）整件已删；
    #    入口现在长在**壳**（`V.m04` 的「强制通过」按钮 ⇒ `POST /api/m04/plans/{id}/force`）⇒ 该 claim 由
    #    `test_wired_m04.py` 的壳侧断言 ＋ `test_api_m04_force.py` 的请求级断言**一起钉着**。
    # ⚠️ **M5 已换靶（2026-09-24）**：原 claim =「手动行「归月」字段不得与筛选月同名（`FormData` 同名取第一个
    #    ⇒ 会被静默忽略）」—— 那个危险**只存在于旧服务端表单**；新壳的手动行走 **JSON**（无 `FormData` 同名语义）
    #    ⇒ 原变异点**结构上不存在了**。⇒ 换成**同主题的活 claim**：手动行「年月」**必须校验形态**（归月依据）。
    ("M5 手动行「年月」形态不再校验（非法归月被静默接受）", MANUAL,
     "    if not _YM_RE.match(ym):",
     "    if False:  # 变异：年月形态不再校验"),
]


def run_tests() -> tuple[int, bool]:
    # ⚠️ `TEST` 可能是**多件**（空格分隔）⇒ 必须 `split()` 成多个 argv，⛔ 别整串当一个路径传
    #    （整串传 ⇒ pytest 报 "file or directory not found" ⇒ 基线假红 ⇒ 本件停手）。
    p = subprocess.run([str(PY), "-m", "pytest", "-q", *TEST.split()],
                       cwd=B, capture_output=True, text=True, encoding="utf-8")
    out = p.stdout + p.stderr
    failed = "failed" in out or p.returncode != 0
    return p.returncode, failed


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in (ROUTER, REPO, DOMAIN, MANUAL)}
    _, failed0 = run_tests()
    print(f"  基线：全部通过 = {not failed0}")
    if failed0:
        print("  ⛔ 基线就不是全绿 ⇒ 停手")
        return 1

    hits = 0
    for name, path, old, new in CASES:
        text = path.read_text(encoding="utf-8")
        if old not in text:
            print(f"  ❌ {name} —— 变异串没找到（实现已变？）")
            continue
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        rc, failed = run_tests()
        path.write_bytes(before[path][0])          # 立刻复原
        print(f"  {'✅' if failed else '❌'} {name} —— 期望变红 ⇒ {'命中' if failed else '仍绿（断言没区分力）'}")
        hits += 1 if failed else 0

    ok = all(md5(p) == before[p][1] for p in before)
    print(f"\n  复原校验（MD5 逐字节）：{'✅ ' + str(len(before)) + '/' + str(len(before)) if ok else '❌ 有文件没复原'}")
    print(f"  反向灵敏度：**{hits}/{len(CASES)} 命中**")
    return 0 if (hits == len(CASES) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
