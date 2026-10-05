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


def do_d(apply: bool) -> None:
    """甲2 + 丙（用户 2026-10-05 点头：激进档 ＋ 全清 6 件）—— 零机器引用的设计件 ＋ ops 实测类。

    ⚠️ **只搬「机器引用 0」的**：`10-designs` 里另有 **10** 件被测试/代码钉着（分层门禁/识别样本/…）⇒ 碰了 pytest 会红。
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
    MARK = "〔已归档〕"
    NOTE = "（⭐ 已归档 · 2026-10-05 `TAIL-235`）"
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

    def _dedup(ln: str) -> str:
        """去掉重复的 `〔已归档〕` 前缀 —— ⚠️ 本函数头一次跑就留下了 `〔已归档〕〔已归档〕`
        （`ops_readme` 有"先删再插"守卫、`thr`/`asset` 原来没有 ⇒ 重跑即脏）。"""
        while MARK + MARK in ln:
            ln = ln.replace(MARK + MARK, MARK)
        return ln

    def _mark(ls: list[str], *stems: str) -> list[str]:
        """把 `stems` 指向的件标成「已归档」。

        ⛔⛔ **为什么替换时要去掉目录前缀**（`/code-review` 抓到的真问题）：`audit_common._PATH_RE`
        首字符限 `[A-Za-z0-9_]` ⇒ `` `work/10-designs/X.md` ``（首字符 `w`）**会被 `T3` 当成仓内路径**去查、
        查不到就判红；而给它加 `〔已归档〕` 前缀又**把整条洗成不匹配** ⇒ **制造假绿**（`ops/` 本来在
        `TOP_DIRS` 内，那个保护是真实存在的）。⇒ 改成**只留中文文件名**（首字符非 ASCII ⇒ `T3` 天然照不到）
        ＋ 括注归档事实；`claim_audit` 的 `C2` 认 `` `…md` `` ⇒ 出处仍然可核。
        ⚠️ 幂等靠**整段（含目录前缀）匹配** —— 已改过的行不再含 `work/10-designs/…` ⇒ 第二次跑是 no-op。
        """
        out = []
        for ln in ls:
            for s in stems:
                # ⚠️ 替换串**必须带上收尾那个反引号**（`…md`）—— 否则括注会插到反引号**外面**、
                # 原文那个收尾反引号就变成孤立的（实测踩过一次：`…md`（…）` §五之补`）。
                ln = (ln.replace(f"work/10-designs/{MARK}{s}.md`", f"{s}.md`{NOTE}")
                        .replace(f"ops/{MARK}{s}.md`", f"{s}.md`{NOTE}"))
            out.append(_dedup(ln))
        return out

    def root_readme(ls: list[str]) -> list[str]:
        return [ln.replace(" · 原型断言-归属映射.md", "") for ln in ls]

    _rewrite("ops/README.md", lambda ls: ops_readme_text(ops_readme(ls)))
    _rewrite("ops/阈值表.md", lambda ls: _mark(ls, "设计-文档审计-20260929", "设计-文档审计-20261002"))
    _rewrite("ops/素材包-索引.md", lambda ls: _mark(ls, "原型断言-归属映射"))
    _rewrite("README.md", root_readme)


#: ⚠️ 2026-10-05 已执行并过闸的动作 —— ⛔ **默认拒绝重跑**（`/code-review` 抓到的安全风险：
#:   `do_b` 会把 `plans/archive/` 连**唯一索引件**一起搬走 ⇒ `LENIENT_GLOBS`（`.codebuddy/plans/archive/归档-*.md`）
#:   空命中 ⇒ `T18` 判红「那一片从没被扫过」）。⇒ 真要重跑必须显式 `--force`。
#: ⛔ 另两个动作（A 归一 journal · C 旧版说明书）**已删除** —— 已完成且被本守卫拦住，留着只是
#:   「为过期需求留的可执行抽象」（`/code-review` 判 `Speculative Generality`）⇒ 当时的做法在 git 历史里。
DONE_ACTIONS = "B"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真落盘（缺省＝干跑）")
    ap.add_argument("--only", default="D", help="只跑某几个动作（B 需 --force）")
    ap.add_argument("--force", action="store_true",
                    help="⚠️ 显式允许重跑已落盘的动作（%s）" % DONE_ACTIONS)
    args = ap.parse_args()
    hit = [c for c in args.only if c in DONE_ACTIONS]
    if hit and not args.force:
        print(f"⛔ 动作 {'/'.join(hit)} 已于 2026-10-05 执行并过闸，**默认拒绝重跑**：")
        print("   · `do_b` 会把 `plans/archive/` 连**唯一索引件**一起搬走")
        print("     ⇒ `LENIENT_GLOBS` 空命中 ⇒ `T18` 判红（那一片从没被扫过）")
        print("   ⇒ 确认那些件还在原处、且真的要重跑，才加 `--force`。")
        return 1
    if args.apply:
        OUT.mkdir(parents=True, exist_ok=True)
        print(f"仓外归档根 = {OUT}")
    for ch in args.only:
        {"B": do_b, "D": do_d, "E": do_e}[ch](args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
