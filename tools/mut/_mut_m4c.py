"""`TAIL-03 / TAIL-02 / TAIL-01`（机械手录 · 历史导入 · 手动导入 Excel）的**反向灵敏度**。

跑法：`python tools/_mut_m4c.py`（在工程根）—— 退出码非 0 = 有"仍绿"或有还原失败。

⚠️ 三条纪律（样板 = `tools/_mut_m4b.py`）：
1. **本仓源码行尾不统一** ⇒ 片段一律按 LF 写，匹配前用 `_fit()` 按目标文件归一；
2. **片段含中文要用 `str` + `.encode()`** —— bytes 字面量只允许 ASCII；
3. **跑完必须重跑一次全套 `pytest`** —— 否则 `var/state/verification/acc_results.json` 留的是**变异态**结果。
"""

from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import hashlib
import os
import pathlib
import subprocess

# ⛔ **结果隔离**（本仓纪律）：本脚本跑的是**子集** pytest ⇒ 必须把四态结果写到**临时文件**，
#    否则会把权威 `var/state/verification/acc_results.json` 冲成"只有这几条"（`doc_audit` 的 T4 立刻报红）。

ROOT = pathlib.Path(__file__).resolve().parents[2]
BE = ROOT / "backend"
PY = str(BE / ".venv/Scripts/python.exe")

