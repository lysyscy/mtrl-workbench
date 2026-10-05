"""尾巴**销号**的机械三件事（一次性工具 · 2026-10-02 立 · 出处 = `/retro` 复盘的候选 4）。

**为什么要有它**：销号不是"改一行"，是**三处同改** —— 而人（我）在本仓已经在这上面栽过：
2026-10-02 办 `TAIL-214` 时，`doc_audit` 的 `T6` 当场判红两次（**编号重复**：销号后 §一 那行没删；
**§14.3 行首格式**被 ✅ 前缀挡掉），连带 `_run_mut` 三支红 ⇒ 白跑两轮。

**它做的**（全是机械的；**判断那部分仍是你写**）：
  ① **§一/§二/§三 删行** —— 销号 ⇒ 只留 §四 的**留痕行**（⚠️ 那一行要你**先写好**：事项 / 依据 / 日期是判断）；
  ② **顶部两处计数按真源重算后写对** —— ⛔ 不再手抄；
  ③ **断言三件事**：§四 里已有该编号的留痕行 · §一/§二/§三 里**恰好 1 行** · 两处计数行都认得出来。

⚠️⚠️ **计数一律问真源**：本件**不自己写第二套计数算法** —— 直接调
   `tools/audit/audit_meta.py::ledger_counts()`（`T6` 与 `T4` 的计数锚点**共用**的那一份）。
   实测教训（2026-10-02 · 本件第一版）：自己镜像了一遍段解析，算出的"已销号"= **214**，
   而真源是 **216** ⇒ 差 2。⚠️ 若各写一份，`doc_audit` 的 `T6` 会立刻报「计数与实际不符」——
   也就是说**这个错误一定会被抓住**，但更好的做法是**从一开始只有一份**。

用法（**先干跑**）：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail_close.py --id 215
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail_close.py --id 215 --apply
    （自测用）… --plan .codebuddy\\work\\00-scratch\\_plan_copy.md   # ⛔ 只在副本上试，别指向真件之外的东西
⚠️ **不达标的整批不写盘**（同 `tools/oneoff/` 里其它一次性件的口径）。
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "audit"))
import audit_common  # noqa: E402  ← ⭐ 计数行**形态**的唯一出处（`write_counts`）
import audit_meta  # noqa: E402  ← ⭐ 计数的**真源**（`ledger_counts()`）

PLAN = REPO / ".codebuddy" / "plans" / "开发计划-主文档.md"

#: 段标题（`### 一、…` / `### 四、已销号（…）`）
SEC_RE = re.compile(r"^#{2,3}\s*([一二三四])、")
#: 尾巴行（**编号只认第一格** —— 与 `audit_meta.check_tail_ledger` 同口径）
ROW_RE = re.compile(r"^\|\s*`?(TAIL-\d+)`?\s*\|")
#: ⚠️ 2026-10-02（`/retro` 候选 1）：顶部两处计数行的**正则已移进 `audit_common.py`**
#:    （`COUNT_MIN_RE` / `COUNT_FULL_RE` ＋ `write_counts()`）—— ⛔ 别在这里再写一遍。


def sections(lines: list[str]) -> dict[str, list[int]]:
    """段号 ⇒ 该段正文的行号（0 基；到下一个 `### [一二三四]、` 标题为止）—— **只用来定位行**。"""
    marks = [(i, SEC_RE.match(l).group(1)) for i, l in enumerate(lines) if SEC_RE.match(l)]
    out: dict[str, list[int]] = {}
    for k, (start, name) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
        out.setdefault(name, []).extend(range(start + 1, end))
    return out


def counts_via_source(text: str) -> dict[str, int] | None:
    """问**真源**要计数 ⇒ `audit_meta.ledger_counts(text)`。

    ⭐ 2026-10-02（`/retro` 候选 1）：原先这里要"**把新文本临时落盘 ＋ monkeypatch `LEDGER_REL`**"
    （因为 `ledger_counts()` 当时只按路径读）—— 现在真源直接吃文本 ⇒ **那套动作整段删掉**
    （少一个临时件、少一处 monkeypatch ⇒ 少一类"临时件残留污染基线"的坑，本仓吃过）。
    """
    return audit_meta.ledger_counts(text)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="尾巴销号：三处同改（先干跑 · 计数问真源）")
    ap.add_argument("--id", required=True, help="尾巴号（如 215）")
    ap.add_argument("--apply", action="store_true", help="真写盘（默认只干跑）")
    ap.add_argument("--plan", default=str(PLAN), help="计划主文档路径（默认仓内那份）")
    a = ap.parse_args(argv)

    n = str(a.id).lstrip("TILA-")            # 容错：允许传 `TAIL-215`
    tag = f"TAIL-{n}"
    path = pathlib.Path(a.plan).resolve()
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    sec = sections(lines)

    # ① 断言：§四 里**已经有**留痕行（判断那部分要人先写好）
    done = [i for i in sec.get("四", []) if ROW_RE.match(lines[i]) and ROW_RE.match(lines[i]).group(1) == tag]
    if len(done) != 1:
        print(f"⛔ §四（已销号）里 `{tag}` 的留痕行 {len(done)} 条（期望 1）"
              " ⇒ 先把「事项 / 销号依据 / 日期」那一行写好（那是判断，本件不代笔）")
        return 1

    # ② 找 live 行（§一/§二/§三）⇒ 删掉
    live = [(s, i) for s in "一二三" for i in sec.get(s, [])
            if ROW_RE.match(lines[i]) and ROW_RE.match(lines[i]).group(1) == tag]
    if len(live) != 1:
        print(f"⛔ §一/§二/§三 里 `{tag}` 的行 {len(live)} 条（期望 1）"
              f" ⇒ 要么没登记，要么已被销号过一次；清单 = {[f'§{s} 第 {i + 1} 行' for s, i in live]}")
        return 1
    sec_name, live_i = live[0]
    print(f"① 删 §{sec_name} 第 {live_i + 1} 行：{lines[live_i].strip()[:96]}…")

    # ③ 计数：**问真源**（⛔ 本件不镜像算法）
    text_new = "".join(l for k, l in enumerate(lines) if k != live_i)
    c = counts_via_source(text_new)
    if not c:
        print("⛔ 真源 `ledger_counts()` 在这份新文本上回 None（段标题形态变了？）⇒ **未写盘**")
        return 1
    print(f"② 真源重算：A {c.get('一', 0)} · B {c.get('二', 0)} · C {c.get('三', 0)}"
          f" · 已销号 {c.get('四', 0)}")
    text_new, n0, n15 = audit_common.write_counts(text_new, c)
    if n0 != 1 or n15 != 1:
        print(f"⛔ 计数行命中：§0.2 {n0} 处 / §15 顶部 {n15} 处（各期望 1）⇒ **未写盘**"
              "（多半是计数行被改写过，形态变了）")
        return 1
    # 写完计数后再问一次真源：**数对上了才算过**（计数行本身不参与计数 ⇒ 应不变）
    again = counts_via_source(text_new)
    if again != c:
        print(f"⛔ 复查不一致：写计数前 {c} / 写计数后 {again} ⇒ **未写盘**")
        return 1
    print("③ 两处计数已按真源改写（§0.2 ＋ §15 顶部各 1 处）· 复查一致 ✅")

    # ④ 排期表：只提醒，不改（销号后 T6 不再要求它在 §14.3，但留着那行是留痕）
    sched = [i for i, l in enumerate(text_new.splitlines(keepends=True))
             if l.lstrip().startswith("|") and tag in l.split("|")[1]]
    print(f"④ §14.3 排期表里该编号的行：{len(sched)} 处（{'留痕保留' if sched else '⚠️ 没有那行'}"
          " —— 本件不动它）")

    # ⑤ ⭐ 2026-10-04（`TAIL-225` 票体系）：**票文件标 `done`** —— 状态是票体系唯一的进度信号
    #    （销了号票文件还写 `ready-for-agent` ⇒ 下一个人会再领一遍这张票）。
    tdir = REPO / ".codebuddy" / "work" / "50-tickets"
    tk = next((p for p in sorted(tdir.glob(f"{tag}-*.md"))), None) if tdir.is_dir() else None
    if tk is None:
        print(f"⛔ 找不到 {tag} 的票文件（`{tdir.name}/`）⇒ **未写盘**"
              "（票体系下每张在办票都该有票文件；先去 `_tail_open.py` 建它）")
        return 1
    t_old = tk.read_bytes()
    #  ⑤ 的锚点 = **`audit_meta.TICKET_STATE_RE`**（票面 `**Status:** <受控词>` 的**唯一机器主人** ——
    #    `T6` 判票状态也用它）。⛔ 2026-10-05（`TAIL-231` 销号时踩到）：本件原先**自己写了一份正则**、
    #    且只认中文「状态：」—— 而票面格式的真正主人 `tools/oneoff/_tail_open.py` 写的是
    #    `**Status:** <受控词>` ⇒ 命中 0 处 ⇒ **任何票都无法用它销号**（`TAIL-225` 那次是手改票文件绕过去的）。
    #    修法 = 删掉本地那份、改为问主人（与本件第 44–45 行「计数口径不写第二遍」同一条纪律）。
    t_text = tk.read_text(encoding="utf-8")
    hits = list(audit_meta.TICKET_STATE_RE.finditer(t_text))
    if len(hits) != 1:
        print(f"⛔ 票文件里 `**Status:**` 行命中 {len(hits)} 处（期望 1）⇒ **未写盘**"
              f"（锚点主人 = `tools/audit/audit_meta.py::TICKET_STATE_RE`"
              f"；票格式见 `ops/agents/issue-tracker.md` §二）")
        return 1
    m_st = hits[0]
    t_new = t_text[:m_st.start(1)] + "done" + t_text[m_st.end(1):]
    print(f"⑤ 票文件标 done：{tk.relative_to(REPO).as_posix()}")

    if not a.apply:
        print("\n（干跑 —— 要真写盘加 --apply）")
        return 0
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False,
                                     dir=path.parent, prefix="~tailclose-", suffix=".tmp") as fh:
        fh.write(text_new)
        tmp_out = pathlib.Path(fh.name)
    tmp_out.replace(path)                       # 原子替换（同目录 ⇒ 不会跨盘）
    try:
        tk.write_text(t_new, encoding="utf-8", newline="")
    except OSError:
        path.write_bytes("".join(lines).encode("utf-8"))     # 票文件写不动 ⇒ 主文档回滚（不留半成品）
        raise
    print(f"\n✅ 已写盘：{path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else path}"
          f" ＋ 票文件标 `done`（{tk.name}）"
          " ⇒ 接着跑 `tools/audit/doc_audit.py`（`T6` 应当不再判红）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
