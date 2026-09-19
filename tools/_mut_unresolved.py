# -*- coding: utf-8 -*-
"""`TAIL-41`（未命中清单的新鲜度）—— **反向灵敏度**（变异测试）：改坏 ⇒ 断言必须变红。

⚠️ 每条变异：改坏 → 跑**指定那条断言**（期望 FAIL / ERROR）→ **按 bytes 复原** → 核 MD5。
⚠️ 锚点一律打在**被判据真正覆盖的那一处**（打偏 = 锚点错，不是断言假绿）。
⚠️ 子进程带 `PYTHONIOENCODING=utf-8` ＋ `CODEBUDDY_SAFE_DELETE_ENABLED=0`。

用法： backend/.venv/Scripts/python.exe tools/_mut_unresolved.py
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
PY = BACKEND / ".venv" / "Scripts" / "python.exe"

REPO = "backend/app/mod03_notice/repository.py"
DOM = "backend/app/mod03_notice/domain.py"
RT = "backend/app/mod03_notice/router.py"
# ⚠️ 2026-09-19（`T5` 拆件）：`get_fetch_executor` 的**实体**已搬到 `notice_executors.py`
#    （`router.py` 只再导出它）⇒ **动它执行器体内的变异要指新件**，⛔ 别再指 `router.py`（那会报"锚点未命中"＝未验证）。
EXEC = "backend/app/mod03_notice/notice_executors.py"
T = "tests/test_unresolved_freshness.py"

MUTS = [
    ("M1 退回「回溯历史记录」（最近一次已走完也照样把旧清单端出去 = TAIL-41 原地复发）", REPO,
     '        if detail.get("reason") != "ownership_unsettled":\n            return []',
     '        if detail.get("reason") != "ownership_unsettled":\n            continue',
     [T + "::test_抓取成功之后就没有未命中清单了"]),

    ("M2 写侧不写 `notice_fetch` 标记（读侧认不出「最近一次是哪一条」）", REPO,
     "    return {FETCH_MARK: True, **extra}\n",
     "    return {**extra}\n",
     [T + "::test_抓取成功之后就没有未命中清单了", T + "::test_只认付款通知书抓取的记录",
      T + "::test_三条结局都要写标记"]),

    ("M3 读侧信传入顺序（不按 id 取最新 ⇒ 离线和真机走两条路）", REPO,
     '    for r in sorted(recs, key=lambda x: getattr(x, "id", 0) or 0, reverse=True):\n',
     "    for r in recs:\n",
     [T + "::test_最近一次要按id判不许信传入顺序", T + "::test_抓取成功之后就没有未命中清单了"]),

    ("M4 清单不按当前档案现算（补过词 / 建过档的行还摆在清单里 ⇒ 用户白干）", DOM,
     '        if not getattr(d, "settled", False):\n',
     "        if True:\n",
     [T + "::test_已经补过词的行不再出现在清单里",
      T + "::test_现算走的是链路C同一个出口"]),

    ("M5 读端点不走现算过滤（把记录里那份**当时的判定**直接端出去）", RT,
     "        items = still_unsettled(latest_unresolved(session), projects)\n",
     "        items = latest_unresolved(session)\n",
     [T + "::test_读端点必须走现算过滤"]),

    ("M6 成功那一条结局绕过写侧出口（裸 `detail={...}` ⇒ 漏写标记）", EXEC,
     "                detail=fetch_detail(created=created, updated=updated, total=len(rows),\n"
     "                                    excluded=n_excluded),\n",
     '                detail={"created": created, "updated": updated, "total": len(rows),\n'
     '                        "excluded": n_excluded},\n',
     [T + "::test_三条结局都要写标记"]),
]


def _read(rel: str) -> bytes:
    return (ROOT / rel).read_bytes()


def _fit(rel: str, text: str) -> bytes:
    """按目标文件的**行尾习惯**归一（本仓源码行尾不统一 ⇒ ⛔ 不能硬用 `\\n`）。"""
    data = _read(rel)
    return (text.replace("\n", "\r\n") if b"\r\n" in data else text).encode("utf-8")


def main() -> int:
    rels = {REPO, DOM, RT, EXEC}
    base = {rel: _read(rel) for rel in rels}
    before = {rel: hashlib.md5(d).hexdigest() for rel, d in base.items()}
    print("基线 MD5:")
    for rel, h in before.items():
        print("   %-46s %s" % (rel, h))

    ok = fail = 0
    env = dict(os.environ, CODEBUDDY_SAFE_DELETE_ENABLED="0", PYTHONIOENCODING="utf-8")
    for name, rel, old, new, tests in MUTS:
        path = ROOT / rel
        ob, nb = _fit(rel, old), _fit(rel, new)
        cur = path.read_bytes()
        if ob not in cur:
            print("\n✗ SKIP %s —— 锚点没命中（`%s`）" % (name, old.strip().splitlines()[0][:60]))
            fail += 1
            continue
        path.write_bytes(cur.replace(ob, nb, 1))
        r = subprocess.run([str(PY), "-m", "pytest", "-q", *tests], cwd=str(BACKEND),
                           capture_output=True, text=True, encoding="utf-8", env=env)
        path.write_bytes(base[rel])
        restored = hashlib.md5(path.read_bytes()).hexdigest() == before[rel]
        red = r.returncode != 0
        good = red and restored
        ok += 1 if good else 0
        fail += 0 if good else 1
        print("\n%s %s" % ("✓" if good else "✗", name))
        print("     断言变红=%s  复原 MD5 一致=%s" % (red, restored))
        if not red:
            print("     ⚠️ 变异后仍然全绿 ⇒ **这条断言是假绿**，必须改紧！")

    print("\n--- 收尾核对 ---")
    for rel in rels:
        now = hashlib.md5((ROOT / rel).read_bytes()).hexdigest()
        assert now == before[rel], "%s 未逐字节复原！%s != %s" % (rel, now, before[rel])
        print("   %-46s 复原 ✓ %s" % (rel, now))
    print("\n结果：%d/%d 通过" % (ok, ok + fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
