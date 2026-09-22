"""反向灵敏度 · `TAIL-29`-③（抓取链路接自动建档）。

用法：`python tools/_mut_archive_chain.py`
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
PY = BACKEND / ".venv" / "Scripts" / "python.exe"
DOM = BACKEND / "app" / "mod01_projects" / "domain.py"
RTR = BACKEND / "app" / "mod03_notice" / "router.py"

# (说明, 文件, 原名, 改成, 期望变红的测试)
MUTS = [
    (
        "M1 永不建档（= 修之前的行为）",
        DOM,
        '    return any(d.kind == "not_archived" for d in decisions)',
        "    return False",
        "test_有未建档的行就要走建档",
    ),
    (
        "M2 把「未命中关键词」也当成要建档（混淆链路 A 与链路 C）",
        DOM,
        '    return any(d.kind == "not_archived" for d in decisions)',
        '    return any(d.kind in ("not_archived", "needs_keyword") for d in decisions)',
        "test_未命中关键词不触发建档",
    ),
    (
        "M3 建档后不重判（新档案不生效）",
        RTR,
        '            if not archive_out.get("degraded"):\n                judged = _judge()',
        '            if not archive_out.get("degraded"):\n                pass',
        "test_顺序是判定到建档再到重判",
    ),
    (
        "M4 建档不复用会话（会额外登录 = 多一次强踢）",
        RTR,
        "load_common=lambda: cp_loader(allow_kick, client),",
        "load_common=lambda: cp_loader(allow_kick),",
        "test_建档复用同一个i8会话不额外登录",
    ),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one(name: str) -> bool:
    r = subprocess.run(
        [str(PY), "-m", "pytest", "-q", f"tests/test_wired_archive_chain.py::{name}"],
        cwd=str(BACKEND), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    return r.returncode == 0


def main() -> int:
    files = sorted({m[1] for m in MUTS})
    before = {p: (p.read_bytes(), md5(p)) for p in files}
    hits = 0
    try:
        for desc, path, old, new, expect in MUTS:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
            assert text.count(old) == 1, f"{desc}：锚串命中 {text.count(old)} 次，脚本停手"
            path.write_bytes(text.replace(old, new, 1).encode("utf-8"))
            passed = run_one(expect)
            if not passed:
                hits += 1
            print(f"  {'✅ 命中（变红）' if not passed else '❌ 未命中（仍绿 ⇒ 假绿！）'}  {desc}")
            path.write_bytes(raw)
    finally:
        ok = all(p.read_bytes() == before[p][0] for p in files)
        print(f"\n  反向灵敏度：{hits}/{len(MUTS)} 命中")
        print(f"  复原校验（MD5 逐字节）：{'✅ 全部复原' if ok else '❌ 没复原！'}")
        for p in files:
            print(f"      {p.relative_to(ROOT)}  md5={md5(p)}")
    return 0 if hits == len(MUTS) else 1


if __name__ == "__main__":
    sys.exit(main())
