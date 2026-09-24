#!/usr/bin/env python
"""`B4`（m11 接入建议/校验/记忆）的**反向灵敏度**：四处改坏 ⇒ 对应断言必须变红 ⇒ 逐字节复原（MD5 校验）。

⭐ 为什么留成脚本：B4 那三条边界是**纪律**（建议不许自动变成判定 · 撞车不许预选 · 提示不许改判定 ·
   记忆不许记错域）—— 日后有人"顺手"松掉一条，本脚本立刻证明**判据护住了**。

⛔ 纪律：只临时替换源文件；跑完立刻回写原文并核对 MD5；⚠️ 结果必须写到**变异用**结果文件
   （否则会把正式 `artifacts/acc_results.json` 覆盖掉 ⇒ `doc_audit` T4 会红 —— 踩过）。
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = ROOT / "backend/.venv/Scripts/python.exe"
EP = ROOT / "backend/app/mod11_jc/excel_parse.py"
SV = ROOT / "backend/app/mod11_jc/import_service.py"
T = "tests/test_jc_import_engine.py"

#: `(说明, 文件, 原文, 改成, 目标测试)` —— 每处只坏一件事
MUTS = [
    ("M1 建议**自动变成判定**（本该只预选）", EP,
     '            x["preselect"] = True\n    return out',
     '            x["preselect"] = True\n'
     '    for x in out:                                   # MUT：建议直接写进判定\n'
     '        if x.get("preselect"):\n'
     '            mapping["fields"][x["field"]] = x["col"]\n'
     '    return out',
     f"{T}::test_未认出的列给引擎建议_但一律需你确认_且不改判定"),
    ("M2 撞车不再降级（多列建议同一字段照样预选）", EP,
     '        if seen[x["field"]] > 1:',
     '        if False:',
     f"{T}::test_未认出的列给引擎建议_但一律需你确认_且不改判定"),
    ("M3 值画像交叉校验关掉（名字认对、列拿错也不吭声）", EP,
     '        if not prof or not _type_conflict(prof, FIELD_TYPES.get(fld, "")):\n            continue',
     '        if True:\n            continue',
     f"{T}::test_值画像交叉校验_名字认对但值不像就提示_且不改判定"),
    ("M4 记忆记到别的域（跨域套用）", SV,
     '        st.save(DOMAIN, labels, saved, source_label=f"{filename}·{sheet}")',
     '        st.save("m04_plan", labels, saved, source_label=f"{filename}·{sheet}")',
     f"{T}::test_确认过的映射按表头指纹记住_下次预填并标明来源"),
]

originals: dict[pathlib.Path, str] = {}
ok = True
for name, path, old, new, target in MUTS:
    src = originals.setdefault(path, path.read_text(encoding="utf-8"))
    if old not in src:
        print(f"⛔ 锚点找不到，跳过：{name}")
        ok = False
        continue
    path.write_text(src.replace(old, new, 1), encoding="utf-8", newline="")
    env = dict(os.environ)
    env["ACC_RESULTS_PATH"] = "../artifacts/_mut_acc_results.json"
    got = subprocess.run([str(PY), "-m", "pytest", target, "-q", "-p", "no:cacheprovider",
                          "--tb=no", "-x"], cwd=ROOT / "backend", capture_output=True, env=env)
    red = got.returncode != 0
    print(f"{'✅' if red else '⛔'} {name} ⇒ 断言{'变红（有区分力）' if red else '**仍然绿**（判据没护住！）'}")
    ok = ok and red
    path.write_text(src, encoding="utf-8", newline="")

for path, src in originals.items():
    path.write_text(src, encoding="utf-8", newline="")
    same = hashlib.md5(path.read_bytes()).hexdigest() == hashlib.md5(src.encode("utf-8")).hexdigest()
    print(f"复原校验 {path.name}：{'MD5 一致 ✅' if same else '⛔ 不一致！'}")
    ok = ok and same

print("结论：" + ("四处都变红 ⇒ B4 判据有区分力" if ok else "⚠️ 有判据没护住，得补"))
sys.exit(0 if ok else 1)
