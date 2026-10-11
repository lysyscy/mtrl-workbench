# -*- coding: utf-8 -*-
"""反向灵敏度（变异测试）—— `TAIL-40` 剔除规则落库的**后端断言**是否真有区分力。

用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_mut_rules.py`

⚠️ 纪律（见 memory §十七 / 细则 §十七）：一律走 bytes · 变异点必须**唯一命中** · 默认重跑全套（`--no-full-suite` 显式跳过，不刷新权威四态） · 末尾核 MD5。
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
FILES = {
    "repo": ROOT / "backend" / "app" / "mod03_notice" / "rules_repository.py",
    "router": ROOT / "backend" / "app" / "mod03_notice" / "notice_executors.py",
    "classify": ROOT / "backend" / "app" / "mod03_notice" / "classify.py",
    "api": ROOT / "backend" / "app" / "mod14_config" / "rules_api.py",
}

MUTATIONS: list[tuple[str, str, str, str, str]] = [
    ("分隔符只认全角（半角命中值会被当成一个超长值 ⇒ 静默不命中）",
     "repo", 'ALT_SEPS = ("|", "｜", "，", ",")', 'ALT_SEPS = ("｜",)',
     "test_命中值分隔符全角为主_半角也认"),
    ("库空不再回落出厂默认（首装静默偏离 §4.2.2）",
     "repo", "    return rules if rules else classify.DEFAULT_RULES", "    return rules",
     "test_库空回落到出厂默认"),
    ("幂等初始化不再判空（会重复灌出厂默认）",
     "repo", "    if all_rows(s):\n        return 0", "    if False:\n        return 0",
     "test_幂等初始化不会重复落库"),
    ("库行转判定值时不过 split_values（命中值结构走形）",
     "repo", "return classify.ExcludeRule(kind=str(row.kind or \"\"), values=split_values(row.values))",
     "return classify.ExcludeRule(kind=str(row.kind or \"\"), values=(str(row.values),))",
     "test_库行转判定值时对象是_excludeRule"),
    ("抓取管线只喂一处（另一处回落到默认 ⇒ 两处判据分叉）",
     "router", "        need_own = rows_needing_ownership(rows, rules)",
     "        need_own = rows_needing_ownership(rows)",
     "test_抓取管线读到规则并同时喂给两处"),
    ("抓取管线顺带调写库的初始化（破坏「抓取纯读」）",
     "router", "            rules = effective_rules(session)",
     "            rules = (ensure_seeded(session), effective_rules(session))[1]",
     "test_抓取管线不得调幂等初始化"),
    ("付款域反向 import 配置域（成环风险）",
     "repo", "from app.mod03_notice import classify",
     "from app.mod03_notice import classify\nfrom app.mod14_config import models as _m14bad",
     "test_付款域不反向依赖配置域"),
    ("出厂默认里混进一条非法规则（空命中值 ⇒ 灌进库后改都改不动）",
     "classify", '    ExcludeRule(KIND_INPUT_BY, ("梁丽佳",)),',
     '    ExcludeRule(KIND_INPUT_BY, ("梁丽佳",)),\n    ExcludeRule(KIND_BILL_NAME, ()),',
     "test_出厂默认本身必须合法"),
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
        target = orig[fkey]
        o = _fit(old.encode("utf-8"), target)
        n = _fit(new.encode("utf-8"), target)
        cnt = target.count(o)
        if cnt != 1:
            print(f"  {i:2d}. ⚠️ SKIP（变异点命中 {cnt} 次 —— 先收紧锚）—— [{fkey}] {label}")
            miss += 1
            continue
        FILES[fkey].write_bytes(target.replace(o, n))
        r = subprocess.run([str(PY), "-m", "pytest", "-q", "-k", test_name, "tests/"],
                           cwd=ROOT / "backend", capture_output=True, text=True)
        bad = r.returncode != 0
        print(f"  {i:2d}. {'✅ 变红' if bad else '⛔ 仍绿（假绿！）'} —— [{fkey}] {label}  [{test_name}]")
        if bad:
            hit += 1
        FILES[fkey].write_bytes(target)

    md5_after = {k: hashlib.md5(p.read_bytes()).hexdigest() for k, p in FILES.items()}
    ok_md5 = all(md5_after[k] == md5_before[k] for k in FILES)
    print(f"\n命中 {hit}/{len(MUTATIONS) - miss} · SKIP {miss} · "
          f"MD5 {'逐字节复原 ✅' if ok_md5 else '⛔ 不一致'}")

    if "--no-full-suite" in sys.argv:
        print("跳过全套 pytest（--no-full-suite）：本轮不刷新权威四态")
        full_rc = 0
    else:
        print("重跑全套 pytest（复原态）…")
        full = subprocess.run([str(PY), "-m", "pytest", "-q", "tests/"],
                              cwd=ROOT / "backend", capture_output=True, text=True)
        print("  全套 pytest 退出码 =", full.returncode)
        full_rc = full.returncode
    return 0 if (ok_md5 and miss == 0 and hit == len(MUTATIONS) and full_rc == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
