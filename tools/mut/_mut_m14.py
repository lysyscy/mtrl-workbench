# -*- coding: utf-8 -*-
"""反向灵敏度（变异测试）—— `MOD-14` 壳接线断言（`ACC-CFG-RULE-001` 5 点）**是否真有区分力**。

做法：把实现**故意改坏**若干处，确认**对应断言确实变红**；每次立刻按 bytes 复原，最后核对 MD5。

用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_mut_m14.py`

⚠️ 本仓纪律（见 memory §十七）：
1. **一律走 bytes**（`write_text` 在 Windows 会把 `\\n` 写成 `\\r\\n` ⇒ MD5 假 BAD）；
2. 变异片段**含中文**时用 `str` ＋ `.encode()`（`b"…"` 只允许 ASCII）；
3. **行尾按目标文件归一**（本仓源码行尾不统一）；
4. 变异点**必须唯一命中**，否则重写（不得当成"已通过"）；
5. 跑完**必须再跑一次全套 `pytest`**（否则 `acc_results.json` 留的是变异态 ⇒ 报表数字是假的）。
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))  # ⭐ `TAIL-58` 分目录：shell_source 在 audit/
from shell_source import SHELL_PATH, pick  # noqa: E402  ← `P4`① 读取点收敛

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
FILES = {
    "shell": SHELL_PATH,
    "api": ROOT / "backend" / "app" / "mod14_config" / "rules_api.py",
}

T1 = "test_剔除规则真增删改且改动落到规则数据"
T2 = "test_分类规则表只读不渲染编辑入口"
T3 = "test_规则与说明表不得被标为可排序"
T4 = "test_命中值结构与口径一致"
T5 = "test_关键词编辑入口在项目行本页只读"

#: (说明, 目标文件, 原文片段, 改坏成, 应当变红的测试名)
MUTATIONS: list[tuple[str, str, str, str, str]] = [
    # ---- 001-01 · 真增删改 + 条数实时算
    ("ruleSave 变成假成功（不落库、只弹提示）",
     "shell",
     "const res = i>=0 ? await API.m14RuleSet((RULE_RAW[i]||{}).id, body) : await API.m14RuleAdd(body);",
     "const res = {ok:true, message:'已保存'};",
     T1),
    ("ruleDel 不再走后端",
     "shell",
     "const res = await API.m14RuleDel((RULE_RAW[i]||{}).id);",
     "const res = {ok:true, message:'已删除'};",
     T1),
    ("ruleSave 写完不重拉（改了看不见）",
     "shell",
     "closeModal(); await reloadM14(); render();",
     "closeModal(); render();",
     T1),
    ("卡头条数写死成 4（不跟着规则条数走）",
     "shell",
     "<h4>剔除规则（<b>${RULE_EX.length}</b> 类有效）",
     "<h4>剔除规则（<b>4</b> 类有效）",
     T1),
    ("reloadM14 不填 RULE_EX（表格恒空）",
     "shell",
     "RULE_EX = RULE_RAW.map(r => [r.kind_label, r.values, r.meaning]);",
     "RULE_EX = [];",
     T1),
    ("后端写端点不走仓储（另写一套）",
     "api",
     "RR.add_row(s, kind=req.kind",
     "_add_row(s, kind=req.kind",
     T1),
    ("后端删端点没了",
     "api",
     '@router.delete("/api/m14/rules/{rule_id}")',
     '@router.delete("/api/m14/rules-removed/{rule_id}")',
     T1),
    ("写侧出现历史重算调用（§4.2.2 禁止）",
     "api",
     "from app.mod03_notice import rules_repository as RR",
     "from app.mod03_notice import rules_repository as RR\n"
     "from app.mod03_notice.classify import decide_placement  # noqa: F401",
     T1),
    # ---- 001-02 · 分类说明默认不再展示
    ("默认页分类说明模块复活",
     "shell", "<h4>集采项目剔除名单", "<h4>分类规则</h4><h4>集采项目剔除名单", T2),
    # ---- 001-03 · 配置/说明表不得可排序
    ("剔除规则表被标成可排序",
     "shell",
     '<table class="dt"><thead><tr><th>规则类别</th>',
     '<table class="dt" data-sort><thead><tr><th>规则类别</th>',
     T3),
    # ---- 001-04 · 结构与后端同源
    ("RULE_KINDS 不从后端落定（下拉空 / 只能硬编码）",
     "shell",
     "RULE_KINDS = d.kinds || [];",
     "RULE_KINDS = [];",
     T4),
    ("ruleForm 的类别下拉不再用后端 kinds",
     "shell",
     "+ RULE_KINDS.map(k=>",
     "+ [].map(k=>",
     T4),
    # ---- 001-05 · 关键词入口在项目行
    ("默认页关键词说明模块复活",
     "shell", "<h4>集采项目剔除名单", "<h4>小微识别关键字配置</h4><h4>集采项目剔除名单", T5),
    ("项目行（m01）的关键词入口没了",
     "shell",
     'data-act="editKw"',
     'data-act="editKwX"',
     T5),
]


def _fit(fragment: bytes, sample: bytes) -> bytes:
    if b"\r\n" in sample:
        return fragment.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return fragment.replace(b"\r\n", b"\n")


def main() -> int:
    orig = {k: p.read_bytes() for k, p in FILES.items()}
    md5_before = {k: hashlib.md5(v).hexdigest() for k, v in orig.items()}
    for k, v in orig.items():
        print(f"{k}: {len(v)} 字节 · MD5 {md5_before[k][:12]}")

    hit = miss = 0
    for i, (label, fkey, old, new, test_name) in enumerate(MUTATIONS, 1):
        # ⚠️ 2026-09-19（性能 `P4`② 三刀真拆）：壳是多件 ⇒ 锚点在哪件就改哪件（⛔ 仍逐字节复原）。
        #    ⚠️ 判断基准一律用**原始** `SHELL_PATH`：`FILES["shell"]` 已被上一条改成别的件，
        #    拿它当基准会**累积失效**（实测：第 6 条起全 SKIP）。
        if fkey == "shell":
            FILES["shell"] = pick(SHELL_PATH, old, new)
            orig["shell"] = FILES["shell"].read_bytes()
            md5_before["shell"] = hashlib.md5(FILES["shell"].read_bytes()).hexdigest()
        target = orig[fkey]
        o = _fit(old.encode("utf-8"), target)
        n = _fit(new.encode("utf-8"), target)
        cnt = target.count(o)
        if cnt != 1:
            print(f"  {i:2d}. ⚠️ SKIP（变异点命中 {cnt} 次）—— [{fkey}] {label}")
            miss += 1
            continue
        FILES[fkey].write_bytes(target.replace(o, n))
        r = subprocess.run(
            [str(PY), "-m", "pytest", "-q", "-k", test_name, "tests/"],
            cwd=ROOT / "backend", capture_output=True, text=True,
        )
        bad = r.returncode != 0
        print(f"  {i:2d}. {'✅ 变红' if bad else '⛔ 仍绿（假绿！）'} —— [{fkey}] {label}  [{test_name}]")
        if bad:
            hit += 1
        FILES[fkey].write_bytes(target)

    md5_after = {k: hashlib.md5(p.read_bytes()).hexdigest() for k, p in FILES.items()}
    ok_md5 = all(md5_after[k] == md5_before[k] for k in FILES)
    print(f"\n命中 {hit}/{len(MUTATIONS) - miss} · SKIP {miss} · "
          f"MD5 {'逐字节复原 ✅' if ok_md5 else '⛔ 不一致'}")

    # ⚠️ 必须再跑一次全套（复原态）：否则 acc_results.json 留的是子集运行的结果 ⇒ 四态报表数字是假的
    print("重跑全套 pytest（复原态）…")
    full = subprocess.run([str(PY), "-m", "pytest", "-q", "tests/"],
                          cwd=ROOT / "backend", capture_output=True, text=True)
    print("  全套 pytest 退出码 =", full.returncode)
    return 0 if (ok_md5 and miss == 0 and hit == len(MUTATIONS) and full.returncode == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
