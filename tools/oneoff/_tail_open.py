"""尾巴**立台账**的机械三件事（一次性工具 · 2026-10-02 立 · 出处 = `/retro` 候选 1）。

**为什么要有它**：**销号**有 `tools/oneoff/_tail_close.py`（三处同改 · 干跑优先 · 计数问真源），
而**立台账一个都没有** ⇒ 2026-10-02 我一次立 4 条时**只写了 §15、漏了 §14.3 排期表** ⇒
`doc_audit` 的 `T6` 当场报 **3 条必须修**，还连带 `_run_muts` 里两支变异"**基线不干净 ⇒ 拒跑**"
（我又多花一轮去定位真因）。⇒ 同款收口：**立台账也是三处同改** =
  ① `§15 §一` 插行 ② **`§14.3 逐条排期` 插行** ③ 顶部**两处计数**按真源重写。

**它做的**（全是机械的；**判断那部分仍是你写** —— 事项 / 来源 / 四问 / 落点）：
  ① 插 `§15 §一` 一行（**列序现读表头** ⇒ ⛔ 本件不写死列序）
  ② 插 `§14.3` 一行
  ③ 两处计数按 `audit_meta.ledger_counts()`（**真源**）重算 ⇒ `audit_common.write_counts()` 只管写法
  ④ ⭐ **收尾断言**：真写盘后再跑一次 `doc_audit`，它必须「必须修 0」（＝ `T6` 认得这行新条目）；
     ⚠️ **不达标 ⇒ 逐字节回滚**（本仓口径：不达标的整批不留痕）。

⚠️ **编号顺延**（`_tail_close.py` 不释放编号 ⇒ 别重用）；本件会**拒绝**已存在的编号。
⚠️ 干跑**不写盘**；真写盘才做 ④。

用法（**先干跑**）：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail_open.py --id 223 \
        --what "🆕 一句话（事项）" --src "来源（谁在什么场合点的）" \
        --not-doing "不做会怎样" --where "落点（哪一份 / 哪一件）" --when "随时" \
        --why "四问理由（①②③④ 各一句）" --pre "前置 / 触发" --apply
    （自测）… --plan .codebuddy\\work\\00-scratch\\_plan_copy.md   # ⛔ 只在副本上试
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "audit"))
import audit_common  # noqa: E402  ← ⭐ 计数行**形态**的唯一出处（`write_counts`）
import audit_meta  # noqa: E402  ← ⭐ 计数的**真源**（`ledger_counts`）

PLAN = REPO / ".codebuddy" / "plans" / "开发计划-主文档.md"
PY = REPO / "backend" / ".venv" / "Scripts" / "python.exe"

ROW_RE = re.compile(r"^\|\s*`?(TAIL-\d+)`?\s*\|")
SEC1_RE = re.compile(r"^#{2,3}\s*一、")
SCHED_RE = re.compile(r"^#{2,3}\s*[\d.]*\s*逐条排期")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _table(lines: list[str], start: int, stop_prefix: str = "## ") -> tuple[int, list[int]]:
    """从 `start` 往下找**第一张表** ⇒ `(表头行号, 数据行号列表)`（分隔行与表头不计入数据）。"""
    hdr = next(k for k in range(start, len(lines))
               if lines[k].lstrip().startswith("|"))
    rows: list[int] = []
    for k in range(hdr + 1, len(lines)):
        s = lines[k].strip()
        if s.startswith(stop_prefix) or (s and not s.startswith("|")):
            break
        if not s:
            continue
        c = _cells(s)
        if not c or set(c[0]) <= {"-", ":"}:        # 分隔行
            continue
        rows.append(k)
    return hdr, rows


def build_rows(args, hdr1: list[str], hdr_s: list[str]) -> tuple[str, str]:
    """按**现读的表头**拼两行（⛔ 不写死列序）。"""
    tag = f"TAIL-{args.id}"
    val = {
        "事项": f"{args.what}", "来源": args.src, "不做会怎样": args.not_doing,
        "落点": args.where, "阶段": args.when, "时机": args.when, "状态": "待做",
    }
    cells = [f"`{tag}`"]
    for col in hdr1[1:]:
        key = next((k for k in val if k in col), None)
        if key is None:
            raise SystemExit(f"⛔ §一 表头有一栏本件不认识：{col!r} —— 先补本件的映射表")
        cells.append(val[key])
    row1 = "| " + " | ".join(cells) + " |"

    cells_s = [f"`{tag}` {args.what}"]
    for col in hdr_s[1:]:
        if "时机" in col:
            cells_s.append(f"⏳ **{args.when}**")
        elif "理由" in col or "四问" in col:
            cells_s.append(f"**四问**：{args.why}")
        elif "前置" in col or "触发" in col:
            cells_s.append(f"触发 = {args.pre}；落点 = 见 §15 §一 本行")
        else:
            raise SystemExit(f"⛔ §14.3 表头有一栏本件不认识：{col!r}")
    row_s = "| " + " | ".join(cells_s) + " |"
    return row1, row_s


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="尾巴立台账：三处同改（先干跑 · 计数问真源）")
    ap.add_argument("--id", required=True)
    for f in ("what", "src", "not-doing", "where", "when", "why", "pre"):
        ap.add_argument(f"--{f}", required=True)
    ap.add_argument("--apply", action="store_true", help="真写盘（默认只干跑）")
    ap.add_argument("--plan", default=str(PLAN))
    a = ap.parse_args(argv)
    a.id = str(a.id).lstrip("TILA-")
    path = pathlib.Path(a.plan).resolve()

    orig = path.read_bytes()
    lines = orig.decode("utf-8").splitlines(keepends=True)

    # ① 编号不许已存在（顺延；⛔ 不重用）
    dup = [k + 1 for k, l in enumerate(lines) if ROW_RE.match(l) and ROW_RE.match(l).group(1) == f"TAIL-{a.id}"]
    if dup:
        print(f"⛔ 编号 TAIL-{a.id} 已在第 {dup} 行 ⇒ 顺延取新号（`_tail_close.py` 不释放编号）")
        return 1

    i1 = next((k for k, l in enumerate(lines) if SEC1_RE.match(l)), None)
    isd = next((k for k, l in enumerate(lines) if SCHED_RE.match(l)), None)
    if i1 is None or isd is None:
        print("⛔ 找不到 §15 §一 或 §14.3（段标题形态变了？）⇒ 未写盘")
        return 1
    h1, r1 = _table(lines, i1 + 1)
    hs, rs = _table(lines, isd + 1)
    if not r1 or not rs:
        print("⛔ §一 或 §14.3 里找不到数据行 ⇒ 未写盘")
        return 1
    row1, row_s = build_rows(a, _cells(lines[h1]), _cells(lines[hs]))
    print(f"① §15 §一 第 {r1[-1] + 1} 行之后插：{row1[:88]}…")
    print(f"② §14.3 第 {rs[-1] + 1} 行之后插：{row_s[:88]}…")

    new = lines[:r1[-1] + 1] + [row1 + "\n"] + lines[r1[-1] + 1:]
    # ⚠️ §14.3 的行号在插入后**整体下移 1** ⇒ 重新定位（⛔ 别拿旧行号硬算）
    isd = next((k for k, l in enumerate(new) if SCHED_RE.match(l)), None)
    _hs, rs2 = _table(new, isd + 1)
    new = new[:rs2[-1] + 1] + [row_s + "\n"] + new[rs2[-1] + 1:]
    text_new = "".join(new)

    # ③ 计数：**问真源**（⛔ 本件不镜像算法；形态由 `audit_common` 管）
    c = audit_meta.ledger_counts(text_new)
    if not c:
        print("⛔ 真源 `ledger_counts()` 在这份新文本上回 None（段标题形态变了？）⇒ **未写盘**")
        return 1
    text_new, n0, n15 = audit_common.write_counts(text_new, c)
    print(f"③ 真源重算：A {c.get('一', 0)} · B {c.get('二', 0)} · C {c.get('三', 0)} · 已销号 {c.get('四', 0)}"
          f" ⇒ 计数行命中 §0.2 {n0} 处 / §15 顶部 {n15} 处（各期望 1）")
    if n0 != 1 or n15 != 1:
        print("⛔ 计数行命中数不对 ⇒ **未写盘**（多半是计数行被改写过，形态变了）")
        return 1

    if not a.apply:
        print("\n（干跑 —— 要真写盘加 --apply；⚠️ 真写盘会再做一次 `doc_audit` 收尾断言）")
        return 0

    path.write_bytes(text_new.encode("utf-8"))
    # ④ ⭐ 收尾断言：`T6` 必须认得这行新条目（＝ 三处都写到了）；不达标 ⇒ **逐字节回滚**
    r = subprocess.run([str(PY), "-X", "utf8", str(REPO / "tools" / "audit" / "doc_audit.py")],
                       cwd=str(REPO), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    if "必须修 0" not in out:
        path.write_bytes(orig)
        print("⛔ 收尾断言不过（`doc_audit` 不是「必须修 0」）⇒ **已逐字节回滚**；它的输出尾部：")
        print("\n".join(out.splitlines()[-12:]))
        return 1
    print(f"✅ 已写盘 ＋ 收尾断言过（`doc_audit` 必须修 0）：{path.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
