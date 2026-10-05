"""**反向灵敏度**：`T26`（降档判据 —— 「结论已落地」⇒ 该降档）**真有区分力**，且**两个信号缺一即不报**。

`TAIL-236` 第 3 批（2026-10-05）立的判据：件在「**已定稿 / 已实施**」两档，且 ① 件内 `TAIL-` 票
**全部销号** ＋ ② 件内**声明的「落地位置」真存在** ⇒ 报黄「该降档（下沉 / 归档）」。

**为什么要一支专门的变异**（⛔ 不是塞进 `tools/mut/_mut_docaudit.py`）：
票面第 3 批验收 2 要的方向是 **「原本会报 ⇒ 抽掉一个信号 ⇒ 必须**不再**报」**，
而 `_mut_docaudit` 的框架只会断言"**报了**"（`red` / `needle` 两模式都要求命中）
⇒ 「必须不再报」那种断言在那边**表达不出来**（同族先例：`T22` 走 `_mut_injectsplice.py`、
`T23` 走 `_mut_livemachine.py`，都是自己的件）。

**它怎么跑**：**只碰自己创建的文件**（一件临时设计稿 ＋ 一件临时"落地位置"探针）——
⛔ **不改仓库里任何既有文件**（比 `_mut_docaudit` 的 `rename_away` 式更安全：中断也不会把真件留在坏态）。
收尾断言 = ① 临时件全清 ② 两个过程区的文件指纹（md5）逐件一致。

⚠️ **判据串必须窄到"注入的那一处"**（`_mut_docaudit` 的 `M7`/`M21` 都栽过同一个坑：
宽判据在基线里就命中 ⇒ 那支变异**永远为真**、看着是绿的）⇒ 这里用的是三元组
`("[T26]", "结论已落地", <样本件名>)` —— **同一行**里三个串同时出现才算命中。
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"

#: ⭐ **票侧口径从尺子那边 import**（目录 / 文件名形态 / 状态正则 / 词表 / **销号定义**全在那：
#:   `tools/audit/audit_meta.py`）—— ⛔ 本件**一个字面都不许另抄**（抄了就有第二套口径）。
#:   ⚠️ 为什么这里值得把尺子拖进来（`_mut_docaudit` 为一处段界**没有**这么做）：
#:   本件要**构造合法输入**（一张已销号票 ＋ 一张在办票）⇒ 用判据自己那份口径构造，才不会再分裂。
sys.path.insert(0, str(ROOT / "tools" / "audit"))
from audit_meta import TICKET_CLOSED, ticket_states      # noqa: E402

#: 样本件（**变异临时件** · 用完即删）—— 落在过程区、名字合规（`设计-` 前缀 · `T12` 认它）。
SAMPLE = ROOT / ".codebuddy" / "work" / "10-designs" / "设计-_mut降档样本-20990101.md"
#: 「落地位置」探针（**脚本自己创建** ⇒ "把落地文件挪走"那一例可以安全地"删掉它"，
#: ⛔ 不去动仓库里任何真文件）。它落在 `ops/`（`SCAN_GLOBS` 内）⇒ 内容必须**中性**：
#: 不写 `ACC-*` / 不写被撤项名 / 不写任何反引号路径（否则会惊动别的尺子，报的就不是 `T26` 了）。
LANDING_PROBE = ROOT / "ops" / "_mut_landing_probe.md"
PROBE_TEXT = "# 变异临时件（`_mut_downgrade.py` 用后即删）\n\n本件由反向灵敏度脚本临时创建，不是真文档。\n"
#: 过程区（`T26` 的扫描面 —— 口径 = `audit_work.DOWNGRADE_ZONES`；⛔ 这里只当"指纹范围"用）。
ZONES = (ROOT / ".codebuddy" / "work" / "10-designs",
         ROOT / ".codebuddy" / "work" / "30-troubleshooting")


def _num(tag: str) -> int:
    return int(tag.rsplit("-", 1)[-1])


def _pick_tickets() -> tuple[str, str]:
    """现场挑 ① 一张**已销号**票 ② 一张**未销号**票 ⇒ `(已销号, 未销号)`。

    ⭐⛔ **绝不写死票号**：写死的那一版在票一销号那天就会**自己烂掉**（正是本仓点名的
    "变异件静默失效"）—— 而它看上去还是一条绿线。⇒ 从判据那份口径现取（见文件头 import）。
    """
    st = ticket_states()
    closed = sorted((t for t, s in st.items() if s == TICKET_CLOSED), key=_num)
    opened = sorted((t for t, s in st.items() if s and s != TICKET_CLOSED), key=_num)
    return (closed[0] if closed else ""), (opened[0] if opened else "")


def _run_doc_audit() -> tuple[int, str]:
    """→ (`必须修 N`, 全量输出)。⚠️ **不看退出码** —— `doc_audit` 的 rc 还含黄档，两回事。
    ⚠️ **必须带 `-v`**：默认把黄档**按件聚合**，`T26` 那条消息在输出里**根本看不见**。"""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([str(PY), str(ROOT / "tools" / "audit" / "doc_audit.py"), "-v"],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"必须修 (\d+)", out)
    return (int(m.group(1)) if m else -1), out


def _hit_t26(out: str) -> bool:
    """**窄判据**：同一行里必须同时出现 `[T26]` ＋ `结论已落地` ＋ 样本件名（见 docstring 末段）。"""
    return any("[T26]" in ln and "结论已落地" in ln and SAMPLE.name in ln
               for ln in out.splitlines())


def _sample(state: str = "已实施", decl: bool = True, ticket: str = "") -> str:
    """样本稿 —— 四个文头词齐（免得惊动 `T15`）＋ 一个状态档 ＋（可选）落地声明行。"""
    L = [
        "# 设计-_mut降档样本（变异临时件 · 用后即删）",
        "",
        "读者：本件由 `_mut_downgrade.py` 临时创建",
        "回答：`T26`（降档判据）的区分力",
        "何时读：从不（变异注入）",
        f"状态：{state}（变异样本）· 创建/更新 2099-01-01 · 关联 `{ticket}`",
        "",
        "本件由反向灵敏度脚本临时创建，不是真文档。",
    ]
    if decl:
        L += ["", "⭐ **落地位置**：`ops/_mut_landing_probe.md`"]
    return "\n".join(L) + "\n"


def _write_sample(text: str) -> None:
    SAMPLE.write_text(text, encoding="utf-8", newline="")


def _fingerprint() -> tuple:
    """两个过程区里**每一件**的 `(相对名, md5)` —— 证明本件**没碰仓库里任何既有文件**。"""
    out = []
    for z in ZONES:
        for f in sorted(z.glob("*.md")):
            out.append((str(f.relative_to(ROOT)).replace("\\", "/"),
                        hashlib.md5(f.read_bytes()).hexdigest()))
    return tuple(out)


def main() -> int:
    # ⭐ **中断自愈**（同 `_mut_docaudit`）：本件跑一半被取消 ⇒ `finally` 不执行 ⇒
    #   临时件留在盘上 = 基线里多出 `T26`/`T15` 命中 ⇒ 本件下次**拒绝跑**（且提示语不指向真相）
    #   ⇒ 按定义"跑本件之前它们不该存在" ⇒ 先清掉。
    for p in (SAMPLE, LANDING_PROBE):
        if p.exists():
            print(f"  ⚠️ 发现上次中断的残留：{p.name} ⇒ 先清掉（跑本件之前它不该存在）")
            p.unlink()

    fp0 = _fingerprint()
    base_red, base_out = _run_doc_audit()
    print(f"  基线（未改坏）doc_audit 必须修 {base_red} · 输出 {len(base_out)} 字符")
    if _hit_t26(base_out):
        print("  ⛔ 基线的输出里**已经**有那三条判据串 ⇒ 本件判据无效，先重定靶")
        return 1

    closed_ticket, open_ticket = _pick_tickets()
    print(f"  样本输入（现取）：已销号票 = {closed_ticket or '（无）'} · 在办票 = {open_ticket or '（无）'}")
    if not closed_ticket or not open_ticket:
        print("  ⛔ 票仓里凑不齐「已销号 / 未销号」各一张 ⇒ 两条输入无法构造（先核计划 §15 台账）")
        return 1

    #: `(说明, 落地探针是否在位, 样本文本, 期望是否报)`
    cases: list[tuple[str, bool, str, bool]] = [
        ("C1 **正向**：已实施 ＋ 票已销号 ＋ 落地声明真存在 ⇒ 必须报",
         True, _sample(ticket=closed_ticket), True),
        ("C2 **反向 a**：把票换成**未销号**的那张 ⇒ 必须**不再报**",
         True, _sample(ticket=open_ticket), False),
        ("C3 **反向 b**：把**落地文件挪走**（删探针）⇒ 必须**不再报**",
         False, _sample(ticket=closed_ticket), False),
        ("C4 反向 c：状态档换成「**在研**」（不在那两档）⇒ 必须**不再报**",
         True, _sample(state="在研", ticket=closed_ticket), False),
        ("C5 反向 d：**没有落地声明行**（无从机判）⇒ 必须**不再报**",
         True, _sample(decl=False, ticket=closed_ticket), False),
    ]

    hit = 0
    red_kept = True
    try:
        for desc, probe, text, want in cases:
            try:
                if probe:
                    LANDING_PROBE.write_text(PROBE_TEXT, encoding="utf-8", newline="")
                elif LANDING_PROBE.exists():
                    LANDING_PROBE.unlink()
                _write_sample(text)
                red, out = _run_doc_audit()
            finally:
                # ⭐ 每条立刻清场：下一例要的是"干净起点"（否则 C3 删掉的探针会漏进 C4）
                SAMPLE.unlink(missing_ok=True)
                LANDING_PROBE.unlink(missing_ok=True)
            got = _hit_t26(out)
            ok = got == want
            if desc.startswith("C1") and red != base_red:
                ok = False
                red_kept = False
                print(f"  ⛔ C1 的「必须修」从 {base_red} 变成 {red} ⇒ `T26` **不是黄档**")
            tail = ("输出里出现该条（黄档）" if got else "输出里没有该条（不报）")
            print(("  ✅ " if ok else "  ⛔ 未命中 ") + desc + "  → " + tail)
            hit += bool(ok)
    finally:
        # ⭐ 收尾清场（无论中途怎么退出）—— 两种临时件都不许留在盘上
        SAMPLE.unlink(missing_ok=True)
        LANDING_PROBE.unlink(missing_ok=True)

    fp1 = _fingerprint()
    clean = not SAMPLE.exists() and not LANDING_PROBE.exists()
    same = fp0 == fp1
    print()
    print(f"  命中 {hit}/{len(cases)}")
    print(f"  临时件清场：{'✅ 无残留' if clean else '❌ 还在：' + str([p.name for p in (SAMPLE, LANDING_PROBE) if p.exists()])}"
          f" · 两个过程区指纹：{'✅ 逐件 md5 一致（本件没碰任何既有文件）' if same else '❌ 有文件被改了'}")
    if not red_kept:
        print("  ⛔ `T26` 动了「必须修」= 它跑到红档去了（口径：**黄 · 只报不动**）")
    return 0 if (hit == len(cases) and clean and same and red_kept) else 1


if __name__ == "__main__":
    sys.exit(main())
