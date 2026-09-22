# -*- coding: utf-8 -*-
"""反向灵敏度（变异测试）：`ACC-PRJ-SYNC-001/001-06` 新增的那两条断言有没有区分力。

做法：把实现**故意改坏** → 该断言**必须变红** → 逐字节复原（MD5 校验）。

⚠️ 本仓源码行尾不统一 ⇒ 片段按目标文件归一（`_fit`）。
⚠️ 跑完**必须再跑一次全套 `pytest`**（否则 `acc_results.json` 留的是变异态）。
"""
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BK = ROOT / "backend"
ARCHIVE = BK / "app" / "mod01_projects" / "archive.py"
TEST = "tests/test_acc_prj_sync.py"


def _md5(p: pathlib.Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def _fit(raw: bytes, frag: bytes) -> bytes:
    """把片段的行尾归一成目标文件的样子（LF 文件里塞 CRLF 片段 ⇒ 永远命中 0）。"""
    if b"\r\n" in raw and b"\r\n" not in frag:
        return frag.replace(b"\n", b"\r\n")
    if b"\r\n" not in raw and b"\r\n" in frag:
        return frag.replace(b"\r\n", b"\n")
    return frag


# (说明, 文件, 原文片段, 变异片段, 该变红的测试)
MUTS = [
    ("① 壳已在档时**不再列出**壳下未建档的小微（回到被静默吞掉的老行为）",
     ARCHIVE,
     "            if kind == TYPE_SHELL and gap_whs:\n",
     "            if False:\n",
     TEST),
    ("② 壳下小微**不看是否已建档**（已建过的反复催）",
     ARCHIVE,
     "        gap_whs = [w for w in whs if w not in taken]\n",
     "        gap_whs = list(whs)\n",
     TEST),
]


def main() -> int:
    print("=" * 78)
    print("反向灵敏度 · ACC-PRJ-SYNC-001/001-06（壳下具体小微的「显式列出」）")
    print("=" * 78)
    files = {ARCHIVE}
    before = {p: _md5(p) for p in files}
    print("变异前 MD5：")
    for p, m in before.items():
        print(f"  {p.relative_to(ROOT)}  {m}")
    print()

    hit = miss = 0
    for i, (title, path, old, new, tgt) in enumerate(MUTS, start=1):
        raw = path.read_bytes()
        frag = _fit(raw, old.encode("utf-8"))
        n = raw.count(frag)
        print(f"[{i}/{len(MUTS)}] {title}")
        if n != 1:
            print(f"    SKIP —— 锚点命中 {n} 次（应为 1），锚点会随代码演进而失效，请重写\n")
            miss += 1
            continue
        path.write_bytes(raw.replace(frag, _fit(raw, new.encode("utf-8"))))
        try:
            r = subprocess.run([str(BK / ".venv" / "Scripts" / "python.exe"), "-m", "pytest",
                                "-q", tgt, "-x", "--no-header"],
                               cwd=BK, capture_output=True, text=True, timeout=300)
            ok = r.returncode != 0
            tail = [ln for ln in (r.stdout or "").splitlines() if ln.strip()][-2:]
            print(f"    变异后 pytest rc={r.returncode} ⇒ {'✅ 如期变红' if ok else '❌ 仍绿（假绿！）'}")
            for ln in tail:
                print("      ", ln.strip()[:140])
            hit += int(ok)
            miss += int(not ok)
        finally:
            path.write_bytes(raw)
        print()

    print("=" * 78)
    after = {p: _md5(p) for p in files}
    restored = all(before[p] == after[p] for p in files)
    print(f"复原校验（逐字节）：{'✅ 全部一致' if restored else '❌ 有文件被改动残留'}")
    for p in files:
        print(f"  {p.relative_to(ROOT)}  {after[p]}  {'OK' if before[p] == after[p] else '!! 不一致'}")
    print(f"\n结论：如期变红 {hit} / 锚点失效 {miss - (len(MUTS) - hit - miss) if False else miss}")
    print("⚠️ 收尾必做：回 backend 再跑一次**全套** pytest（清掉变异态留下的 acc_results.json）")
    return 0 if restored else 1


if __name__ == "__main__":
    sys.exit(main())
