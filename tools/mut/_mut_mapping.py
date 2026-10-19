#!/usr/bin/env python
"""反向灵敏度（变异测试）· `import_kit.mapping` / `import_kit.profile_store`（`TAIL-75` B1）。

做法：把实现**故意改坏 7 处**，每处都应让**对应断言变红**；跑完**逐字节复原**（MD5 校验）。
⛔ 有一处没变红 ⇒ 说明那条断言是"现象"不是"意图" ⇒ 必须修断言（不是修变异）。
"""
from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import hashlib
import pathlib
import subprocess
import sys
import os

# ⛔ **结果隔离**（本仓纪律）：非全套 pytest 必须把四态结果写到**临时文件** ——
#    否则每处变异都会把权威 `var/state/verification/acc_results.json` 冲成单条 ⇒ `doc_audit` 的 T4 立刻报红。
os.environ.setdefault("ACC_RESULTS_PATH", str(_run_output('_mut_acc_results.json')))

sys.stdout.reconfigure(encoding="utf-8")
REPO = pathlib.Path(__file__).resolve().parents[2]
MAP = REPO / "backend" / "app" / "import_kit" / "mapping.py"
STORE = REPO / "backend" / "app" / "import_kit" / "profile_store.py"

#: (说明, 文件, 原文, 改成, 期望变红的测试 -k 片段)
MUTATIONS: list[tuple[str, pathlib.Path, str, str, str]] = [
    ("① 单位括号不再剥（`金额（元）` 认不出）", MAP,
     '_UNIT_WORDS = frozenset({\n    "元", "万元", "千元", "亿元", "rmb", "人民币", "万元整", "个", "天", "月", "次", "笔",\n})',
     '_UNIT_WORDS = frozenset()', "归一化"),
    ("② 语义括号也被无脑剥掉（`不含税` 丢失 ⇒ 含税/不含税 撞车）", MAP,
     's = _PAREN.sub(lambda m: "" if m.group(1).strip().lower() in _UNIT_WORDS else m.group(0), s)',
     's = _PAREN.sub("", s)', "归一化"),
    ("③ 认不出也预选（`blank` 档消失 ⇒ 开始猜了）", MAP,
     '_CONF_CONFIRM = 0.70', '_CONF_CONFIRM = 0.0', "留空"),
    ("④ 纯整数也判「金额」（序列号歧义被抹掉）", MAP,
     'return "金额" if money_fmt / n >= 0.2 else "数字"     # 有小数点/千分位才算金额',
     'return "金额"', "画像"),
    ("⑤ 年月不校验月份（`400000` 也算年月）", MAP,
     'return len(s) == 6 and s.isdigit() and 1 <= int(s[4:]) <= 12',
     'return len(s) == 6 and s.isdigit()', "画像"),
    ("⑥ 未映射的列不再原样保留（`raw` 丢列）", MAP,
     '            if to and to != IGNORE:\n                rec[to] = val\n            elif keep_raw:\n                raw[src] = val',
     '            if to and to != IGNORE:\n                rec[to] = val\n            elif keep_raw and to != IGNORE:\n                raw[src] = val',
     "取行"),
    ("⑦ 记忆指纹路不校验域（跨域套用旧映射）", STORE,
     '        if hit is not None and hit.domain == domain:',
     '        if hit is not None:', "按域隔离"),
]


def md5(p: pathlib.Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_pytest(k: str) -> int:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_import_mapping.py", "-q",
         "-p", "no:cacheprovider", "--tb=no", "-k", k],
        cwd=REPO / "backend", capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = [ln for ln in (r.stdout or "").splitlines() if "passed" in ln or "failed" in ln]
    print(f"      pytest -k {k} ⇒ rc={r.returncode} · {tail[-1] if tail else ''}")
    return r.returncode


def main() -> int:
    # ⚠️ **一律按字节读写** —— 用 `read_text/write_text` 会把 CRLF 悄悄转成 LF，
    #    于是"复原"后的 MD5 对不上（自测踩到过：逻辑复原了、MD5 却不等）。
    before = {p: p.read_bytes() for p in (MAP, STORE)}
    fail: list[str] = []

    print("基线（未变异）…")
    if run_pytest("import_mapping") != 0:
        fail.append("基线就是红的（尺子/实现有问题）")
        print("⛔ 基线红 ⇒ 停止（先让测试全绿再跑变异）")
        return 1

    for name, path, old, new, k in MUTATIONS:
        src = path.read_bytes()
        old_b, new_b = old.encode("utf-8"), new.encode("utf-8")
        if src.count(old_b) != 1:
            fail.append(f"锚点不唯一：{name}（找到 {src.count(old_b)} 处）")
            print(f"  ⚠️ 锚点不唯一，跳过：{name}")
            continue
        print(f"变异 {name} …")
        path.write_bytes(src.replace(old_b, new_b))
        try:
            if run_pytest(k) == 0:
                fail.append(f"变异未被抓到：{name}")
                print(f"      ⛔ 未被抓到 ⇒ 断言要修：{name}")
        finally:
            path.write_bytes(src)                               # 逐字节复原

    print("\n复原校验（MD5）…")
    for p, want in before.items():
        got = md5(p)
        ok = got == hashlib.md5(want).hexdigest()
        print(f"  {'✅' if ok else '⛔'} {p.name} · {got[:8]}{'' if ok else ' ≠ 原始'}")
        if not ok:
            fail.append(f"未复原：{p.name}")

    print()
    if fail:
        print("⛔ 未通过：")
        [print("   -", x) for x in fail]
        return 1
    print(f"✅ 反向灵敏度通过：{len(MUTATIONS)} 处变异**全部被抓到** · 源文件逐字节复原")
    return 0


if __name__ == "__main__":
    sys.exit(main())
