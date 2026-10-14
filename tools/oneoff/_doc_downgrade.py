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
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "audit"))
#: ⛔ 下面 import 的是**口径**（仓外根 · 五区名单 · 降档两档 ＋ 判据本体 ＋ 文头窗口），本件一个字都不另抄。
from audit_common import OUTSIDE_ROOTS                              # noqa: E402
from audit_meta import WORK_DIR_ALLOW                               # noqa: E402
from audit_work import (                                            # noqa: E402
    DOWNGRADE_STATES, STATE_KEY, WORK_HEAD_LINES, check_downgrade_candidates,
)
#: 引用口径**只从 `refs_query` 取**（活机器六路 / 活文档 / 未销号票 —— ⛔ 本件不另扫一份）。
from refs_query import (                                            # noqa: E402
    Blob, build_doc_corpus, build_live_corpus, build_ticket_corpus, build_tickets, find_refs,
)

#: 仓外归档根 = `OUTSIDE_ROOTS[0]`（`T18` 守着它在盘上真存在 ⇒ ⛔ 不在此写死第二份）
OUT_ROOT = Path(OUTSIDE_ROOTS[0])
#: 仓内过程区 → 仓外子目录。⚠️ 沿用 2026-10-05（`TAIL-235` 甲2）**已建**的落点名，⛔ 不另起名。
ZONE_OUT_SUBDIR: dict[str, str] = {"10-designs": "work-10-designs"}
#: ⛔ **不搬的区 ＋ 一句话理由**（⚠️ **不复述各区去向** —— 那是 `docs/guides/work-records.md` §二
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
INDEX_REL = "docs/archive/legacy-plans/归档-留痕索引-20261005.md"
#: 登记表头 —— 与索引件里那句是**一对契约**（同 `T15` 文头四词 vs `work/README.md` §四 模板那对：
#:   ⛔ 两边必须同一个词；命令找不到它就**拒绝**，绝不静默写到别处）。
INDEX_TABLE_HEAD = "| 降档日期 | 件（仓内原名） | 仓外落点（会被 `T3` 真核） | 备注 |"
#: 自测样本仅存在于临时仓库，引用查询和T26读取同一隔离现场。
SAMPLE_REL = ".codebuddy/work/10-designs/设计-_mut降档自测件-20990101.md"


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
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _worktree_state() -> str:
    return _git("status", "--porcelain")[1]


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


def _refs_of(rel: str) -> list[tuple[str, str, int]]:
    """→ `[(路名, 引用方, 行号)]`（活机器 / 活文档 / 未销号票）—— ⛔ 口径全部 import `refs_query`。

    ⭐⭐ **为什么要这个守卫**（2026-10-06 `/retro` 当场暴露，票面 `Implementation Decisions` 3
    只写了前半句）：**判据不看引用、动作要看**。
      · 判据（`T26`）不看引用 ＝ 对：它只报"该降档"，搬不搬是人的决定；
      · **动作必须看** —— 2026-10-06 实测：**11 件设计件每一件都有活引用**（三路全 0 的 27 件里
        一件设计件都没有）⇒ 搬任何一件都会留下**死指针**，而 `T3` 只扫文档面、
        **照不到 `.py` docstring / 一次性脚本里的指针** ⇒ 搬完**没有人喊**。
    ⇒ `--apply` 前有引用就**拒绝**，并把位置逐条列出来（让人同批改）。
    """
    name = rel.rsplit("/", 1)[-1]
    skip = frozenset({rel})
    live, _lanes = build_live_corpus()
    doc, _lenient = build_doc_corpus()
    open_tickets, _closed = build_tickets()
    tick = build_ticket_corpus(open_tickets)
    out: list[tuple[str, str, int]] = []
    for blob, label in ((Blob(live), "机器"), (Blob(doc), "文档"), (Blob(tick), "票")):
        out += [(label, o, n) for _lane, o, n in find_refs(blob, rel, name, skip)]
    return out


