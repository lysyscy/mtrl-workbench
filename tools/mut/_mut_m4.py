"""M4 · `ACC-RPT-EXP-001`（过程资料导出）的反向灵敏度。

做法与 `_mut_m9.py` 同款：**bytes ＋ `_fit()` 行尾归一**，逐条施加 → 跑断言 → 逐字节还原 → 复核 MD5。
⚠️ 片段**一律按 LF 写**；含中文的片段用 `str` 再 `.encode()`（bytes 字面量只允许 ASCII）。
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

# ⚠️ 2026-09-23（`TAIL-77`）：本件随 `TAIL-58` 从 `tools/` 搬进 `tools/mut/` ⇒ 深度 +1，
#    原 `parent.parent` 会指向 `tools/`（⇒ `BE = tools/backend` ⇒ 一跑就 `FileNotFoundError`）。
ROOT = Path(__file__).resolve().parents[2]
BE = ROOT / "backend"
PY = str(BE / ".venv/Scripts/python.exe")
# ⚠️ 带上 `test_acc_proc_001.py`：本单元的导出展开区**同页存在**，把该件那条
#    「筛选栏不给多选」的整页断言撞红了 ⇒ 已改成绑筛选栏段，这里一并钉住它。
# ⚠️ 2026-09-23（`TAIL-77`）：⑥⑧⑨⑩ 的靶随旧页（`mod06_proc/view.py`）删除搬进了**壳**
#    ⇒ 必须连 `test_wired_m06.py` 一起跑（那四条 shell 断言住在那里）。
TEST = "tests/test_acc_proc_exp.py tests/test_acc_proc_001.py tests/test_wired_m06.py"


def _b(s: str) -> bytes:
    return s.replace("\r\n", "\n").encode("utf-8")


def _fit(fragment: bytes, sample: bytes) -> bytes:
    """把 LF 片段转成与目标文件一致的行尾。"""
    if b"\r\n" in sample:
        return fragment.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return fragment.replace(b"\r\n", b"\n")


#: (说明, 文件, 原串, 变异串) —— 覆盖 001-01 / 001-02 / 001-03 / 001-04 四个点
MUTATIONS: list[tuple[str, str, str, str]] = [
    ("① 展开区不再默认选中当前项目（连「清空」也退回默认）",
     "app/mod06_proc/domain.py",
     "    if not touched:\n        return [current] if current else []",
     "    if True:\n        return [current] if current else []"),

    ("② 多项目不再打成 zip",
     "app/mod06_proc/domain.py",
     '        "zip": len(files) > 1,',
     '        "zip": False,'),

    ("③ 单个项目也给 zip 名（形态判断错）",
     "app/mod06_proc/domain.py",
     '        "zip_name": f"{EXPORT_DOMAIN}_{ym}.zip" if len(files) > 1 else "",',
     '        "zip_name": f"{EXPORT_DOMAIN}_{ym}.zip" if len(files) >= 1 else "",'),

    ("④ 提示不再跟随当前表（恒取默认表）",
     "app/mod06_proc/domain.py",
     "    cur = tab_of(tab)\n    return next(label for num, label in TABS if num == cur)",
     "    cur = DEFAULT_TAB\n    return next(label for num, label in TABS if num == cur)"),

    ("⑤ 文件名不再含表名（取数同源断掉）",
     "app/mod06_proc/domain.py",
     '    return f"{project}_{EXPORT_DOMAIN}_{tab_name(tab)}_{ym}.xlsx"',
     '    return f"{project}_{EXPORT_DOMAIN}_{ym}.xlsx"'),

    # ⭐ 2026-09-23（`TAIL-77`）：⑥⑧⑨⑩ 的靶随旧页（`mod06_proc/view.py`）于 2026-09-18 删除
    #    ⇒ **改指壳**（`index.html` 的 `V.m06` 切片 / `shell/actions.js`）—— **claim 一字未改**，
    #    对应断言现在住在 `tests/test_wired_m06.py`（已加进 `TEST`）。
    ("⑥ 展开区被挪成两处 / 与表格同容器（浮层会被裁）",
     "app/web/index.html",
     "    ${procExpOn?procExpStrip():''}",
     "    ${procExpOn?(procExpStrip()+procExpStrip()):''}"),

    # ⛔ ⑦ 已撤（2026-09-23 逐条核过，**不是缺口**）：原 claim 是「说明里的列数**来自列定义**」，
    #    旧页 `view.py` 里确实是 `len(D.PROC_COLUMNS)`；而新壳那句是**模板自己的**列数说明
    #    （「17 列模板 ｜ 入库 5 类 ｜ 出库 5 类 ｜ 机械 6 列」）—— 17 由**母本模板文件**定死，
    #    ⛔ 本来就**不该**跟着域常量派生（模板改了列数，说明也得跟着人改）。⇒ 变异点没了，不是丢了守卫。
    ("⑧ 候选项**全部**预勾选（默认选中 ≠ 当前项目）",
     "app/web/shell/actions.js",
     "   if(procExpOn&&!procExpPjs.length&&procPj) procExpPjs=[procPj];",
     "   if(procExpOn) procExpPjs=[procPj];"),

    ("⑨ 0 个项目时导出按钮不禁用（会导出一个用户没选的东西）",
     "app/web/index.html",
     "${procExpPjs.length?'':'disabled'}",
     "''"),

    ("⑩ 筛选栏的项目面板变成多选（与导出面板同款 ⇒ 001-04「单选」被破坏）",
     "app/web/index.html",
     "const procPjPanel=()=>projPanel({list:()=>pjSort(PROC_PJS),selected:()=>[procPj],"
     "pickAct:'procPjPick',meta:PROJ_META_KEY,single:true});",
     "const procPjPanel=()=>projPanel({list:()=>pjSort(PROC_PJS),selected:()=>[procPj],"
     "pickAct:'procPjPick',meta:PROJ_META_KEY});"),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_test() -> int:
    return subprocess.run([PY, "-m", "pytest", *TEST.split(), "-qq", "--no-header",
                           "-p", "no:cacheprovider"], cwd=BE, capture_output=True).returncode


def main() -> int:
    # ⚠️ 2026-09-23（`TAIL-77`）：靶文件**已被删**的不许把整个脚本崩掉 —— 原先这里直接
    #    `md5(BE / rel)` 读一个不存在的路径 ⇒ `FileNotFoundError` ⇒ **后面每一条都没验**，
    #    而屏幕上只有一段 traceback（看起来像"脚本坏了"，其实是"靶早没了"）。
    rels = {rel for _d, rel, _o, _n in MUTATIONS}
    for rel in sorted(r for r in rels if not (BE / r).exists()):
        print(f"[SKIP] ⚠️ 靶文件已不存在：{rel}（该条的 claim 已搬家或已撤 —— 见 `MUTATIONS` 注释）")
    before = {rel: md5(BE / rel) for rel in rels if (BE / rel).exists()}
    ok, miss, still_green = 0, [], []
    for desc, rel, old_s, new_s in MUTATIONS:
        p = BE / rel
        if not p.exists():
            miss.append(f"{desc}（靶文件已删：{rel}）")
            continue
        src = p.read_bytes()
        old, new = _fit(_b(old_s), src), _fit(_b(new_s), src)
        hit = src.count(old)
        if hit != 1:
            miss.append(f"{desc}（命中 {hit} 次）")
            print(f"[MISS] ❌ 变异点应唯一命中，实得 {hit} —— {desc}")
            continue
        p.write_bytes(src.replace(old, new, 1))
        rc = run_test()
        p.write_bytes(src)
        if rc != 0:
            ok += 1
            print(f"[RED ] ✅ {desc}")
        else:
            still_green.append(desc)
            print(f"[GREEN] ❌ 变异了却还是绿 —— {desc}")

    print("\n--- 还原复核 ---")
    bad = []
    for rel, h in before.items():
        now = md5(BE / rel)
        if now != h:
            bad.append(rel)
        print(f"  {'OK ' if now == h else 'BAD'} {rel}  {now}")
    print(f"\n命中 {ok}/{len(MUTATIONS)} · 变异点找不到 {len(miss)} · 变异后仍绿 {len(still_green)}")
    for x in miss + still_green:
        print("   !", x)
    return 0 if (not bad and not miss and not still_green) else 1


if __name__ == "__main__":
    sys.exit(main())