#: `(说明, 相对路径, 原文, 替换, 该变异应被哪几个测试文件抓住)`
MUTATIONS: list[tuple[str, str, str, str, str]] = [
    # ---------------------------------------------------------- TAIL-03 机械手录
    ("① 手录放过负数（§8.4：机械 6 列 ≥ 0）",
     "backend/app/mod06_proc/mech_ui.py",
     "        if value < 0:\n            raise ValueError(f\"「{label}」不得为负数（当前 {value}）\")",
     "        if False:\n            raise ValueError(f\"「{label}」不得为负数（当前 {value}）\")",
     "tests/test_page_m06.py tests/test_acc_proc_002.py"),

    # ⚠️ 2026-09-23：②③ 的靶（`mech_ui._value_of` 表单回填 · `mech_ui.block_html` 机械区块）
    #    **已于 2026-09-18 随旧服务端渲染页整体删除**（`mech_ui.py` 文件头有留痕）⇒ 锚点早已命中 0 次
    #    （表现为 `SKIP`，⛔ 不是通过 —— 与 ⑬⑭ 同款 ⇒ 一并删除，留痕在此）。
    #    ⚠️ 它们守的两条 claim 现在归**壳的机械区块**（`legacy.js`）：
    #      · ② 录第二次要能看见上次的值（回填）；
    #      · ③ 机械区块**只**给机械 6 列输入框，材料列只读（§5.2.3 单向流）。
    #    ⛔ **这两条在壳侧目前还没有断言** ⇒ 已登记为尾巴（补壳侧断言），⛔ 别当"已覆盖"。
    ("④ `YYYY-MM` 归一放过 13 月",
     "backend/app/mod06_proc/domain.py",
     "    if not 1 <= mm <= 12:",
     "    if False:",
     "tests/test_page_m06.py"),

    # ---------------------------------------------------------- TAIL-02 历史导入
    # ⚠️ 2026-09-23：⑤⑥⑨ 的锚点随 `B3`/`B5-0` 重写 `importer.py`（两级表头拼名 ＋ 四条口径裁定）
    #    被改没了 ⇒ 同样表现为 `SKIP`（静默失效）。**判据没变** ⇒ 锚点改指**现在的**那几行。
    ("⑤ 机械列**静默忽略**（不再列出来给人看）",
     "backend/app/mod06_proc/importer.py",
     "    plan.ignored_mech = [c[\"label\"] for c in D.PROC_COLUMNS\n"
     "                         if c[\"key\"] in D.MECH_KEYS and c[\"key\"] in found]",
     "    plan.ignored_mech = [c[\"label\"] for c in D.PROC_COLUMNS\n"
     "                         if c[\"key\"] in D.MECH_KEYS and False]",
     "tests/test_page_m06.py"),

    ("⑥ 核算月认不出的行**静默跳过**（不再逐条报）",
     "backend/app/mod06_proc/importer.py",
     "            if not ym:\n"
     "                plan.anomalies.append({\"line\": offset, \"reason\":\n"
     "                                       f\"核算月认不出：",
     "            if False:\n"
     "                plan.anomalies.append({\"line\": offset, \"reason\":\n"
     "                                       f\"核算月认不出：",
     "tests/test_page_m06.py"),

    ("⑦ 导入时把「截止核算月」吞掉（历史段整段失效）",
     "backend/app/mod06_proc/importer.py",
     "        operator=operator, cutoff_ym=str(cutoff_ym or plan.default_cutoff or \"\"),",
     "        operator=operator, cutoff_ym=\"\",",
     "tests/test_page_m06.py tests/test_acc_proc_002.py"),

    ("⑧ 核对报告交白卷（不再列「会印空的月份」）",
     "backend/app/mod06_proc/importer.py",
     "    empty_months = sorted(m for m in inv_months\n"
     "                          if m and cutoff_ym and m <= str(cutoff_ym) and m not in snap_months)",
     "    empty_months = []",
     "tests/test_page_m06.py"),

    ("⑨ 导入解析改成**按下标认列**（挪列就认错）",
     "backend/app/mod06_proc/importer.py",
     "        if got:\n            out[col] = got[0]",
     "        if got:\n            out[width - 1 - col] = got[0]",
     "tests/test_page_m06.py"),

    # ⚠️ 2026-09-21（`§19` 四个暂留件收口）：⑩⑪⑫ 的落点随导入页**搬家**（服务端渲染 → JSON API ＋ 壳）
    #    ⇒ 锚点同步改指新件（**逐字**搬过去的文本原样可用 —— 这正是"形态变、判据不变"）。
    # ⚠️ 2026-09-23（`TAIL-75` `B5c-2`）：旧页与旧端点都退休了 ⇒ 靶改指**壳的通用面上传口**
    #    （`core.js` 的 `impParse`）；判据侧同步钉住这条字面量（见 `test_page_m06.py`）。
    # ⭐ 2026-09-24：壳再拆一刀 —— `API` 块从 `core.js` 搬进 **`api.js`** ⇒ 靶同步改指 `api.js`
    #    （⛔ 不改 ⇒ 锚点命中 0 ⇒ 报 **SKIP** ⇒ **尺子假装在岗**；与 `_mut_stale.py` 同日同病）。
    ("⑩ 导入页的上传口指错端点（通用面 parse 写错 ⇒ 传了文件也没人接）",
     "backend/app/web/shell/api.js",
     "/api/imp/${encodeURIComponent(domain)}/parse",
     "/api/impx/${encodeURIComponent(domain)}/parse",
     "tests/test_page_m06.py"),

    # ---------------------------------------------------------- TAIL-01 手动导入 Excel
    # ⚠️ 2026-09-23：⑪⑫ 的靶文件 `backend/app/mod08_inv/import_api.py` 已随**「库存单据手动导入」整件取消**
    #    （用户 2026-09-22 裁定「给删掉，不要了」）一起删除 ⇒ 与 ⑬⑭ 同款：**既是过期锚点，又会把整支脚本拖崩**
    #    （`main()` 开头对所有靶文件 `read_bytes()` ⇒ 缺件 = `FileNotFoundError` ⇒ **一条都跑不了**）。
    #    ⭐ 它们守的 claim（手动导入的金额转 `Decimal` / 分组金额不漏算）随模块取消**一并消失**
    #    ⇒ 直接删除，⛔ 不留空靶（库存数据唯一入口 = i8 抓取，见 `audit_common.CANCELLED` 的 `m08imp`）。
    #    ⚠️ 教训：**删文件时要顺手查一遍 `tools/mut/` 有没有以它为靶的脚本** —— 否则尺子静默失效。

    # ⚠️ 原先的 ⑬⑭ 靶在**旧明细页** `backend/app/mod08_inv/view.py` 上 —— 那个文件已于 2026-09-19
    #    （`§19` 批 2，授权 `D18`）整体删除 ⇒ 两条变异**既是"命中 0 次的过期锚点"，又会把整个脚本拖崩**
    #    （`main()` 一开头就对所有靶文件 `read_bytes()` ⇒ 缺件 = `FileNotFoundError`、**一条都跑不了**）。
    #    ⇒ 2026-09-21 一并删除（留痕在此）。它们守的 claim（**降级后确实有手动导入这条路**）现由
    #    `tests/test_wired_m08.py`（壳里两个入口 ＋ 解析端点；原 `test_page_m08.py` 已随旧页删除，该件已不在仓里）
    #    ＋ `test_acc_inv_fetch.py::001-08` 承接 ✓

    ("⑮ 预览暂存取不到时**回落成空**（而不是显式报错）",
     "backend/app/core/preview_store.py",
     "    if not path.exists():\n        raise MustReportError(EXPIRE_TIP)",
     "    if not path.exists():\n        return {}",
     "tests/test_page_m06.py"),

    # ---------------------------------------------------------- 路由静态守卫（全局）
    # ⚠️ 2026-09-21：⑯ 的锚点原在**历史导入那条 PRG**（`import_mech` 里 `ym = D.normalize_ym(form.get("ym"))`），
    #    那一段已随四个暂留件收口**切除**（改走 `import_api.py`）⇒ 改指**仍在的**那条写路径
    #    （`POST /api/m06/mech` 的 `api_mech_save`）—— 守的还是同一件事：
    #    「路由里把出口挂到**不存在**的模块上 ⇒ `test_router_refs` 必须抓住」。
    ("⑯ 路由把出口挂到错的模块上（`normalize_ym` 其实住在 `domain`）",
     "backend/app/mod06_proc/router.py",
     "    ym = D.normalize_ym(req.ym)",
     "    ym = mech_ui.normalize_ym(req.ym)",
     "tests/test_router_refs.py tests/test_acc_rpt_big.py"),
]