def _index_line(zone: str, name: str, out_abs: Path) -> str:
    """固定源提交，归档删除提交后仍可取回；未入Git的件从仓外原文恢复。"""
    rel_in = f".codebuddy/work/{zone}/{name}"
    rc, revision = _git("rev-parse", "HEAD")
    revision = revision.strip()
    recorded = (rc == 0 and _git("cat-file", "-e", f"{revision}:{rel_in}")[0] == 0
                and _git("diff", "--quiet", revision, "--", rel_in)[0] == 0)
    # 取回指令不加反引号，避免T3把已搬走的原路径当成现行引用。
    recovery = (f"取回 git show {revision}:{rel_in}" if recorded
                else "Git未保存当前原文，原文从仓外落点取回")
    return (f"| {date.today().isoformat()} | `{name}` | `{out_abs}` |"
            f" 原区 `.codebuddy/work/{zone}/` · {recovery} |")


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
                print("   （去向口径 = `docs/guides/work-records.md` §二 本区那一行）")
                return 1
        print("⛔ 找不到这件：%s" % name)
        print("   只降档 `%s` 里的设计件" % "/".join(sorted(ZONE_OUT_SUBDIR)))
        return 1

    out_abs = _out_path(zone, fname)
    rel = path.relative_to(ROOT).as_posix()
    line = _index_line(zone, fname, out_abs)
    st = _index_check(out_abs)
    refs = _refs_of(rel)
    print("降档 · %s" % fname)
    print("  区     %s（依据 `docs/guides/work-records.md` §二：本区定稿实施完 ⇒ 归档仓外）" % zone)
    print("  仓内   %s" % rel)
    print("  仓外   %s" % out_abs)
    print("  索引   %s" % INDEX_REL)
    print("  判据   %s" % _t26_says(rel))
    print("  引用   %s" % ("**零引用**（三路都没有人用它）" if not refs
                         else "%d 处（%s）" % (len(refs), " · ".join(
                             "%s %s:%d" % (lane, o, n) for lane, o, n in refs[:6]))))
    if st == "no-index":
        print("⛔ 仓内索引件不在：%s ⇒ 拒绝（不留没有指针的搬运）" % INDEX_REL)
        return 1
    if st == "no-head":
        print("⛔ 索引件里没有登记表头（%s…）⇒ 拒绝，⛔ 绝不静默写到别处" % INDEX_TABLE_HEAD[:20])
        return 1
    if not apply:
        print("\n[dry] 未动手（真搬要加 --apply）· 计划写进登记表的那一行：\n  %s" % line)
        return 0
    if refs:
        print("⛔ **它还有 %d 处活引用 ⇒ 拒绝搬**" % len(refs))
        print("   理由：搬走 ⇒ 这些指针全变死指针，而 `T3` 只扫文档面、**照不到 `.py` / 脚本里的指针**")
        print("        ⇒ 搬完**没有任何尺子会喊**（这正是 2026-10-06 实测：`refs_query --all` 显示"
              "11 件设计件每一件都有引用）")
        for lane, o, n in refs[:15]:
            print("     %s %s:%d" % (lane, o, n))
        print("   ⛔ 先**同批**改掉这些指针（或确认它们只是留痕叙述），再重跑；"
              "复查：`tools/audit/refs_query.py %s`" % fname)
        return 1

    if out_abs.exists():
        print("⛔ 仓外已有同名件：%s ⇒ 拒绝覆盖，原件和索引未动" % out_abs)
        return 1

    if not out_abs.parent.is_dir():
        out_abs.parent.mkdir(parents=True, exist_ok=True)
        print("  仓外   （新建落点目录 %s）" % out_abs.parent)
    # ⭐ 顺序：**先搬、后写索引** —— 反过来的话，`move` 失败就留下"指针指向不存在的仓外件"半状态。
    idx = ROOT / INDEX_REL
    idx_before = idx.read_bytes()
    shutil.move(str(path), str(out_abs))
    try:
        if st == "already":
            print("  索引   已有那一行 ⇒ 不重复写（幂等）")
        else:
            _index_insert(line, out_abs)
    except Exception:                                              # noqa: BLE001
        try:
            idx.write_bytes(idx_before)
        finally:
            shutil.move(str(out_abs), str(path))
        print("⛔ 索引写入失败 ⇒ **原件与索引均已恢复**（不留半状态）")
        raise
    print("✅ 已搬：仓内原件已移出 · 仓外留原文 · 索引%s"
          % ("原有一行（未重复写）" if st == "already" else "已留行"))
    print("   后悔时：① 把 %s 搬回 %s ② 删掉索引里那一行" % (out_abs, rel))
    return 0


# --------------------------------------------------------------- 自测（缝 C 五件事 ＋ 4 条验收）
def _sample_text() -> str:
    return ("# 设计降档样本（自测临时件 · 用完即删）\n\n读者：`_doc_downgrade.py --selftest`\n"
            "回答：本件能不能被可逆地搬走\n何时读：从不（自测注入）\n"
            "状态：已实施（自测样本）· 关联 `TAIL-225`\n\n⭐ **落地位置**：`docs/reference/thresholds.md`\n"
            "自测注入，⛔ 不是真文档。\n")


