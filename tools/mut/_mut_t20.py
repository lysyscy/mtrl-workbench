#!/usr/bin/env python
"""`T20` 反向灵敏度 —— 证明「保留期与容量」这条判据**真的有牙**。

守什么（`audit_work.check_retention`）：
- `README.md` 写着 `.codebuddy/backups/`「留 5 份 · 月度清」，而 2026-09-22 整改设计给的验收判据
  就是「目录计数 ≤5（可数）」—— 却**从没被机器守过** ⇒ 43 个条目静默堆着（含 09-18 的旧快照）。
- 2026-09-29（`TAIL-194`）加：**`tools/oneoff/` 件数 / 容量**。
- ⭐⭐ 2026-10-02（`TAIL-217` · 用户选「②」）加**两条**：
  · **交付面改前快照**（`交付面-*` / `原型-备份-*` / `_smoke.js-备份-*` / `*.bak`）的**条目数 / 容量** ——
    这一类此前**一个上限都没有**（旧口径只说「另一用途 ⇒ 不计入 5 份上限」）⇒ 涨到多少都没人看见；
  · **显式归档子目录**（`_归档-*` / `_旧快照归档-*`）的**件数 / 容量** —— 此前**只打印、从不判**
    ⇒ 把东西「全塞归档」就能把上一条糊弄成假绿。
- ⚠️ 2026-10-01（`TAIL-204` 第 7 步）**撤掉**原先那一处「`.workbuddy/scratch/` 活区规模」⇒ 本件跟着**少一个变异** ——
  因为它是**僵尸判据**：那个目录搬家后就不存在了，尺子**每次都在空集上跑**；⚠️ 而本件当初往那个**死路径**写
  51 MB 稀疏文件 ⇒ 一跑就**在仓里复活旧根**（且因为两边用同一个死路径，它还"自证通过"）。
  ⭐ 教训：**撤判据时，它的变异件必须同批撤** —— 否则留下一个"打不着的靶"，比没有更坏。

变异（都在**新增临时件**上做，跑完**必清**；⛔ 不删任何既有备份）：
  ① 往 `.codebuddy/backups/` 放 `BACKUP_KEEP + 1` 个**假快照目录** ⇒ 「顶层手工快照」那条必须报出来；
  ② 往 `tools/oneoff/` 放一个 6 MB 稀疏文件（> 容量线 5 MB）⇒ 「oneoff」那条必须报出来；
  ③ ⭐ 往 `.codebuddy/backups/` 放 `FACE_KEEP + 1` 个假 `原型-备份-*` ⇒ 「交付面改前快照」那条必须报出来；
  ④ ⭐ 往 `.codebuddy/backups/_归档-t20probe/` 放 `ARCHIVE_KEEP + 1` 件 ⇒ 「归档子目录」那条必须报出来。

⭐⭐ **判法（2026-09-29 订正 —— 这里踩过一次）**：原来只比「**命中条数**是否上升」，而这在该项
**基线本就超线**时**必然失效** —— 那几处超线都只报**一行**，`7 → 8` 个条目仍是 **1 行** ⇒
变异"没抓到"是**假红**（实测：当时 `backups/` 顶层 7 > 5，①靶当场报红）。
⇒ 现改成：**按 marker 取出那一行 marker 之后的第一个数字**（条目数 / 件数），比**这个数字**是否变大
（`无命中 → 有命中` 也算变大）。⚠️ 用的仍是 `check_retention()` 的**真逻辑**（⛔ 不另写一套判定），
只是**读它报出来的数**。

⚠️⚠️ **2026-10-02（`TAIL-217`）marker 换靶 —— 这一处是"判据自己瞎了"的同族**：
  原先按 `rel`（`.codebuddy/backups/`）匹配；而本轮给 `T20` 新加的**两条**判定的 `rel` **也含**
  `.codebuddy/backups/` ⇒ 按 rel 会**读到别人那一行**（靶看着是绿的、其实瞄错了）。
  ⇒ 改成按**报告行里唯一的那截中文**匹配（`顶层 ` / `tools/oneoff/ ` / `交付面改前快照 ` / `归档子目录 `）。
  ⭐ 同族教训 = `T17` 那次「锚用**裸词** ⇒ 静默空扫」（见 `docs` 里那条 `M18`）。

⚠️ 上限一律**从真源 `audit_work` 取常量**（⛔ 本件不抄数字 —— 抄了就会漂）。
"""
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
R = pathlib.Path(r"D:\dev\mtrl-workbench")
sys.path.insert(0, str(R / "tools" / "audit"))
import audit_work as AW                                   # noqa: E402  ← ⭐ 上限的真源