def _fit(fragment: str, sample: bytes) -> bytes:
    """把片段的行尾归一成 `sample` 的样子（本仓源码行尾不统一）。"""
    raw = fragment.replace("\r\n", "\n").encode("utf-8")
    if b"\r\n" in sample:
        return raw.replace(b"\n", b"\r\n")
    return raw


def run_tests(targets: str) -> int:
    return subprocess.run([PY, "-m", "pytest", *targets.split(), "-qq", "--no-header",
                           "-p", "no:cacheprovider"], cwd=BE, capture_output=True).returncode


def main() -> int:
    files = sorted({rel for _d, rel, _o, _n, _t in MUTATIONS})
    src0 = {f: (ROOT / f).read_bytes() for f in files}
    md5_0 = {f: hashlib.md5(b).hexdigest() for f, b in src0.items()}
    bad = 0
    for desc, rel, old_s, new_s, targets in MUTATIONS:
        src = src0[rel].replace(b"\r\n", b"\n")
        o, n = old_s.encode("utf-8"), new_s.encode("utf-8")
        if src.count(o) != 1:
            print(f"[SKIP ] ❓ {desc} —— 锚点命中 {src.count(o)} 次（应为 1）")
            bad += 1
            continue
        (ROOT / rel).write_bytes(_fit(src.replace(o, n, 1).decode("utf-8"), src0[rel]))
        rc = run_tests(targets)
        (ROOT / rel).write_bytes(src0[rel])
        print(f"[{'RED ' if rc else 'GREEN'}] {'✅' if rc else '❌'} {desc}")
        bad += 0 if rc else 1
    print("\n--- 还原复核（MD5 逐字节）---")
    for f in files:
        now = hashlib.md5((ROOT / f).read_bytes()).hexdigest()
        ok = now == md5_0[f]
        print(("OK  " if ok else "BAD "), f, now)
        bad += 0 if ok else 1
    print(f"\n合计问题 = {bad}（0 = 全部变异都被判据抓住、且源文件逐字节复原）")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