def _selftest() -> int:
    """在临时仓与临时仓外目录验证真实动作；只替换路径，不替换判据或引用查询。"""
    import tempfile
    from contextlib import ExitStack
    from unittest.mock import patch

    import audit_meta
    import audit_work
    import refs_query

    with tempfile.TemporaryDirectory(prefix="tmp-doc-downgrade-") as folder, ExitStack() as stack:
        fixture = Path(folder) / "repo"
        fixture.mkdir()
        stack.enter_context(patch.multiple(sys.modules[__name__], ROOT=fixture,
                                           OUT_ROOT=Path(folder) / "archive"))
        for module in (audit_meta, audit_work, refs_query):
            stack.enter_context(patch.object(module, "REPO_ROOT", fixture))
        return _selftest_fixture()


def _selftest_fixture() -> int:
    from unittest.mock import patch

    res: list[tuple[str, bool]] = []

    def chk(label: str, ok: bool) -> None:
        res.append((label, bool(ok)))
        print("  %s %s" % ("✅" if ok else "⛔", label))

    sample, idx = ROOT / SAMPLE_REL, ROOT / INDEX_REL
    for parent in (sample.parent, idx.parent, ROOT / "docs/reference", ROOT / "tools/probe",
                   ROOT / ".codebuddy/work/50-tickets"):
        parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "docs/reference/thresholds.md").write_text("# 隔离落地样本\n", encoding="utf-8")
    closed = ROOT / ".codebuddy/work/50-tickets/TAIL-225-样本.md"
    closed.write_text("**Status:** done\n", encoding="utf-8")
    idx_bytes0 = ("# 隔离索引\r\n\r\n" + INDEX_TABLE_HEAD
                  + "\r\n|---|---|---|---|\r\n\r\n## 表后内容\r\n").encode("utf-8")
    idx.write_bytes(idx_bytes0)
    sample_bytes = _sample_text().encode("utf-8")
    sample.write_bytes(sample_bytes)
    commit_args = ("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                   "-c", "core.hooksPath=" + str(ROOT / "no-hooks"), "commit", "-qm")
    for args in (("init", "-q"), ("add", SAMPLE_REL, INDEX_REL, "docs/reference/thresholds.md",
                 closed.relative_to(ROOT).as_posix()),
                 (*commit_args, "fixture")):
        rc, output = _git(*args)
        if rc != 0:
            raise RuntimeError("隔离Git准备失败：" + output)
    git0 = _worktree_state()
    out_abs = _out_path(sample.parent.name, sample.name)

    chk("不给件名拒绝且工作区未变", main([]) == 2 and _worktree_state() == git0)
    chk("真实T26能报告已落地样本", any(h["rel"] == SAMPLE_REL
                                       for h in check_downgrade_candidates()))
    dirty_bytes = sample_bytes + "未提交的新内容\n".encode("utf-8")
    sample.write_bytes(dirty_bytes)
    rc = do_downgrade(sample.name, True)
    dirty_row = idx.read_text(encoding="utf-8")
    chk("未提交修改从仓外恢复当前原文", rc == 0 and not sample.exists()
        and out_abs.read_bytes() == dirty_bytes and "原文从仓外落点取回" in dirty_row
        and "git show" not in dirty_row)
    shutil.move(str(out_abs), str(sample))
    sample.write_bytes(sample_bytes)
    idx.write_bytes(idx_bytes0)
    idx.unlink()
    chk("缺索引拒绝且原文未动", do_downgrade(sample.name, True) != 0
        and sample.read_bytes() == sample_bytes and not out_abs.exists())
    idx.write_bytes(b"# invalid index\r\n")
    chk("缺表头拒绝且原文未动", do_downgrade(sample.name, True) != 0
        and sample.read_bytes() == sample_bytes and not out_abs.exists())
    idx.write_bytes(idx_bytes0)
    before = _fp([sample, idx])
    chk("默认干跑不改字节或mtime", main([sample.name]) == 0
        and _fp([sample, idx]) == before and not out_abs.exists())

    for lane, rel in (("机器", "tools/probe/refers_sample.py"),
                      ("文档", "docs/reference/活引用.md"),
                      ("票", ".codebuddy/work/50-tickets/TAIL-226-引用.md")):
        referrer = ROOT / rel
        referrer.write_text("**Status:** ready-for-agent\n# 指向 " + SAMPLE_REL + "\n",
                            encoding="utf-8")
        try:
            refs = _refs_of(SAMPLE_REL)
            chk(lane + "活引用拒绝且原文未动", any(r[0] == lane for r in refs)
                and do_downgrade(sample.name, True) != 0
                and sample.read_bytes() == sample_bytes and idx.read_bytes() == idx_bytes0
                and not out_abs.exists())
        finally:
            referrer.unlink()

    for zone in ("30-troubleshooting", "40-decisions"):
        refused = ROOT / ".codebuddy/work" / zone / "拒绝样本.md"
        refused.parent.mkdir(parents=True, exist_ok=True)
        refused.write_bytes(sample_bytes)
        chk(zone + "拒绝且原件未动", do_downgrade(refused.name, True) != 0
            and refused.read_bytes() == sample_bytes and idx.read_bytes() == idx_bytes0)
        refused.unlink()

    out_abs.parent.mkdir(parents=True, exist_ok=True)
    out_abs.write_bytes(b"existing archive")
    rc = do_downgrade(sample.name, True)
    chk("仓外同名件拒绝覆盖", rc != 0 and sample.is_file()
        and out_abs.read_bytes() == b"existing archive" and idx.read_bytes() == idx_bytes0)
    # 此处只恢复隔离样本，使失败也能继续检查其余行为。
    sample.write_bytes(sample_bytes)
    out_abs.unlink()
    idx.write_bytes(idx_bytes0)

    def broken_index(*_args) -> None:
        idx.write_bytes(b"partial index write")
        raise OSError("隔离注入：索引写入中断")

    try:
        with patch.object(sys.modules[__name__], "_index_insert", side_effect=broken_index):
            do_downgrade(sample.name, True)
    except OSError:
        chk("索引写入失败同时恢复原文和索引", sample.is_file()
            and sample.read_bytes() == sample_bytes and not out_abs.exists()
            and idx.read_bytes() == idx_bytes0)
    else:
        chk("索引写入失败必须暴露", False)
    idx.write_bytes(idx_bytes0)

    rc = do_downgrade(sample.name, True)
    text = idx.read_text(encoding="utf-8")
    chk("真搬保留原文字节且索引入表", rc == 0 and not sample.exists()
        and out_abs.read_bytes() == sample_bytes and text.count(str(out_abs)) == 1
        and any(str(out_abs) in row for row in text.splitlines()[:_index_row_no(text) + 1])
        and b"\r\n" in idx.read_bytes() and b"\n" not in idx.read_bytes().replace(b"\r\n", b""))
    row = next(line for line in text.splitlines() if str(out_abs) in line)
    match = re.search(r"git show ([0-9a-f]+):" + re.escape(SAMPLE_REL), row)
    for args in (("add", "-u", SAMPLE_REL, INDEX_REL), (*commit_args, "archive")):
        rc, output = _git(*args)
        if rc != 0:
            raise RuntimeError("隔离归档提交失败：" + output)
    rc, recovered = _git("show", match.group(1) + ":" + SAMPLE_REL) if match else (1, "")
    chk("归档删除提交后固定SHA仍可恢复同一件", str(out_abs) in row
        and _git("show", "HEAD:" + SAMPLE_REL)[0] != 0 and rc == 0
        and recovered.encode("utf-8") == sample_bytes)
    before = (idx.read_bytes(), idx.stat().st_mtime_ns,
              out_abs.read_bytes(), out_abs.stat().st_mtime_ns, _worktree_state())
    rc = do_downgrade(sample.name, True)
    chk("重复执行不改字节、mtime或Git状态", rc == 0 and before
        == (idx.read_bytes(), idx.stat().st_mtime_ns, out_abs.read_bytes(),
            out_abs.stat().st_mtime_ns, _worktree_state()))
    chk("搬后T26不再报告样本", not any(h["rel"] == SAMPLE_REL
                                       for h in check_downgrade_candidates()))
    shutil.move(str(out_abs), str(sample))
    rc = do_downgrade(sample.name, True)
    chk("原件恢复后再搬不重复索引", rc == 0 and not sample.exists()
        and out_abs.read_bytes() == sample_bytes
        and idx.read_text(encoding="utf-8").count(str(out_abs)) == 1)
    shutil.move(str(out_abs), str(sample))
    idx.write_bytes(idx_bytes0)
    for args in (("add", SAMPLE_REL, INDEX_REL), (*commit_args, "restore")):
        rc, output = _git(*args)
        if rc != 0:
            raise RuntimeError("隔离恢复提交失败：" + output)
    chk("恢复后原文、索引和Git状态一致且仓外无残留", sample.read_bytes() == sample_bytes
        and idx.read_bytes() == idx_bytes0 and _worktree_state() == git0
        and not out_abs.exists())
    bad = [label for label, ok in res if not ok]
    print("  自测 %d/%d%s" % (len(res) - len(bad), len(res),
                              "　⛔ 未过：" + "、".join(bad) if bad else ""))
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="降档动作（可逆搬运 ＋ 仓内索引留行）· 默认干跑")
    ap.add_argument("name", nargs="?", help="件名 / 相对路径（⛔ 不给 ⇒ 拒绝）")
    ap.add_argument("--apply", action="store_true", help="真搬（不给就是干跑）")
    ap.add_argument("--selftest", action="store_true", help="隔离自测（临时仓内验证搬运与恢复）")
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
