# -*- coding: utf-8 -*-
"""反向灵敏度（变异测试）—— `TAIL-39`「兜底前先查 i8 仓库名单」的断言。

做法：把实现**故意改坏**，确认对应断言**确实变红**；每处跑完**逐字节复原**并核 MD5。
⚠️ 跑 pytest 时结果**另写**一份（⛔ 别把全套的 `artifacts/acc_results.json` 冲掉）。

跑法（工程根）：`backend\\.venv\\Scripts\\python.exe tools\\_mut_ownwh.py`
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
BE = ROOT / "backend"
MUT_RESULTS = str(ROOT / "artifacts" / "_mut_acc_results.json")

MUTATIONS: list[dict] = [
    {
        "id": "M1", "file": "backend/app/web/index.html",
        "old": "    const seen = OWN_WH[i];\n    if (!seen) {\n      return toast('先点「<b>① 先查 i8 仓库名单</b>」",
        "new": "    const seen = OWN_WH[i];\n    if (false) {\n      return toast('先点「<b>① 先查 i8 仓库名单</b>」",
        "test": "tests/test_wired_own_wh.py", "k": "没查过不许建",
        "why": "**没查过也能建** ⇒ 用户照样凭猜填仓库名（这一环等于白做，假档案行照旧）",
    },
    {
        "id": "M2", "file": "backend/app/mod01_projects/domain.py",
        "old": "    return {\"found\": bool(matched), \"owners\": owners, \"matched\": matched, \"total\": total}",
        "new": "    return {\"found\": True, \"owners\": owners, \"matched\": matched, \"total\": total}   # 变异：永远算命中",
        "test": "tests/test_acc_prj_wh_check.py", "k": "查名单的三态",
        "why": "名单里没有也说「有」 ⇒ 用户以为 i8 里有这个仓库（最坏的一种假话）",
    },
    {
        "id": "M3", "file": "backend/app/mod03_notice/router.py",
        "old": "        rows, cached_at = wh_cache.load()",
        "new": "        rows, cached_at = None, \"\"   # 变异：不看上次名单（缓存兜底被去掉）",
        "test": "tests/test_acc_prj_wh_check.py", "k": "有上次缓存时用缓存",
        "why": "抓不到就直接认「没结果」⇒ 明明留着上次名单却不用（用户白等一次重试，`TAIL-39` 想要的兜底没了）",
    },
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run(test: str, k: str) -> int:
    env = dict(os.environ)
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
                "CODEBUDDY_SAFE_DELETE_ENABLED": "0", "ACC_RESULTS_PATH": MUT_RESULTS})
    r = subprocess.run([str(PY), "-m", "pytest", "-q", test, "-k", k, "-p", "no:cacheprovider",
                        "--no-header"], cwd=BE, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode


def main() -> int:
    ok = bad = 0
    for m in MUTATIONS:
        f = ROOT / m["file"]
        before = md5(f)
        raw = f.read_bytes()
        eol = b"\r\n" if b"\r\n" in raw else b"\n"
        needle = m["old"].encode("utf-8").replace(b"\n", eol)
        newb = m["new"].encode("utf-8").replace(b"\n", eol)
        cnt = raw.count(needle)
        if cnt != 1:
            print(f"❌ {m['id']} 变异点命中 {cnt} 次（须唯一）—— 源码已变，按现码重写锚点")
            bad += 1
            continue
        f.write_bytes(raw.replace(needle, newb))
        try:
            rc = run(m["test"], m["k"])
        finally:
            f.write_bytes(raw)
        same = md5(f) == before
        good = rc != 0 and same
        ok += 1 if good else 0
        bad += 0 if good else 1
        print(f"{m['id']} [TAIL-39 查名单] {'✅ 变红' if rc != 0 else '❌ 仍绿（断言没抓住！）'}"
              f"  rc={rc} · MD5复原={'是' if same else '否❗'}")
        print(f"    {m['file']} ← {m['why']}")
    Path(MUT_RESULTS).unlink(missing_ok=True)
    print(f"\n合计 {ok}/{len(MUTATIONS)} 中 · 源文件全部逐字节复原 = {'是' if bad == 0 else '否'}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
