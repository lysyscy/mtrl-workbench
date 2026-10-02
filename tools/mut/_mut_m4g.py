# -*- coding: utf-8 -*-
"""反向灵敏度（变异测试）：**导出项目参数保序去重**（`ACC-PRJ-AUTO-001/001-03` 的新边界）有没有区分力。

背景：真机跑通自动建档后才发现 —— 新建的**具体小微**与**壳共享同一个 `phid`**
⇒ `project_ids` 出现重复项（13 条档案 / 12 个唯一 phid）。这条隐患**离线断言原本看不见**
（断言只调函数，不看导出参数），所以必须专门证明"改回不去重 ⇒ 断言真的会红"。

做法：把实现**故意改坏** → 对应用例**必须变红** → 逐字节复原（MD5 校验）。
⚠️ 跑完**必须再跑一次全套 `pytest`**（否则 `acc_results.json` 留的是变异态）。
"""
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BK = ROOT / "backend"
REPO = BK / "app" / "mod01_projects" / "repository.py"
FS7 = BK / "app" / "mod07_setl" / "fetch_service.py"

T_AUTO = "tests/test_acc_prj_auto.py"

MUTS = [
    ("① 取数口**不去重**（壳与其下小微的 phid 出现两遍 ⇒ 项目被导出两遍）", REPO,
     "        if phid and phid not in seen:\n            seen.append(phid)\n",
     "        if phid:\n            seen.append(phid)\n",
     T_AUTO),
    ("② 空档案**不再报错**（拼出空串 ⇒ 可能导出全量）", REPO,
     "    if not seen:\n        raise MustReportError(\n", "    if False:\n        raise MustReportError(\n",
     T_AUTO),
    ("③ 抓取链路**又各写一份薄名**（⛔ 绕开唯一出口 —— 2026-10-02 `TAIL-218` 批 2 刚销掉的就是它）", FS7,
     "def unknown_warehouses(s: Session, rows: list[dict]) -> list[str]:\n",
     "def project_ids(s: Session) -> str:      #: ⛔ 变异：把批 2 销掉的那份薄名写回来\n"
     "    return P1S.export_phids(s)\n\n\n"
     "def unknown_warehouses(s: Session, rows: list[dict]) -> list[str]:\n",
     T_AUTO),
]


def _md5(p: pathlib.Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def _fit(raw: bytes, frag: bytes) -> bytes:
    """按目标文件归一此行尾（本仓行尾不统一 ⇒ 不归一会永远命中 0）。"""
    if b"\r\n" in raw and b"\r\n" not in frag:
        return frag.replace(b"\n", b"\r\n")
    if b"\r\n" not in raw and b"\r\n" in frag:
        return frag.replace(b"\r\n", b"\n")
    return frag


def main() -> int:
    print("=" * 78)
    print("反向灵敏度 · 导出项目参数保序去重（真机暴露的隐患）")
    print("=" * 78)
    files = {REPO, FS7}
    before = {p: _md5(p) for p in files}
    for p, m in before.items():
        print(f"  {p.relative_to(ROOT)}  {m}")
    print()

    red = skipped = 0
    for i, (title, path, old, new, target) in enumerate(MUTS, start=1):
        raw = path.read_bytes()
        frag = _fit(raw, old.encode("utf-8"))
        n = raw.count(frag)
        print(f"[{i}/{len(MUTS)}] {title}")
        if n != 1:
            print(f"    SKIP —— 锚点命中 {n} 次（应为 1）⇒ 锚点失效，请按新代码重写\n")
            skipped += 1
            continue
        path.write_bytes(raw.replace(frag, _fit(raw, new.encode("utf-8"))))
        try:
            r = subprocess.run([str(BK / ".venv" / "Scripts" / "python.exe"), "-m", "pytest",
                                "-q", target, "-x", "--no-header"],
                               cwd=BK, capture_output=True, text=True, timeout=300)
            ok = r.returncode != 0
            red += int(ok)
            print(f"    变异后 pytest rc={r.returncode} ⇒ {'✅ 如期变红' if ok else '❌ 仍绿（假绿！）'}")
            for ln in [x for x in (r.stdout or "").splitlines() if x.strip()][-2:]:
                print("      ", ln.strip()[:130])
        finally:
            path.write_bytes(raw)
        print()

    after = {p: _md5(p) for p in files}
    good = all(before[p] == after[p] for p in files)
    print("=" * 78)
    print(f"复原校验（逐字节）：{'✅ 全部一致' if good else '❌ 有文件残留被改'}")
    for p in files:
        print(f"  {p.relative_to(ROOT)}  {after[p]}  {'OK' if before[p] == after[p] else '!! 不一致'}")
    print(f"\n结论：如期变红 {red} · 锚点失效 {skipped} · 共 {len(MUTS)} 处")
    print("⚠️ 收尾必做：回 backend 再跑一次**全套** pytest")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
