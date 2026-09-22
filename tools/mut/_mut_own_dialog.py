"""反向灵敏度 · `TAIL-29`-② ④（链路 C 弹窗）。用法：`python tools/_mut_own_dialog.py`"""

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

MUTS = [
    (
        "M1 候选不过滤所属壳（会把别壳的小微也列出来）",
        DOM, "        if p.parent_shell_id == shell_id", "        if True",
        "test_候选小微按壳取且键是id",
    ),
    (
        "M2 候选的键不给 id（写操作就无法按 id 定位）",
        DOM, '            "id": p.id,', '            "id": 0,',
        "test_候选小微按壳取且键是id",
    ),
    (
        "M3 提交端点不做关键词校验（词不在单据名里也放行）",
        RTR,
        "        keyword = validate_keyword_in_doc(req.keyword, req.doc_name)",
        '        keyword = (req.keyword or "").strip()',
        "test_提交端点在且先校验再写",
    ),
    (
        "M4 补词直接赋值（覆盖原有关键词，而不是去重追加）",
        RTR,
        "                session, small, append_keyword_dedup(small.match_keywords, keyword)",
        "                session, small, [keyword]",
        "test_补词走去重追加而不是覆盖",
    ),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one(name: str) -> bool:
    r = subprocess.run(
        [str(PY), "-m", "pytest", "-q", f"tests/test_wired_own_dialog.py::{name}"],
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
