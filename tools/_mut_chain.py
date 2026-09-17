"""反向灵敏度（链路对账）—— 证明 `chain_audit` 的每一把尺子**真的有区分力**。

做法：逐次把**源代码/真源/认领表**故意改坏一处 ⇒ 断言**对应的那条红确实出现/消失** ⇒ 逐字节复原（MD5）。
⚠️ 本尺子**本来就红** ⇒ 不能只看 `rc`：必须断言"**那条具体的红**"。

    python tools/_mut_chain.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
EXP = ROOT / "tools" / "chain_expected.txt"
SRC = ROOT / "tools" / "chain_sources.txt"


def run() -> dict:
    p = subprocess.run([str(PY), str(ROOT / "tools" / "chain_audit.py"), "--json"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return json.loads(p.stdout)


def md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def main() -> int:
    exp0, src0 = EXP.read_bytes(), SRC.read_bytes()
    h_exp, h_src = md5(exp0), md5(src0)
    hits = 0

    def expect(name: str, needle: str, *, must: bool = True) -> None:
        nonlocal hits
        d = run()
        found = any(needle in r for r in d["red"])
        good = found is must
        print(f"  {'✅' if good else '❌'} {name} —— 期望{'出现' if must else '消失'}「{needle[:34]}」"
              f" ⇒ {'命中' if found else '未见'}")
        hits += 1 if good else 0
        EXP.write_bytes(exp0)
        SRC.write_bytes(src0)

    # M1 · C3 落点名字写错 ⇒ 报「落点名字在文件里找不到」
    EXP.write_text(exp0.decode("utf-8").replace(
        "print/ipp.py::send_pdf", "print/ipp.py::send_pdf_TYPO"), encoding="utf-8")
    expect("M1 落点名字写错", "落点名字在文件里找不到")

    # M2 · C2 文档锚改一字 ⇒ 报「文档锚在真源里找不到」
    EXP.write_text(exp0.decode("utf-8").replace(
        "勾选通知书 → 点「批量打印」", "勾选通知书 → 点「批量打印X」"), encoding="utf-8")
    expect("M2 文档锚改一字", "文档锚在真源里找不到")

    # M3 · C1 链路代码未注册 ⇒ 报「没在 chain_sources.txt 注册」
    SRC.write_text(src0.decode("utf-8").replace(
        "P5|批量打印与只导出 PDF", "# P5|批量打印与只导出 PDF"), encoding="utf-8")
    expect("M3 链路代码未注册", "没在 chain_sources.txt 注册")

    # M4 · ⭐ 把 P1 那条「缺」认成「已接」⇒ 该红项**必须消失**（证明"修好能销号"）
    fixed = exp0.decode("utf-8").replace(
        "|指定项目不在统计范围|—|缺：需补判据（链路级）|缺",
        "|指定项目不在统计范围|backend/app/mod03_notice/router.py::apply_fetched_row|ACC-PRJ-OWN-001|已接")
    before = len(run()["red"])
    EXP.write_text(fixed, encoding="utf-8")
    d_after = run()
    hit = not any("整批校验**前**先剔掉规则剔除栏" in r or "整批校验**前**先剔掉规则剔除行" in r
                  for r in d_after["red"])
    print(f"  {'✅' if hit else '❌'} M4 把 P1 的「缺」改成「已接」—— 该分支从红里消失"
          f"（红 {before} → {len(d_after['red'])}）")
    hits += 1 if hit else 0
    EXP.write_bytes(exp0)

    # M5 · C6 覆盖哨：把 P1 全部认领行删掉 ⇒ 报「没有任何认领行」
    keep = [l for l in exp0.decode("utf-8").splitlines() if not l.startswith("P1|")]
    EXP.write_text("\n".join(keep) + "\n", encoding="utf-8")
    d = run()
    hit = any(s["chain"] == "P1" and s["total"] == 0 for s in d["summary"])
    print(f"  {'✅' if hit else '❌'} M5 删掉 P1 全部认领行 —— 总览里 P1 变「没有任何认领行」")
    hits += 1 if hit else 0
    EXP.write_bytes(exp0)

    # 逐字节复原校验
    ok = md5(EXP.read_bytes()) == h_exp and md5(SRC.read_bytes()) == h_src
    print(f"\n  复原校验：认领表 {'✅' if ok else '❌'} · 真源注册表 {'✅' if ok else '❌'}"
          f"（MD5 逐字节）")
    print(f"\n  反向灵敏度：**{hits}/5 命中**")
    return 0 if (hits == 5 and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