BK = R / ".codebuddy" / "backups"

#: ⚠️ 2026-10-01（`TAIL-204` 第 7 步）：①的靶**加厚**成 `BACKUP_KEEP + 1` 个 —— 原来只放 2 个，
#:   只在"基线本来就贴着上限"时才会越线 ⇒ 基线收敛后**静默失效**（当场报 `None → None`）。
#:   同族教训 = `M7` 换靶那次：「靶必须跟着现实走，否则留下的是一条**打不着的靶**」。
FAKE_SNAPS = [BK / f"_t20_probe_tmp{i}" for i in range(1, AW.BACKUP_KEEP + 2)]
#: ⚠️ 2026-10-01（`TAIL-204` 第 7 步）：原 `BIG`（`.workbuddy/scratch/…` 那个 51 MB 稀疏文件）**已撤** —— 见文件头。
BIG3 = R / "tools" / "oneoff" / "_t20_probe_tmp.bin"
#: ⭐ 2026-10-02（`TAIL-217`）③ 的靶：`FACE_KEEP + 1` 个假「原型改前备份」⇒ **与基线无关、必越线**。
FAKE_FACE = [BK / f"原型-备份-t20probe{i}.html" for i in range(1, AW.FACE_KEEP + 2)]
#: ⭐ 同上 ④ 的靶：造一个 `_归档-t20probe/`（⚠️ 名字必须以 `_归档-` 打头，否则会被算成"顶层手工快照"）。
FAKE_ARCH_DIR = BK / "_归档-t20probe"
FAKE_ARCH = [FAKE_ARCH_DIR / f"x{i}.md" for i in range(1, AW.ARCHIVE_KEEP + 2)]

#: 四条变异各自"该看哪一行"的唯一 marker（见文件头那句"marker 换靶"）。
M_TOP, M_ONEOFF, M_FACE, M_ARCH = "顶层 ", "tools/oneoff/ ", "交付面改前快照 ", "归档子目录 "


