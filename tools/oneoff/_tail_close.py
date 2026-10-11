"""尾巴**销号**的机械三件事（一次性工具 · 2026-10-02 立 · 出处 = `/retro` 复盘的候选 4）。

**为什么要有它**：销号不是"改一行"，是**三处同改** —— 而人（我）在本仓已经在这上面栽过：
2026-10-02 办 `TAIL-214` 时，`doc_audit` 的 `T6` 当场判红两次（**编号重复**：销号后 §一 那行没删；
**§14.3 行首格式**被 ✅ 前缀挡掉），连带 `_run_mut` 三支红 ⇒ 白跑两轮。

**它做的**（全是机械的；**判断那部分仍是你写**）：
  ① **§一/§二/§三 删活动行** —— 先由人把事项 / 依据 / 日期追加到已销号姊妹件；
  ② **顶部两处计数按真源重算后写对** —— ⛔ 不再手抄；
  ③ **断言三件事**：姊妹件里已有该编号 · 活动区里**恰好 1 行** · 两处计数行都认得出来。
  ④ §14.3 的活动排期原行迁入同份计划的「已办排期（历史）」区；票文件标 done。

⚠️⚠️ **计数一律问真源**：本件**不自己写第二套计数算法** —— 直接调
   `tools/audit/audit_meta.py::ledger_counts()`（`T6` 与 `T4` 的计数锚点**共用**的那一份），
   输出「活跃 N · 已销号 M」。
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
CLOSED_INDEX = REPO / audit_common.CLOSED_INDEX_REL

#: 段标题（`### 一、…` 至 `### 三、…`）
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


def counts_via_source(text: str, closed_text: str) -> dict[str, int] | None:
    """问**真源**要计数 ⇒ `audit_meta.ledger_counts(text)`。

    ⭐ 2026-10-02（`/retro` 候选 1）：原先这里要"**把新文本临时落盘 ＋ monkeypatch `LEDGER_REL`**"
    （因为 `ledger_counts()` 当时只按路径读）—— 现在真源直接吃文本 ⇒ **那套动作整段删掉**
    （少一个临时件、少一处 monkeypatch ⇒ 少一类"临时件残留污染基线"的坑，本仓吃过）。
    """
    return audit_meta.ledger_counts(text, closed_text)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="尾巴销号：三处同改（先干跑 · 计数问真源）")
    ap.add_argument("--id", required=True, help="尾巴号（如 215）")
    ap.add_argument("--apply", action="store_true", help="真写盘（默认只干跑）")
    ap.add_argument("--plan", default=str(PLAN), help="计划主文档路径（默认仓内那份）")
    ap.add_argument("--closed-index", default=str(CLOSED_INDEX), help="已销号姊妹件（默认仓内那份）")
    ap.add_argument("--tickets", default=str(REPO / audit_meta.TICKET_DIR_REL), help="票仓目录（自测指隔离副本）")
    a = ap.parse_args(argv)

    n = str(a.id).lstrip("TILA-")            # 容错：允许传 `TAIL-215`
    tag = f"TAIL-{n}"
    path = pathlib.Path(a.plan).resolve()
    p_old = path.read_bytes()
    lines = p_old.decode("utf-8").splitlines(keepends=True)
    sec = sections(lines)
    archive_path = pathlib.Path(a.closed_index).resolve()
    if not archive_path.exists():
        print(f"⛔ 已销号姊妹件不存在：{archive_path} ⇒ 未写盘")
        return 1
    archive_text = archive_path.read_text(encoding="utf-8")

    # ① 断言：姊妹件里**已经有**人写好的留痕行
    done = [line for line in archive_text.splitlines()
            if ROW_RE.match(line) and ROW_RE.match(line).group(1) == tag]
    if len(done) != 1:
        print(f"⛔ 姊妹件里 `{tag}` 的留痕行 {len(done)} 条（期望 1）"
              " ⇒ 先在表尾追加「事项 / 销号依据 / 日期」（判断，本件不代笔）")
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
    c = counts_via_source(text_new, archive_text)
    if not c:
        print("⛔ 真源 `ledger_counts()` 在这份新文本上回 None（段标题形态变了？）⇒ **未写盘**")
        return 1
    print(f"② 真源重算：活跃 {c.get('活跃', 0)} · 已销号 {c.get('四', 0)}")
    text_new, n0, n15 = audit_common.write_counts(text_new, c)
    if n0 != 1 or n15 != 1:
        print(f"⛔ 计数行命中：计划概览 {n0} 处 / §15 顶部 {n15} 处（各期望 1）⇒ **未写盘**"
              "（多半是计数行被改写过，形态变了）")
        return 1
    # 写完计数后再问一次真源：**数对上了才算过**（计数行本身不参与计数 ⇒ 应不变）
    again = counts_via_source(text_new, archive_text)
    if again != c:
        print(f"⛔ 复查不一致：写计数前 {c} / 写计数后 {again} ⇒ **未写盘**")
        return 1
    print("③ 两处计数已按真源改写（计划概览 ＋ §15 顶部各 1 处）· 复查一致 ✅")

    # ④ 只搬活动排期的原行；历史区保留完整行，不重写四问。
    schedule_lines = text_new.splitlines(keepends=True)
    begin = next((i for i, l in enumerate(schedule_lines) if audit_meta.TAIL_SCHEDULE_RE.match(l.strip())), None)
    if begin is None:
        print("⛔ 找不到活动排期区 ⇒ 未写盘")
        return 1
    boundary = next((i for i in range(begin + 1, len(schedule_lines))
                     if schedule_lines[i].startswith("## ")), len(schedule_lines))
    history = next((i for i in range(begin + 1, boundary)
                    if schedule_lines[i].startswith("### ") and "已办排期（历史）" in schedule_lines[i]), None)
    if history is None:
        print("⛔ 找不到同份计划的已办排期（历史）区 ⇒ 未写盘")
        return 1
    sched = [i for i in range(begin + 1, history)
             if re.match(r"^\|\s*`?" + re.escape(tag) + r"`?(?:\s|\|)", schedule_lines[i])]
    if len(sched) != 1:
        print(f"⛔ 活动排期 {tag} 命中 {len(sched)} 行（期望 1）⇒ 未写盘")
        return 1
    end = next((i for i in range(history + 1, len(schedule_lines))
                if schedule_lines[i].startswith("## ")), len(schedule_lines))
    anchor = max(i for i in range(history + 1, end) if schedule_lines[i].startswith("|"))
    schedule_lines.insert(anchor + 1, schedule_lines[sched[0]])
    del schedule_lines[sched[0]]
    text_new = "".join(schedule_lines)
    print(f"④ {tag} 活动排期原行迁入已办排期（历史）区")

    # ⑤ ⭐ 2026-10-04（`TAIL-225` 票体系）：**票文件标 `done`** —— 状态是票体系唯一的进度信号
    #    （销了号票文件还写 `ready-for-agent` ⇒ 下一个人会再领一遍这张票）。
    tdir = pathlib.Path(a.tickets).resolve()
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
    t_text = t_old.decode("utf-8")
    hits = list(audit_meta.TICKET_STATE_RE.finditer(t_text))
    if len(hits) != 1:
        print(f"⛔ 票文件里 `**Status:**` 行命中 {len(hits)} 处（期望 1）⇒ **未写盘**"
              f"（锚点主人 = `tools/audit/audit_meta.py::TICKET_STATE_RE`"
              f"；票格式见 `ops/agents/issue-tracker.md` §二）")
        return 1
    m_st = hits[0]
    t_new = t_text[:m_st.start(1)] + "done" + t_text[m_st.end(1):]
    print(f"⑤ 票文件标 done：{tk}")

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
        path.write_bytes(p_old)     # 票文件写不动 ⇒ 主文档逐字节回滚（不留半成品）
        raise
    print(f"\n✅ 已写盘：{path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else path}"
          f" ＋ 票文件标 `done`（{tk.name}）"
          " ⇒ 接着跑 `tools/audit/doc_audit.py`（`T6` 应当不再判红）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
