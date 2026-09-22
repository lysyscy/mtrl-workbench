# -*- coding: utf-8 -*-
"""反向灵敏度（变异测试）—— `ACC-PRJ-OWN-001/001-10·001-11` ＋ `ACC-CFG-RULE-001/001-06·001-08`。

做法：把实现**故意改坏**，确认对应断言**确实变红**；每处跑完**逐字节复原**并核 MD5。
⚠️ 变异点一律**不是**"无害变异"（那种改了行为不变、断言当然不红 —— 会假装"检验过了"）：
    每一处都**真的改变行为**，且**不改动被测断言的锚字符串本身**。

跑法（工程根）：`backend\\.venv\\Scripts\\python.exe tools\\_mut_owncfg.py`
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
BE = ROOT / "backend"

#: 变异跑 pytest 时**另写一份结果文件** —— ⛔ 别把全套的 `artifacts/acc_results.json` 冲掉
#: （冲掉之后 `acc_report` 会把大半判据点读成"未绑定"，看起来像出了大事）。
#: ⚠️ **必须给绝对路径**：pytest 的 cwd = `backend/` ⇒ 相对路径会落到 `backend/artifacts/`，
#:    而本脚本按仓根删（两边对不上 ⇒ 临时文件留在库里、还会被 `git add -A` 带进提交 —— 实测踩到一次）。
MUT_RESULTS = str(ROOT / "artifacts" / "_mut_acc_results.json")

MUTATIONS: list[dict] = [
    {
        "id": "M1",
        "point": "ACC-PRJ-OWN-001/001-10",
        "file": "backend/app/mod03_notice/repository.py",
        "old": 'return []                      # ⭐ 最近一次**已走完** ⇒ 没有清单（⛔ 不回溯更早的）',
        "new": 'continue                       # 变异：退回"回溯更早的记录"那个旧行为',
        "test": "tests/test_unresolved_freshness.py",
        "k": "抓取成功之后",
        "why": "「最近一次已走完 ⇒ 没有清单」改成 continue ⇒ 退回回溯 ⇒ 旧清单又冒出来",
    },
    {
        "id": "M2",
        "point": "ACC-PRJ-OWN-001/001-11",
        "file": "backend/app/mod03_notice/domain.py",
        "old": '        if not getattr(d, "settled", False):\n            out.append(it)',
        "new": '        if True:                       # 变异：不按当前档案现算，原样端出去\n            out.append(it)',
        "test": "tests/test_unresolved_freshness.py",
        "k": "已经补过词",
        "why": "现算过滤失效 ⇒ 已能归属的行仍留在清单里（用户对着已解决的白干）",
    },
    {
        "id": "M3",
        "point": "ACC-CFG-RULE-001/001-08",
        "file": "backend/app/mod03_notice/rules_repository.py",
        "old": '    classify.validate_rules([classify.ExcludeRule(kind=str(kind or ""), values=tuple(values))])',
        "new": '    return None                    # 变异：写前不校验（非法写法也照写）',
        "test": "tests/test_rules_store.py",
        "k": "非法写法",
        "why": "写前校验没了 ⇒ 非法类别 / 空命中值都能写进去（并且真落行）",
    },
    {
        "id": "M4",
        "point": "ACC-CFG-RULE-001/001-08",
        "file": "backend/app/mod14_config/rules_api.py",
        "old": '@router.post("/api/m14/rules")',
        "new": '@router.post("/api/m14/rules", status_code=400)   # 变异：拒绝走 4xx',
        "test": "tests/test_rules_store.py",
        "k": "规则端点已注册",
        "why": "写侧改成 4xx ⇒ 约定「恒 200 ＋ ok 标志」被破坏（那句中文原因会丢）",
    },
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run(test: str, k: str) -> int:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["ACC_RESULTS_PATH"] = MUT_RESULTS
    r = subprocess.run([str(PY), "-m", "pytest", "-q", test, "-k", k,
                        "-p", "no:cacheprovider", "--no-header", "-x"],
                       cwd=BE, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode


def main() -> int:
    ok, bad = 0, 0
    for m in MUTATIONS:
        f = ROOT / m["file"]
        before = md5(f)
        raw = f.read_bytes()
        # ⚠️ 行尾归一：本仓源码 LF / CRLF 混杂 ⇒ 按 `\n` 找、按找到的原文长度切（不整文件转行尾）
        needle = m["old"].encode("utf-8")
        idx = raw.find(needle)
        if idx < 0:
            print(f"❌ {m['id']} 变异点没命中（{m['file']}）—— 源码可能已变，按现码重写锚点")
            bad += 1
            continue
        if raw.count(needle) != 1:
            print(f"❌ {m['id']} 变异点命中 {raw.count(needle)} 次（须唯一）")
            bad += 1
            continue

        f.write_bytes(raw[:idx] + m["new"].encode("utf-8") + raw[idx + len(needle):])
        try:
            rc = run(m["test"], m["k"])
        finally:
            f.write_bytes(raw)
        same = md5(f) == before

        verdict = "✅ 变红" if rc != 0 else "❌ 仍绿（断言没抓住！）"
        if rc != 0 and same:
            ok += 1
        else:
            bad += 1
        print(f"{m['id']} [{m['point']}] {verdict}  rc={rc} · MD5复原={'是' if same else '否❗'}")
        print(f"    {m['file']} ← {m['why']}")

    leftover = ROOT / MUT_RESULTS
    if leftover.exists():
        leftover.unlink()
    print(f"\n合计 {ok}/{len(MUTATIONS)} 中 · 源文件全部逐字节复原 = {'是' if bad == 0 else '否'}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