def report() -> str:
    """跑 `check_retention()`（子进程 · 走真逻辑）⇒ 它的完整输出文本。

    ⚠️ 必须带 `-X utf8`：否则 Windows 控制台编码会把中文输出搞崩 ⇒ 子进程 rc≠0、判据读不到
       （本仓「跑审计件的正确起手」那一条）。
    ⚠️ 走**子进程**（不是 import）⇒ 拿到的就是"另一次真跑"的结果，与本进程状态无关。
    """
    r = subprocess.run(
        [str(R / "backend" / ".venv" / "Scripts" / "python.exe"), "-X", "utf8", "-c",
         "import sys; sys.path.insert(0, r'tools/audit');"
         "from audit_work import check_retention as c;"
         "h = c();"
         "print('命中', len(h));"
         "[print('  -', x['code'], x['rel'], x['what'][:60]) for x in h]"],
        cwd=R, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    if "命中" not in out:
        print(out[-400:])
    return out


def n_for(text: str, marker: str) -> int | None:
    """报告里含 `marker` 的那一行、`marker` **之后**的第一个数字；无命中 ⇒ `None`。"""
    for line in text.splitlines():
        if line.strip().startswith("-") and marker in line:
            m = re.search(r"(\d+)", line.split(marker, 1)[1])
            if m:
                return int(m.group(1))
    return None


def grew(before: str, after: str, marker: str) -> bool:
    a, b = n_for(before, marker), n_for(after, marker)
    if b is None:
        return False
    return a is None or b > a


def cleanup() -> None:
    """**必清**（`finally` 里调）—— ⛔ 不给盘上留一个假件（同族风险：靶件留坏态会污染基线）。"""
    for p in FAKE_FACE:
        p.unlink(missing_ok=True)
    for p in FAKE_ARCH:
        p.unlink(missing_ok=True)
    shutil.rmtree(FAKE_ARCH_DIR, ignore_errors=True)
    for d in FAKE_SNAPS:
        (d / "x.md").unlink(missing_ok=True)
        try:
            d.rmdir()
        except OSError:
            pass
    BIG3.unlink(missing_ok=True)


def main() -> int:
    fail: list[str] = []
    print("基线…")
    base = report()
    print(base)
    try:
        print(f"变异①：`backups/` 里放 **{len(FAKE_SNAPS)} 个**假快照目录（= 上限 {AW.BACKUP_KEEP} + 1）"
              "⇒ 「顶层手工快照」那条**必须**报出来…")
        for d in FAKE_SNAPS:
            d.mkdir(parents=True, exist_ok=True)
            (d / "x.md").write_text("tmp", encoding="utf-8")
        r1 = report()
        if not grew(base, r1, M_TOP):
            fail.append(f"① 顶层条目数没变大（{n_for(base, M_TOP)} → {n_for(r1, M_TOP)}）"
                        " —— ⚠️ 若基线手工快照数本来就高，说明**靶没加够**，不是判据坏了")
        for d in FAKE_SNAPS:
            (d / "x.md").unlink(missing_ok=True)
            d.rmdir()

        print("变异②：`tools/oneoff/` 里放一个 6 MB 稀疏文件 ⇒ 该处规模应变大…")
        with BIG3.open("wb") as f:
            f.truncate(6 * 1024 * 1024)
        r3 = report()
        if not grew(base, r3, M_ONEOFF):
            fail.append(f"② 「tools/oneoff/」规模没变大"
                        f"（{n_for(base, M_ONEOFF)} → {n_for(r3, M_ONEOFF)}）")
        BIG3.unlink(missing_ok=True)

        print(f"变异③：`backups/` 里放 **{len(FAKE_FACE)} 个**假 `原型-备份-*`（= 上限 {AW.FACE_KEEP} + 1）"
              "⇒ 「交付面改前快照」那条**必须**报出来…")
        for p in FAKE_FACE:
            p.write_text("tmp", encoding="utf-8")
        r4 = report()
        if not grew(base, r4, M_FACE):
            fail.append(f"③ 「交付面改前快照」那条没报出来"
                        f"（{n_for(base, M_FACE)} → {n_for(r4, M_FACE)}）—— 靶加了 {len(FAKE_FACE)} 个，本该必越线")
        for p in FAKE_FACE:
            p.unlink(missing_ok=True)

        print(f"变异④：`backups/_归档-t20probe/` 里放 **{len(FAKE_ARCH)} 件**（= 上限 {AW.ARCHIVE_KEEP} + 1）"
              "⇒ 「归档子目录」那条**必须**报出来…")
        FAKE_ARCH_DIR.mkdir(parents=True, exist_ok=True)
        for p in FAKE_ARCH:
            p.write_text("tmp", encoding="utf-8")
        r5 = report()
        if not grew(base, r5, M_ARCH):
            fail.append(f"④ 「归档子目录」那条没报出来"
                        f"（{n_for(base, M_ARCH)} → {n_for(r5, M_ARCH)}）—— 靶加了 {len(FAKE_ARCH)} 件，本该必越线")
    finally:
        cleanup()

    print("复检…")
    after = report()
    for m in (M_TOP, M_ONEOFF, M_FACE, M_ARCH):
        if n_for(after, m) != n_for(base, m):
            fail.append(f"清场不完（`{m}` 复检 {n_for(after, m)} vs 基线 {n_for(base, m)}）")

    if fail:
        print("❌ " + "；".join(fail))
        return 1
    print(f"✅ 有区分力：四条变异都让报告里的数变大（顶层 {n_for(base, M_TOP)}→{n_for(r1, M_TOP)} · oneoff "
          f"{n_for(base, M_ONEOFF)}→{n_for(r3, M_ONEOFF)} · 交付面改前快照 "
          f"{n_for(base, M_FACE)}→{n_for(r4, M_FACE)} · 归档子目录 {n_for(base, M_ARCH)}→{n_for(r5, M_ARCH)}）"
          "、临时件已清（⚠️ 原来第三处「scratch 活区规模」2026-10-01 已撤 —— 那是**僵尸判据**，见文件头）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
