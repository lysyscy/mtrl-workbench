#!/usr/bin/env python
"""**降档动作**（可逆搬运 ＋ 仓内索引留行）—— `TAIL-236` 第 4 批 · 2026-10-06 立。

把**一件设计件**从 `.codebuddy/work/10-designs/` 搬到**仓外**（落点 = `audit_common.OUTSIDE_ROOTS[0]`
下的 `work-10-designs/` —— ⚠️ **本件一个字都不写死那个根**），并在**仓内留痕索引**里追加一行；
那一行写着**仓外绝对路径** ⇒ `T3` 的「仓外白名单**真核存在**」会真的去核那份在不在。
**可逆** = 仓外留原文 ＋ 仓内留指针 ＋ git 历史里还有一份。
⛔ **本命令没有删除分支** ——「真删必须用户点头」那条规矩的实现方式就是**这里根本没有删除**。

跑法（**默认干跑**；`--apply` 才真搬 —— 同 `_tail_open.py` 的「干跑优先」）：

    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_doc_downgrade.py <件名>
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_doc_downgrade.py <件名> --apply
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_doc_downgrade.py --selftest

⛔ **不给件名 ⇒ 拒绝**（`TAIL-236` 决定 4：Agent 只报不动，搬运由人显式给件名触发这一条命令）。
⚠️ **为什么不要求「`T26` 报过才准搬」**：`T26` 只见**已声明「落地位置」**的件（边界写在
`audit_work.check_downgrade_candidates` 的 docstring 里）⇒ 拿它当门禁会把大部分该搬的件挡在门外。
⇒ 本命令**打印** `T26` 对该件的结论（命中/未命中 ＋ 理由 ＋ 落地位置），搬不搬由人判断。
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
sys.path.insert(0, str(ROOT / "tools" / "audit"))
#: ⛔ 下面 import 的是**口径**（仓外根 · 五区名单 · 降档两档 ＋ 判据本体 ＋ 文头窗口），本件一个字都不另抄。
from audit_common import OUTSIDE_ROOTS                              # noqa: E402
from audit_meta import WORK_DIR_ALLOW                               # noqa: E402
from audit_work import (                                            # noqa: E402
    DOWNGRADE_STATES, STATE_KEY, WORK_HEAD_LINES, check_downgrade_candidates,
)

#: 仓外归档根 = `OUTSIDE_ROOTS[0]`（`T18` 守着它在盘上真存在 ⇒ ⛔ 不在此写死第二份）
OUT_ROOT = Path(OUTSIDE_ROOTS[0])
#: 仓内过程区 → 仓外子目录。⚠️ 沿用 2026-10-05（`TAIL-235` 甲2）**已建**的落点名，⛔ 不另起名。
ZONE_OUT_SUBDIR: dict[str, str] = {"10-designs": "work-10-designs"}
#: ⛔ **不搬的区 ＋ 一句话理由**（⚠️ **不复述各区去向** —— 那是 `.codebuddy/work/README.md` §二
#:   的事；本件只负责"拒绝并指路"。重述一遍就是第二套口径，`/code-review` 2026-10-06 当场点出）。
ZONE_REFUSE: dict[str, str] = {
    "30-troubleshooting": "该区**不是搬走**",
    "40-decisions": "决策件只加不改",
    "00-scratch": "临时件按 TTL 清（`T14`）",
    "50-tickets": "票靠 `_tail_close.py` 销号（`T6` 守）",
}
#: ⭐ 区名的**唯一主人** = `audit_meta.WORK_DIR_ALLOW`（`T12` 守它）⇒ 本件只**断言覆盖得到**，
#:   ⛔ 不另抄一份五区清单（抄了 = 改一处漏一处，本仓最贵的病）。
assert set(ZONE_OUT_SUBDIR) | set(ZONE_REFUSE) <= set(WORK_DIR_ALLOW), \
    "本件认的区名不在 `WORK_DIR_ALLOW` 里 ⇒ 尺子那边改了区名，本件要跟改"
#: 仓内留痕索引 = **唯一那一份**（⚠️ 文件名里的日期是**首建**日，⛔ 别按它猜"只记 10-05 那天"）
INDEX_REL = ".codebuddy/plans/archive/归档-留痕索引-20261005.md"
#: 登记表头 —— 与索引件里那句是**一对契约**（同 `T15` 文头四词 vs `work/README.md` §四 模板那对：
#:   ⛔ 两边必须同一个词；命令找不到它就**拒绝**，绝不静默写到别处）。
INDEX_TABLE_HEAD = "| 降档日期 | 件（仓内原名） | 仓外落点（会被 `T3` 真核） | 备注 |"
#: 自测用的样本件（**脚本自己创建**，用完即删 —— ⛔ 不拿真件做实验）
SAMPLE_REL = ".codebuddy/work/10-designs/设计-_mut降档样本-20990101.md"
RULE_COUNT_MIN = 5          #: 从钩子件里解析出的尺子名单少于这个数 ⇒ 本件需重定靶
#: 闸门侧那份秒级尺子名单的**真源**（⛔ 本件只读它，不另抄）
HOOK_REL = "ops/hooks/pre-commit"


# --------------------------------------------------------------- 小工具（指纹 / git）
def _fp(paths: list[Path]) -> tuple:
    """`(相对名, 字节数, mtime_ns, md5)` 逐件 —— 证"**一个字节都没动**"。

    ⚠️ **含 mtime**：只比 md5 抓不到"重写了同样的内容"（那正是第 2 遍最该被抓住的）。
    """
    out = []
    for p in paths:
        if not p.is_file():
            out.append((str(p), None))
            continue
        b = p.read_bytes()
        out.append((str(p.relative_to(ROOT)).replace("\\", "/"), len(b),
                    p.stat().st_mtime_ns, hashlib.md5(b).hexdigest()))
    return tuple(out)


def _git(*args: str) -> tuple[int, str]:
    # ⚠️⭐ `-c core.quotepath=false`：**不加它，中文文件名会被 git 转义成 `"\346\226\207…"`**
    #   （`tools/oneoff/_oneoff_measure.py` 早为同一件事栽过）⇒ 任何"按 `.md` 结尾筛中文路径"的
    #   写法都**一个都选不出来**（首版自测第 ⑧ 项就这样空跑成"取回 0 字符"）。
    r = subprocess.run(["git", "-c", "core.quotepath=false", "--no-pager", *args], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _worktree_state() -> str:
    return _git("status", "--porcelain")[1]


# --------------------------------------------------------------- 闸门侧（跑前 / 跑后比）
def _hook_rulers() -> list[list[str]]:
    """闸门里**秒级那几把** = `ops/hooks/pre-commit` 里那份名单 —— ⚠️ **现读**，⛔ 不另抄。

    ⭐ 为什么借那份名单：降档动作只可能影响**文档面**的尺子，而"哪几把是秒级必跑"已经在钩子
    里声明过一次 ⇒ 抄一份进本件就是第二套口径。
    ⛔ **本件不断言"整套收工闸门 rc 相同"**（那套含 pytest / 真机 / 交付面，分钟级且要活服务）
    ⇒ 那一层由**人**在本批开发期手跑一次 `_run_rulers.py --all` 前后对照，结果写在
    **票面第 4 批的「✅ 已办」块**里（⛔ 别把"自测 11/11"读成"整套闸门也验过了"）。
    ⚠️ 解析**失败要报错**，⛔ 不许 `IndexError` 崩在半路（那是"钩子改版式了"的信号）。
    """
    txt = (ROOT / HOOK_REL).read_text(encoding="utf-8")
    try:
        block = txt.split("for spec in \\", 1)[1].split("\ndo", 1)[0]
        specs = [s.split() for s in re.findall(r'"([^"]+)"', block)]
    except IndexError as exc:                      # pragma: no cover
        raise SystemExit("⛔ 解析 %s 的尺子名单失败（钩子改版式了？）⇒ 本件需重定靶：%s" % (HOOK_REL, exc))
    assert len(specs) >= RULE_COUNT_MIN, \
        f"从 {HOOK_REL} 只解析出 {len(specs)} 条尺子（期望 ≥{RULE_COUNT_MIN}）⇒ 本件需重定靶"
    return specs


def _ruler_state() -> list[tuple[str, int, int, str]]:
    """→ `[(件名, rc, 红数, 关键行)]`；红数 = `必须修 N` 的 N（-1 = 那把没有这一行）。"""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    out = []
    for spec in _hook_rulers():
        r = subprocess.run([str(PY), "-X", "utf8", str(ROOT / spec[0]), *spec[1:]], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        key = next((x.strip() for x in (r.stdout or "").splitlines() if x.startswith("必须修")), "")
        n = re.search(r"必须修 (\d+)", key)
        out.append((spec[0], r.returncode, int(n.group(1)) if n else -1, key))
    return out


# --------------------------------------------------------------- 解析件名 → (区, 仓内路径)
def _in_zone_dirs() -> list[Path]:
    work = ROOT / ".codebuddy" / "work"
    return [work / z for z in sorted(ZONE_OUT_SUBDIR) if (work / z).is_dir()]


def _resolve(name: str) -> tuple[str, Path | None, str]:
    """→ `(区名, 仓内路径, 拒绝理由)`；成功时拒绝理由为空串。

    接受**件名**（`设计-x.md`）、**相对路径**（`10-designs/设计-x.md`）与**仓内绝对路径**。
    ⛔ **同名两处 ⇒ 拒绝**（让人写全相对路径）—— 猜错一件就搬错一件，这是本命令唯一不可逆的风险。
    """
    hits: list[tuple[str, Path]] = []
    for zdir in _in_zone_dirs():
        for f in sorted(zdir.glob("*.md")):
            rel = f.relative_to(ROOT).as_posix()
            if name in (f.name, rel, str(f)) or rel.endswith("/" + name.lstrip("/")):
                hits.append((zdir.name, f))
    if len(hits) > 1:
        return "", None, ("两个区各有一件叫这名 ⇒ 写全相对路径（%s）"
                          % " / ".join(h[1].relative_to(ROOT).as_posix() for h in hits))
    if not hits:
        return "", None, ""
    return hits[0][0], hits[0][1], ""


def _out_path(zone: str, name: str) -> Path:
    return OUT_ROOT / ZONE_OUT_SUBDIR[zone] / name


def _t26_says(rel: str) -> str:
    """`T26` 对该件的结论 —— **理由 ＋ 落地位置**一起给（`TAIL-236` 决定 4 要求的"报什么"三件套）。

    ⛔ **不作门禁**（理由见文件头）。⚠️ 状态读法**复用判据那一份**（`WORK_HEAD_LINES` ＋ `STATE_KEY`）
    ——⛔ 不自己再写一遍 `[:15]` / `"状态" in line`（那正是批 3 刚收口掉的"同一形状两处写"）。
    """
    for h in check_downgrade_candidates():
        if h["rel"] == rel:
            return "T26 已报它「该降档」：%s" % h["why"]
    text = (ROOT / rel).read_text(encoding="utf-8", errors="replace").splitlines()
    state = next((w for w in DOWNGRADE_STATES
                  if any(w in l for l in text[:WORK_HEAD_LINES] if STATE_KEY in l)), None)
    return ("T26 未报（%s）—— 没有「落地位置」声明行它就不归这条判据管，"
            "⛔ 那不是「没资格搬」的意思" % (f"状态档是「{state}」但没声明"
                                          if state else "不在「已定稿 / 已实施」两档"))


def _index_line(zone: str, name: str, out_abs: Path) -> str:
    """仓内索引那一行。⚠️ **取回指令故意不加反引号** —— 加了 `T3` 会把已搬走的仓内路径当幽灵报红。"""
    rel_in = f".codebuddy/work/{zone}/{name}"
    return (f"| {date.today().isoformat()} | `{name}` | `{out_abs}` |"
            f" 原区 `.codebuddy/work/{zone}/` · 取回 git show HEAD:{rel_in} |")


def _index_row_no(text: str) -> int:
    """登记表**最后一行**的行号；表头不在 ⇒ -1。

    ⚠️⚠️ 为什么**不直接追加到文件末尾**（`/code-review` 2026-10-06 当场指出）：日后有人在文件
    末尾加一个小节 ⇒ 行落表外，而"守卫串出现 1 次"照样绿 ⇒ **静默坏表**（墓碑 ≠ 守卫）。
    """
    lines = text.splitlines()
    try:
        head = next(i for i, l in enumerate(lines) if l.strip() == INDEX_TABLE_HEAD)
    except StopIteration:
        return -1
    last = head
    for i in range(head + 1, len(lines)):
        if lines[i].lstrip().startswith("|"):
            last = i
        elif lines[i].strip():
            break
    return last


def _index_check(out_abs: Path) -> str:
    """**只读**预检 → `"ok"` / `"already"` / `"no-index"` / `"no-head"`（⛔ 预检不写任何字节）。"""
    p = ROOT / INDEX_REL
    if not p.is_file():
        return "no-index"
    text = p.read_text(encoding="utf-8")
    if _index_row_no(text) < 0:
        return "no-head"
    # ⚠️ **守卫 = 那一行里的仓外落点字面**（不是件名！）—— 件名会与索引里已有的**叙述段**撞车
    #   （那份索引本来就逐个点名过 20 多件设计件）⇒ 用件名判幂等会**假命中**，把真活儿当成"已做过"。
    return "already" if str(out_abs) in text else "ok"


def _index_insert(line: str, out_abs: Path) -> None:
    """把那一行插进表内（幂等守卫已由 `_index_check` 做过）。"""
    p = ROOT / INDEX_REL
    raw = p.read_bytes()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    lines = raw.decode("utf-8").splitlines()
    pos = _index_row_no("\n".join(lines))
    assert pos >= 0, "表头不在 ⇒ `_index_check` 应当先拦住"
    lines.insert(pos + 1, line)
    p.write_bytes((nl.join(lines).rstrip("\r\n") + nl).encode("utf-8"))
    back = p.read_bytes().decode("utf-8")
    assert back.count(str(out_abs)) == 1, "索引里那一行没落上或落重了 ⇒ 写坏了"
    assert ("\r\n" in back) == (nl == "\r\n"), "索引行尾被改乱 ⇒ 写坏了"
    bl = back.splitlines()
    assert any(str(out_abs) in l for l in bl[:_index_row_no(back) + 1]), \
        "那一行没落在登记表里（落表外了）⇒ 写坏了"


# --------------------------------------------------------------- 主流程
def do_downgrade(name: str, apply: bool) -> int:
    zone, path, err = _resolve(name)
    fname = Path(name).name
    if err:
        print("⛔ %s" % err)
        return 1
    if not zone:
        # 仓内没有：要么已降档（幂等），要么件名错 / 在不搬的区
        for z in ZONE_OUT_SUBDIR:
            out_abs = _out_path(z, fname)
            if out_abs.is_file():
                print("✅ 幂等：%s 已在仓外（%s）· 仓内没有原件 · 本次**一个字节都没动**"
                      % (fname, out_abs))
                return 0
        for z, why in ZONE_REFUSE.items():
            if (ROOT / ".codebuddy" / "work" / z / fname).is_file():
                print("⛔ `%s/` 的件不走降档：%s" % (z, why))
                print("   （去向口径 = `.codebuddy/work/README.md` §二 本区那一行）")
                return 1
        print("⛔ 找不到这件：%s" % name)
        print("   只降档 `%s` 里的设计件" % "/".join(sorted(ZONE_OUT_SUBDIR)))
        return 1

    out_abs = _out_path(zone, fname)
    rel = path.relative_to(ROOT).as_posix()
    line = _index_line(zone, fname, out_abs)
    st = _index_check(out_abs)
    print("降档 · %s" % fname)
    print("  区     %s（依据 `.codebuddy/work/README.md` §二：本区定稿实施完 ⇒ 归档仓外）" % zone)
    print("  仓内   %s" % rel)
    print("  仓外   %s" % out_abs)
    print("  索引   %s" % INDEX_REL)
    print("  判据   %s" % _t26_says(rel))
    if st == "no-index":
        print("⛔ 仓内索引件不在：%s ⇒ 拒绝（不留没有指针的搬运）" % INDEX_REL)
        return 1
    if st == "no-head":
        print("⛔ 索引件里没有登记表头（%s…）⇒ 拒绝，⛔ 绝不静默写到别处" % INDEX_TABLE_HEAD[:20])
        return 1
    if not apply:
        print("\n[dry] 未动手（真搬要加 --apply）· 计划写进登记表的那一行：\n  %s" % line)
        return 0

    if not out_abs.parent.is_dir():
        out_abs.parent.mkdir(parents=True, exist_ok=True)
        print("  仓外   （新建落点目录 %s）" % out_abs.parent)
    # ⭐ 顺序：**先搬、后写索引** —— 反过来的话，`move` 失败就留下"指针指向不存在的仓外件"半状态。
    shutil.move(str(path), str(out_abs))
    try:
        if st == "already":
            print("  索引   已有那一行 ⇒ 不重复写（幂等）")
        else:
            _index_insert(line, out_abs)
    except Exception:                                              # noqa: BLE001
        shutil.move(str(out_abs), str(path))                        # 回滚：搬回去，不留半状态
        print("⛔ 索引写入失败 ⇒ **已把件搬回原处**（不留半状态）")
        raise
    print("✅ 已搬：仓内原件已移出 · 仓外留原文 · 索引%s"
          % ("原有一行（未重复写）" if st == "already" else "已留行"))
    print("   后悔时：① 把 %s 搬回 %s ② 删掉索引里那一行" % (out_abs, rel))
    return 0


# --------------------------------------------------------------- 自测（缝 C 五件事 ＋ 4 条验收）
def _sample_text() -> str:
    return ("# 设计降档样本（自测临时件 · 用完即删）\n\n读者：`_doc_downgrade.py --selftest`\n"
            "回答：本件能不能被可逆地搬走\n何时读：从不（自测注入）\n"
            "状态：已实施（自测样本）· 关联 `TAIL-225`\n\n⭐ **落地位置**：`ops/阈值表.md`\n"
            "自测注入，⛔ 不是真文档。\n")


def _selftest() -> int:
    res: list[tuple[str, bool]] = []

    def chk(label: str, ok: bool) -> None:
        res.append((label, bool(ok)))
        print("  %s %s" % ("✅" if ok else "⛔", label))

    sample, idx = ROOT / SAMPLE_REL, ROOT / INDEX_REL
    zone = sample.parent
    out_abs = _out_path(zone.name, sample.name)
    line = _index_line(zone.name, sample.name, out_abs)
    in_zone = sorted(zone.glob("*.md"))

    def _strip_row() -> None:
        """中断自愈：把残留的那一行去掉 —— ⚠️ **必须认原行尾**。

        ⛔ 首版用 `("\\n".join(keep) + "\\n")` 重建 ⇒ 那是 **CRLF** 的索引件被整篇改成 **LF**
        ⇒ 收尾的「索引字节一致」当场变红（**自测抓到的真 bug**，不是判据太严）。
        """
        if not idx.is_file():
            return
        raw = idx.read_bytes()
        nl = "\r\n" if b"\r\n" in raw else "\n"
        lines = raw.decode("utf-8").splitlines()
        keep = [x for x in lines if str(out_abs) not in x]
        if len(keep) != len(lines):
            idx.write_bytes((nl.join(keep).rstrip("\r\n") + nl).encode("utf-8"))

    def cleanup(heal: bool = False) -> None:
        """自愈 / 收尾：**把样本搬回仓内** ＋ 清仓外残留 ＋ 索引复原。

        ⚠️ 收尾走**按字节回写快照**，⛔ 不"逐行删回去"重建（重建会重排行尾 ⇒ 复原断言必红）。
        """
        if out_abs.is_file() and not sample.is_file():
            out_abs.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(out_abs), str(sample))
        for p in (sample, out_abs):
            if p.is_file():
                p.unlink()
        if not heal and idx.is_file() and idx.read_bytes() != idx_bytes0:
            idx.write_bytes(idx_bytes0)
        _strip_row()

    cleanup(heal=True)                          # ⭐ 中断自愈：跑本件之前它们不该存在
    idx_bytes0 = idx.read_bytes()               # 复原基准 = **自愈之后**的样子
    fp_zone0, git0 = _fp(in_zone), _worktree_state()

    print("  ① 不给件名 ⇒ 拒绝（**入口**就拒，⛔ 不是「进了函数再拒」）")
    rc = main([])
    chk("不给件名 rc=%d（非 0）且工作区未变" % rc, rc != 0 and _worktree_state() == git0)

    print("  ② 跑前闸门基线（名单现读自 `%s`）" % HOOK_REL)
    before = _ruler_state()
    for nm, r, n, k in before:
        # ⚠️ **只在有红时打关键行** —— 全绿那行含「必须修 0」⇒ 会被收工闸门的摘要过滤选中，
        #   把真正的结论行「自测 N/N」挤出前三行（`refs_query` 那行会被挡住；实测才发现）。
        print("     %-34s rc=%d 红=%s%s" % (nm, r, n, ("  " + k[:46]) if n != 0 else ""))
    chk("跑前无红", all(n <= 0 for _nm, _r, n, _k in before))
    y_base = next((int(re.search(r"疑似 (\d+)", k).group(1)) for nm, _r, _n, k in before
                   if nm.endswith("doc_audit.py") and "疑似" in k), -1)

    sample.write_text(_sample_text(), encoding="utf-8", newline="")
    out_abs.parent.mkdir(parents=True, exist_ok=True)
    try:
        print("  ③ 造好样本 ⇒ **`T26` 此刻应该报它**（正向断言：没有这一条，`T26` 整体死掉也能满分）")
        chk("T26 报了样本", any(h["rel"] == SAMPLE_REL for h in check_downgrade_candidates()))

        print("  ④ 默认干跑 ⇒ 不动手")
        rc = do_downgrade(sample.name, apply=False)
        no_move = sample.is_file() and not out_abs.is_file() and str(out_abs) not in idx.read_text(encoding="utf-8")
        chk("干跑 rc=%d · 原件仍在原处、索引未动" % rc, rc == 0 and no_move)

        print("  ⑤ 真搬（--apply）⇒ 三件事：仓外留原文 ＋ 仓内已移出 ＋ 索引留行")
        rc = do_downgrade(sample.name, apply=True)
        txt = idx.read_text(encoding="utf-8")
        chk("真搬 rc=%d · 仓外在位=%s 仓内已移出=%s 索引有行=%s"
            % (rc, out_abs.is_file(), not sample.is_file(), str(out_abs) in txt),
            rc == 0 and out_abs.is_file() and not sample.is_file() and str(out_abs) in txt)

        print("  ⑥ 可逆：索引里那一行的仓外落点 **== 仓外真路径**（`T3` 核的就是它）＋ 取回指令在行内")
        # ⚠️⚠️ 只能在**我那一行里**找 token ——⛔ 不能对整篇找：这份索引头部就有别的仓外路径
        #    （`plans-archive\`），取第一个 ⇒ 拿到的是**别人那行**（首版就这么错，判据自己报了）。
        my_row = next((x for x in txt.splitlines() if str(out_abs) in x), "")
        tok = re.search(r"`([A-Za-z]:[\\/][^`]+?)`", my_row)
        chk("我那一行里的 token=%s · 取回指令在行内=%s"
            % (tok.group(1) if tok else "（没找到）", f"git show HEAD:{SAMPLE_REL}" in my_row),
            bool(tok) and tok.group(1) == str(out_abs) and f"git show HEAD:{SAMPLE_REL}" in my_row)

        print("  ⑦ 索引已有那一行 ＋ 原件回到仓内 ⇒ **不重复写行**、仍能搬（`already` 分支）")
        out_abs.replace(sample)                    # 人把文件搬回来了、忘了删索引行
        n_row0 = idx.read_text(encoding="utf-8").count(str(out_abs))
        rc = do_downgrade(sample.name, apply=True)
        n_row1 = idx.read_text(encoding="utf-8").count(str(out_abs))
        chk("rc=%d · 索引里那一行仍是 %d 行（没写重）· 件又搬出去了=%s"
            % (rc, n_row1, out_abs.is_file()),
            rc == 0 and n_row0 == 1 and n_row1 == 1 and out_abs.is_file() and not sample.is_file())

        print("  ⑧ 再跑一遍（件已在仓外）⇒ 字节级 no-op")
        fp_a = (_fp(in_zone), idx.read_bytes(), _worktree_state())
        rc = do_downgrade(sample.name, apply=True)
        fp_b = (_fp(in_zone), idx.read_bytes(), _worktree_state())
        chk("rc=%d · 过程区指纹一致=%s 索引字节一致=%s git 状态一致=%s"
            % (rc, fp_a[0] == fp_b[0], fp_a[1] == fp_b[1], fp_a[2] == fp_b[2]),
            rc == 0 and fp_a == fp_b)

        print("  ⑨ 跑后闸门：逐把 rc 一致 ＋ 仍无红 ＋ 疑似数回到跑前 ＋ `T26` 不再报它")
        after = _ruler_state()
        amap = {x[0]: x for x in after}
        same_rc = [x[0] for x in before if amap[x[0]][1] != x[1]]
        reds = [x[0] for x in after if x[2] > 0]
        y_now = next((int(re.search(r"疑似 (\d+)", k).group(1)) for nm, _r, _n, k in after
                      if nm.endswith("doc_audit.py") and "疑似" in k), -2)
        t26_gone = not any(h["rel"] == SAMPLE_REL for h in check_downgrade_candidates())
        chk("rc 有变=%s · 跑后红=%d · doc_audit 疑似 %d→%d（期望回到跑前）· T26 不再报=%s"
            % (same_rc or "无", len(reds), y_base, y_now, t26_gone),
            not same_rc and not reds and y_now == y_base and t26_gone)

        print("  ⑩ git 取回那条路：对**已提交的真件**可用（样本来不及进 HEAD ⇒ 那一步只能这样证）")
        _rc, tracked = _git("ls-files", ".codebuddy/work/10-designs")
        first = next((x for x in tracked.splitlines() if x.endswith(".md")), "")
        rc2, body = _git("show", f"HEAD:{first}") if first else (1, "")
        chk("git show HEAD:%s 取回 %d 字符" % (first or "（没找到已跟踪件）", len(body)),
            bool(first) and rc2 == 0 and len(body.strip()) > 0)
    finally:
        cleanup()

    print("  ⑪ 复原：git 状态 ＋ 过程区指纹 ＋ 索引字节 ＋ 仓外残留，四样都回到跑前")
    chk("git 状态一致=%s 过程区指纹一致=%s 索引字节一致=%s 仓外无残留=%s"
        % (_worktree_state() == git0, _fp(in_zone) == fp_zone0,
           idx.read_bytes() == idx_bytes0, not out_abs.is_file()),
        _worktree_state() == git0 and _fp(in_zone) == fp_zone0
        and idx.read_bytes() == idx_bytes0 and not out_abs.is_file())
    bad = [x for x in res if not x[1]]
    print("  自测 %d/%d%s" % (len(res) - len(bad), len(res),
                             ("　⛔ 未过：" + "、".join(b[0] for b in bad)) if bad else ""))
    return 0 if not bad else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="降档动作（可逆搬运 ＋ 仓内索引留行）· 默认干跑")
    ap.add_argument("name", nargs="?", help="件名 / 相对路径（⛔ 不给 ⇒ 拒绝）")
    ap.add_argument("--apply", action="store_true", help="真搬（不给就是干跑）")
    ap.add_argument("--selftest", action="store_true", help="自测（造样本 → 跑 → 复原）")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if a.selftest:
        print("降档动作 · 自测")
        print("=" * 78)
        return _selftest()
    if not a.name:
        ap.print_usage()
        print("\n⛔ **不给件名 ⇒ 不降档**（`TAIL-236` 决定 4：Agent 只报不动，搬运由人给件名触发）。")
        print("   例：%s 设计-xxx.md --apply" % Path(sys.argv[0]).name)
        return 2
    return do_downgrade(a.name, a.apply)


if __name__ == "__main__":
    sys.exit(main())
