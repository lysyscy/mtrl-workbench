"""`TAIL-235` · 甲1 · 留痕层收口（**干跑优先** · 每步可单独执行）。

三个动作（彼此独立，`--only A|B|C` 可单跑）：

  **A · 归一逐日日志**（执行既有口径 `work/README.md` §五「journal 是**唯一**的逐日日志」）
      实测病：git **同时跟踪两份**同名日志 —— `.codebuddy/memory/2026-09-24.md …`（10 件，
      CRLF）＋ `.codebuddy/memory/journal/2026-09-24.md …`（9 件，LF），**9 件逐行内容完全相同**
      ⇒ 同一个日志两处写（`T12` 判了 10 条黄）。成因 = `MEMORY.md` §六 把 journal 写成「旧代」。
      做法：先把 journal 下的旧副本**备份到仓外**（防中途失败两边都没了）⇒ 删副本 ⇒ `git mv` 根下 10 件进 journal/。

  **B · 归档件移仓外**：`plans/archive/` 全部（26 件 · 27,976 行）⇒ `D:\\dev\\.归档-mtrl\\plans-archive\\`
      ⚠️ `git mv` **不能移出仓库** ⇒ 分两步：`git rm -r --cached`（从索引摘除，工作区留）
      ＋ 文件系统 `shutil.move`。**可逆机制** = 内容仍在 git 历史里（`git show HEAD:<路径>`）
      ⇒ 回退 = `git checkout HEAD -- <路径>`（索引件里写清）。

  **C · 旧版《说明书》移仓外**：`backups/TRUTH-REVERTED-c010b0-材料科业务全流程说明书-20260921.md`
      （2,819 行 · 被 WPS 云同步回退的旧版，2026-10-05 已用真源恢复并销号 `TAIL-231`）
      ⇒ `D:\\dev\\.归档-mtrl\\backups\\`。`backups/` 是 gitignored ⇒ 纯文件系统移动。

⛔ **不搬 `memory/journal/`**：它是**现役**逐日日志（`README.md` §二③「现役 · 随仓走」·
   `pack.ps1` 产包含 `memory/**`）⇒ 搬走当天就没地方写日志。收口办法见 `TAIL-235` 乙批（轮转判据）。

用法（默认干跑）：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail235_j1.py
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail235_j1.py --apply --only A
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEM = ROOT / ".codebuddy" / "memory"
JOURNAL = MEM / "journal"
ARCHIVE = ROOT / ".codebuddy" / "plans" / "archive"
OUT = Path(r"D:\dev\.归档-mtrl")
OLD_SPEC = ROOT / ".codebuddy" / "backups" / "TRUTH-REVERTED-c010b0-材料科业务全流程说明书-20260921.md"


def git(*args: str) -> tuple[int, str]:
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout + p.stderr).strip()


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def lines(p: Path) -> int:
    return len(p.read_text(encoding="utf-8", errors="replace").splitlines())


def do_a(apply: bool) -> None:
    """归一逐日日志：根下 N 件 ⇒ journal/（journal 下的旧副本先备份到仓外再删）。"""
    roots = sorted(MEM.glob("20*.md"))
    print(f"\n{'=' * 78}\n A · 归一逐日日志（执行「journal 是唯一逐日日志」）\n{'=' * 78}")
    print(f"  memory/ 根下 {len(roots)} 件 · journal/ 下 {len(list(JOURNAL.glob('*.md')))} 件")
    for p in roots:
        q = JOURNAL / p.name
        note = ""
        if q.exists():
            a = p.read_text(encoding="utf-8", errors="replace").splitlines()
            b = q.read_text(encoding="utf-8", errors="replace").splitlines()
            note = "✅ 内容逐行相同（副本）" if a == b else "⚠️⚠️ 内容不同！以根下为准，但请人核"
        print(f"  · {p.name}  {lines(p):>5,} 行  {p.stat().st_size:>9,} B  {note}")
    if not apply:
        print("  ⏱ 干跑（加 --apply 落盘）")
        return
    # ① 旧副本先备份到仓外（防中途失败）
    if list(JOURNAL.glob("*.md")):
        bak = OUT / "memory-journal-重复副本"
        bak.mkdir(parents=True, exist_ok=True)
        for p in sorted(JOURNAL.glob("*.md")):
            shutil.copy2(p, bak / p.name)
            print(f"  ① 旧副本已备份 → {bak / p.name}")
    # ② 删 journal 下的旧副本（索引 + 工作区）
    for p in sorted(JOURNAL.glob("*.md")):
        rc, out = git("rm", "--cached", "-q", "--", str(p.relative_to(ROOT)).replace("\\", "/"))
        if rc != 0:
            print(f"  ⚠️ git rm --cached 失败：{out}")
        p.unlink()
    print(f"  ② journal/ 下旧副本已删（{len(list(JOURNAL.glob('*.md')))} 件剩余）")
    # ③ git mv 根下 → journal/
    for p in roots:
        rc, out = git("mv", str(p.relative_to(ROOT)).replace("\\", "/"),
                      str((JOURNAL / p.name).relative_to(ROOT)).replace("\\", "/"))
        print(f"  ③ git mv {p.name} → journal/  rc={rc} {out[:80]}")


def do_b(apply: bool) -> None:
    """归档件移仓外。"""
    files = sorted(ARCHIVE.rglob("*.md"))
    tot = sum(lines(f) for f in files)
    print(f"\n{'=' * 78}\n B · 归档件移仓外（plans/archive/）\n{'=' * 78}")
    print(f"  {len(files)} 件 · {tot:,} 行 · {sum(f.stat().st_size for f in files):,} 字节"
          f"  ⇒ 目标 {OUT / 'plans-archive'}")
    for f in files:
        print(f"  · {f.relative_to(ARCHIVE).as_posix()}")
    if not apply:
        print("  ⏱ 干跑（加 --apply 落盘）")
        return
    dest = OUT / "plans-archive"
    dest.mkdir(parents=True, exist_ok=True)
    for f in files:
        rel = f.relative_to(ARCHIVE)
        d = dest / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        before = md5(f)
        shutil.move(str(f), str(d))
        after = md5(d)
        print(f"  {'✅' if before == after else '❌'} {rel.as_posix()}  md5 {before[:12]}"
              f"{' 一致' if before == after else ' 不一致！'}")
    rc, out = git("rm", "-r", "--cached", "-q", "--", ".codebuddy/plans/archive")
    print(f"  git rm -r --cached .codebuddy/plans/archive  rc={rc} {out[:100]}")


def do_c(apply: bool) -> None:
    """旧版《说明书》移仓外。"""
    print(f"\n{'=' * 78}\n C · 旧版《说明书》移仓外（backups/）\n{'=' * 78}")
    if not OLD_SPEC.exists():
        print(f"  ⚠️ 不存在：{OLD_SPEC.name}")
        return
    print(f"  · {OLD_SPEC.name}  {lines(OLD_SPEC):,} 行 · {OLD_SPEC.stat().st_size:,} 字节"
          f"  ⇒ 目标 {OUT / 'backups'}")
    if not apply:
        print("  ⏱ 干跑（加 --apply 落盘）")
        return
    dest = OUT / "backups"
    dest.mkdir(parents=True, exist_ok=True)
    before = md5(OLD_SPEC)
    shutil.move(str(OLD_SPEC), str(dest / OLD_SPEC.name))
    after = md5(dest / OLD_SPEC.name)
    print(f"  {'✅' if before == after else '❌'} 移动完成 md5 {before[:12]}")


def do_d(apply: bool) -> None:
    """甲2 + 丙（用户 2026-10-05 点头：激进档 ＋ 全清 6 件）—— 零机器引用的设计件 ＋ ops 实测类。

    ⚠️ **只搬「机器引用 0」的**：`10-designs` 里另有 9 件被测试/代码钉着（分层门禁/识别样本/…）⇒ 碰了 pytest 会红。
    ⚠️ 保留 `设计-表格筛选配置化-20260924.md`（809 行 · `TAIL-64` 未做完的 P4-c/P5-c 还要它 · 用户裁定保留）。
    """
    live: list[tuple[str, str]] = []
    # ⚠️⚠️ 口径**必须与量测件 `_tail235_list.py` 一致**（踩过两次：先漏 `ops/*.ps1`／`rules/*.mdc`，
    #    又漏整个 `.js/.html`）⇒ 「机器引用」= 活机器 ＝ `backend/app`·`backend/tests`
    #    ·`tools/audit|mut|probe`·`ops/*.ps1`·`.codebuddy/rules/*.mdc` ＋ 壳的 `js/html`。
    srcs = [p for d in ("backend/app", "backend/tests", "tools/audit", "tools/mut",
                        "tools/probe", "backend/app/web") for p in (ROOT / d).rglob("*")]
    srcs += list((ROOT / "ops").glob("*.ps1")) + list((ROOT / ".codebuddy/rules").rglob("*.mdc"))
    for p in srcs:
        if p.is_file() and p.suffix in (".py", ".ps1", ".js", ".html", ".mdc"):
            live.append((p.name, p.read_text(encoding="utf-8", errors="replace")))
    kept, designs = [], []
    for p in sorted((ROOT / ".codebuddy/work/10-designs").glob("*.md")):
        if p.name == "设计-表格筛选配置化-20260924.md":
            kept.append((p.name, "用户裁定保留（TAIL-64 P4-c/P5-c）"))
            continue
        hit = [n for n, t in live if p.stem in t]
        (designs.append(p) if not hit else kept.append((p.name, f"机器引用 {len(hit)} 处")))
    print(f"  ⛔ **不搬**的 {len(kept)} 件（供核对）：")
    for n, why in kept:
        print(f"      · {n}  —— {why}")
    ops_go = [p for n in ("宿主hooks-实测结论.md", "i8-名单同步实测结论.md",
                          "M0-0B-渲染实测结论.md", "原型断言-归属映射.md")
              for p in sorted((ROOT / "ops").glob(n))]
    ops_go += sorted((ROOT / "ops/实测快照").glob("*.json"))
    items = [("work-10-designs", p) for p in designs] + [("ops", p) for p in ops_go]
    print(f"\n{'=' * 78}\n D · 甲2 ＋ 丙（零机器引用 ⇒ 移仓外）\n{'=' * 78}")
    print(f"  设计件 {len(designs)} 件 ＋ ops {len(ops_go)} 件 = {len(items)} 件")
    for p in designs + ops_go:
        print(f"  · {p.relative_to(ROOT).as_posix()}  {lines(p):>5,} 行")
    if not apply:
        print("  ⏱ 干跑（加 --apply 落盘）")
        return
    for bucket, p in items:
        dest = OUT / bucket / p.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        before = md5(p)
        rel = p.relative_to(ROOT).as_posix().replace("\\", "/")
        # ⛔⛔ 逐件摘索引（**不能** `git rm -r --cached <目录>` —— 那会把同目录里
        #    **用户裁定保留**的 `设计-表格筛选配置化-20260924.md` 一起摘掉）。
        if git("ls-files", "--error-unmatch", "--", rel)[0] == 0:
            rc, out = git("rm", "--cached", "-q", "--", rel)
            if rc != 0:
                print(f"  ⚠️ git rm --cached 失败 {rel}：{out[:80]}")
        else:
            print(f"  · 未被 git 跟踪（跳过摘索引）：{rel}")
        shutil.move(str(p), str(dest))
        ok = "✅" if before == md5(dest) else "❌"
        print(f"  {ok} {bucket}/{p.name}  md5 {before[:12]}")


def _rewrite(rel: str, fn) -> bool:
    """按行改一个 md/ps1。⚠️ **`newline=""`** —— 否则 `read_text` 会把 CRLF 归一成 LF、
    落盘后**整个文件行尾都变** ⇒ `git diff` 全文变红（本仓 `core.autocrlf=true`）。"""
    p = ROOT / rel
    raw = p.read_text(encoding="utf-8", newline="")
    lines = raw.split("\n")
    out = fn(lines)
    if out == lines:
        print(f"  · {rel} 无需改")
        return False
    p.write_text("\n".join(out), encoding="utf-8", newline="")
    print(f"  ✅ {rel} 已改（{len(lines)} → {len(out)} 行）")
    return True


def do_e(apply: bool) -> None:
    """E · 同批改**活指针**（甲2/丙 搬走的那 28 件在活文档里还指着的地方）。

    ⛔ **主文档不改**：它在 `§13.6` 那些**超长历史行**里记着"当时做了啥"（每行几千字），
       逐处改会加重它已超的 1800 行预算（`T10`/`T13`）⇒ 按「留痕不改成失真」的老办法，
       **在归档索引件里如实记账**。`T3`（幽灵路径）照不到 `.codebuddy/` ⇒ 不影响判据。
    """
    gone = ("宿主hooks-实测结论", "i8-名单同步实测结论", "M0-0B-渲染实测结论",
            "原型断言-归属映射", "实测快照/i8-20260916")
    print(f"\n{'=' * 78}\n E · 同批改活指针（索引不许指着不存在的件）\n{'=' * 78}")
    if not apply:
        print("  ⏱ 干跑（加 --apply 落盘）")
        return

    def ops_readme(ls: list[str]) -> list[str]:
        # ⚠️ **幂等**：第二跑若再插一行 ⇒ 汇总行会重复（踩过一次）⇒ 先看有没有。
        if any("已归档 · 2026-10-05 `TAIL-235`" in ln for ln in ls):
            ls = [ln for ln in ls if "已归档 · 2026-10-05 `TAIL-235`" not in ln]
        out = [ln for ln in ls if not (ln.startswith("| `") and any(g in ln for g in gone))]
        for i, ln in enumerate(out):
            if ln.startswith("| `模板法导出-实测结论.md`"):
                out.insert(i + 1, "| **—（已归档 · 2026-10-05 `TAIL-235`）** | 原型断言归属映射"
                                  "（治理侧 · 无判据）· i8 名单同步原始返回（`实测快照/` 两份 json）"
                                  "· 渲染能否在会话 0 内跑 · 宿主 hooks 能力（含**负结果**：本 IDE 不跑 hooks）"
                                  " —— **正文已移出仓外** `D:\\dev\\.归档-mtrl\\ops\\`（原文可 `git show` 取回）"
                                  "| ⛔ **别再新增实测结论到这个落点** | 同左（脚本已随件归档）| "
                                  "① 换机 / 升 Playwright / 改打印链路 ② 名单抓不到或条数明显变 "
                                  "③ **原型 `_smoke.js` 一改就过期** ④ 换 IDE / 升宿主 | ⛔ 无判据（随件归档）|")
                break
        return out

    def ops_readme_text(ls: list[str]) -> list[str]:
        return [ln.replace("⭐ **结论与负结果全文** ⇒ **`ops/宿主hooks-实测结论.md`**",
                           "⭐ **结论与负结果全文** ⇒ **已归档**（2026-10-05 `TAIL-235`；"
                           "仓外 `D:\\dev\\.归档-mtrl\\ops\\`，原文可 `git show` 取回）")
                for ln in ls]

    def thr(ls: list[str]) -> list[str]:
        return [ln.replace("设计-文档审计-20260929.md", "〔已归档〕设计-文档审计-20260929.md")
                 .replace("设计-文档审计-20261002.md", "〔已归档〕设计-文档审计-20261002.md")
                for ln in ls]

    def asset(ls: list[str]) -> list[str]:
        return [ln.replace("原型断言-归属映射.md", "〔已归档〕原型断言-归属映射.md")
                for ln in ls]

    def root_readme(ls: list[str]) -> list[str]:
        return [ln.replace(" · 原型断言-归属映射.md", "") for ln in ls]

    _rewrite("ops/README.md", lambda ls: ops_readme_text(ops_readme(ls)))
    _rewrite("ops/阈值表.md", thr)
    _rewrite("ops/素材包-索引.md", asset)
    _rewrite("README.md", root_readme)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真落盘（缺省＝干跑）")
    ap.add_argument("--only", default="ABC", help="只跑某几个动作")
    args = ap.parse_args()
    if args.apply:
        OUT.mkdir(parents=True, exist_ok=True)
        print(f"仓外归档根 = {OUT}")
    for ch in args.only:
        {"A": do_a, "B": do_b, "C": do_c, "D": do_d, "E": do_e}[ch](args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
