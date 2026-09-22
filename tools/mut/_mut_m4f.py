# -*- coding: utf-8 -*-
"""反向灵敏度（变异测试）：链路 B（`ACC-PRJ-AUTO-001` 7 点 ＋ `ACC-SETL-FETCH-001/001-10`）的断言有没有区分力。

做法：把实现**故意改坏** → 对应用例**必须变红** → 逐字节复原（MD5 校验）。
⚠️ 跑完**必须再跑一次全套 `pytest`**（否则 `acc_results.json` 留的是变异态）。
"""
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BK = ROOT / "backend"
REC = BK / "app" / "mod01_projects" / "recovery.py"
REPO = BK / "app" / "mod01_projects" / "repository.py"
FS7 = BK / "app" / "mod07_setl" / "fetch_service.py"

T_AUTO = "tests/test_acc_prj_auto.py"
T_SETL = "tests/test_acc_setl_fetch.py"

MUTS = [
    ("① 壳下**不建**具体小微（陌生仓库永远进不了档案）", REC,
     "        if shells:\n", "        if False:\n", T_AUTO),
    ("② 占位行**不扶正**（拿到真实名也不认）", REC,
     "        if current.startswith(PLACEHOLDER_PREFIX):\n", "        if False:\n", T_AUTO),
    ("③ 扶正后**展示名不跟着换**（屏幕一直挂「未建仓-N」）", REPO,
     '    if str(project.disp or "") == old:\n', "    if False:\n", T_AUTO),
    ("④ 取数失败**不再降级**（异常直接冒出去，把抓取拖挂）", REC,
     "    except Exception as exc:                              # noqa: BLE001 —— 降级，不抛\n",
     "    except ZeroDivisionError as exc:                      # noqa: BLE001 —— 降级，不抛\n",
     T_AUTO),
    ("⑤ 扶正口**不再拒绝真实名**（人工改仓库名的后门被打开）", REPO,
     "    if not old.startswith(PLACEHOLDER_PREFIX):\n", "    if False:\n", T_AUTO),
    ("⑥ 收发结存抓取**根本不调用**自动建档（回到「只报不建」）", FS7,
     "    recovery_result = recover_unknown_warehouses(\n"
     "        s, unknown_wh=unknown, load_warehouse_rows=_wh_loader(wh_rows), operator=operator)\n",
     "    recovery_result = {\"promote\": 0, \"create\": 0, \"unresolved\": 0, \"promoted\": [],\n"
     "                       \"created\": [], \"unresolved_items\": [], \"degraded\": False, \"message\": \"\"}\n",
     T_SETL),
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
    print("反向灵敏度 · 链路 B（材料侧自动扶正）")
    print("=" * 78)
    files = {REC, REPO, FS7}
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
