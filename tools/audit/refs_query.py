#!/usr/bin/env python
"""refs —— 「这份文档还有谁在引用」的**只读**查询命令（`TAIL-236` 第 2 批）。

**回答什么**：敲一条命令拿到**三路计数** —— ① 机器引用 ② 活文档口径引用 ③ 未销号票 ——
并自报「**不动的 N 件 ＋ 各自引用数**」⇒ 覆盖面**不用靠回忆核对**。

**为什么值得有**（2026-10-05 实测，当天栽过两次）：清「零机器引用的死重」时，第一版口径只扫代码，
**漏了运维脚本与规则档两路** ⇒ 差点把被运维脚本引用的设计件一起搬走；另有一份**机器引用 0** 的母本
被四张票当唯一依据 ⇒ **零引用只是信号，不是结论**。

**口径只有一份**（⛔ 别在本件里另抄一份）：机器侧 = `audit_common.LIVE_MACHINE_GLOBS`
（`T23` 钉住"缺一路必须报红"）· 文档侧 = `audit_common.SCAN_GLOBS`（减留痕区）· 票侧 = `audit_meta`
的票目录与状态词。⛔ 本件**只读**：不改、不删、不写任何文件。

**为什么不拆（`T5` 黄档 · 400~600 区间 · 2026-10-05 当天量）**：本件落在**四百多行**（⛔ 现值
跑 `doc_audit` 取 —— 数字别抄进注释，抄了必漂），其中约四成是"为什么这么写"的注释。
三条理由：① 拆成"扫描基础设施 ＋ 报告"两件 ⇒ **「口径住在哪」多一处**，
而 `T23` 半边③ 只扫本件（拆了就得扫两件 ⇒ 判据跟着变复杂）；② 拆完逻辑件仍三百多行，
**没解决"长"的病，只多一次跨件跳转**；③ `T5` 在 400~600 只提醒，**>600 才要求**在
`docs/reference/thresholds.md` 点名"为什么不拆" ⇒ 真长过 600 时再登记。

用法（⚠️ 路径含中文时**别靠 argv 传**，`python -c` 与 PowerShell 都吃过字）：

    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\audit\\refs_query.py <件名或路径片段>
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\audit\\refs_query.py --all
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\audit\\refs_query.py --all --selftest
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

#: ⛔ **下面 import 的是"口径"，本件一个字都不许另抄** —— 抄一份就有第二套口径（本仓最贵的病）。
from audit_common import (                                         # noqa: E402
    DOC_SUFFIXES, LENIENT_GLOBS, LIVE_MACHINE_GLOBS, REPO_ROOT, SCAN_GLOBS, TOP_DIRS,
)
from audit_meta import (                                            # noqa: E402
    TICKET_CLOSED, TICKET_DIR_REL, TICKET_NAME_RE, TICKET_STATE_RE, TICKET_STATES,
)

#: 票目录（前缀形态）—— 活文档那一路**排除**它，票的引用**单列第三路**。
TICKET_PREFIX = TICKET_DIR_REL + "/"

#: 盘点对象 = 文档件（⛔ 后缀表**不在这里另抄** —— `/code-review` 当场抓过这一条：
#: `DOC_SUFFIXES` 的真源是 `audit_common`，本件只 import）。

#: ⛔ **分母里排除的目录 ＋ 每一条的理由**（`refs` 的数只有连分母一起看才有意义 ——
#:    2026-10-05 实测教训「报数之前先问这个数分母是什么」）。
#: ⚠️ 这里**故意只排"按制度会消失 / 不是文档"**的目录；留痕区（逐日日志 / 归档 / 设计件）
#:    **一律留在分母里** —— 当天差点被搬走的就是设计件，排掉它等于把眼睛闭上。
#: ⚠️⚠️ **它不是 `T14`/`T15` 那两张白名单**（`/code-review` 当场指出这里容易看错）：
#:    那两张管的是「**尺子看不看**那一件」，本表管的是「**盘点分母里算不算**」——
#:    同一个目录可以在两张表里都出现、也可以只在一张里（`artifacts/` 在 `T15` 白名单里，
#:    但它是**生成物**，盘点时也不该当文档件数）⇒ **别把"加进这里"当成"尺子也不看它了"**。
EXCLUDE_PREFIXES: tuple[tuple[str, str], ...] = (
    (".git/", "版本库内部"),
    ("backend/.venv/", "虚拟环境（非本仓产物）"),
    ("artifacts/", "工具生成物（`T11` 管回执，不管措辞）"),
    ("logs/", "运行日志"),
    (".codebuddy/backups/", "保留期目录（按制度会清，`T20` 管）"),
    (".codebuddy/work/00-scratch/", "临时件（`T14` TTL 14 天）"),
)

#: 名字边界的"不可接字符" —— 防止 `设计-x.md` 被 `设计-x-补充.md` 顺手命中。
#: ⚠️ 范围**只收会粘住名字的字符**：ASCII 字母数字 / 中文 / 下划线 / 连字符。
#:    句点与斜杠**不在内**（`ops/README.md` 这种带前缀的写法要能命中）。
#: ⚠️⛔ **别写成 `frozenset("0-9A-Za-z…")`** —— 字符串里那是**十个单字符**（`0` `-` `9` `A`…），
#:    `1`~`8`/`B`~`Y` 全部缺席 ⇒ 边界检查对半边字母形同虚设（`a1.md` 会被 `a.md` 命中）。
_BOUND_CHARS = (frozenset("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                          "abcdefghijklmnopqrstuvwxyz_-")
                | frozenset(chr(c) for c in range(0x4E00, 0x9FFF + 1)))
#: 供自检断言用（半边：别把上面那行改回字符串写法）
BOUND_CHARS_LEN = len(_BOUND_CHARS)


def _norm(text: str) -> str:
    """路径分隔符归一（Windows 上文档与脚本里两种写法都有 ⇒ 不归一就漏命中）。"""
    return text.replace("\\", "/")


def _boundary_ok(blob: str, pos: int, n: int) -> bool:
    """命中处前后**不得**再接会粘住名字的字符（= 边界匹配，但不用正则）。"""
    pre = blob[pos - 1] if pos > 0 else ""
    post = blob[pos + n] if pos + n < len(blob) else ""
    return pre not in _BOUND_CHARS and post not in _BOUND_CHARS


def _excluded(rel: str) -> str:
    for pre, why in EXCLUDE_PREFIXES:
        if rel.startswith(pre):
            return why
    return ""


def _rel(p: Path) -> str:
    return p.relative_to(REPO_ROOT).as_posix()


# --------------------------------------------------------------- 语料（一次读入）

class Lines:
    """一份语料的**行**视图 —— `(文本, 所属件, 行号)` 三条平行表。

    ⭐ 为什么要按"行"而不是按"文件"存：引用数要能**点名到行**（"谁在第几行提到它"），
    而"某件被引用了几处"这个数只有精确到行才不是印象。
    """

    def __init__(self) -> None:
        self.text: list[str] = []
        self.owner: list[str] = []
        self.lineno: list[int] = []
        self.lane: list[int] = []                 # 活机器侧：这一行属于第几路（文档/票侧恒 -1）
        self.files: dict[str, int] = {}           # rel → 行数（分母用）

    def add_file(self, p: Path, lane: int = -1) -> None:
        rel = _rel(p)
        n0 = len(self.text)
        for i, ln in enumerate(_norm(p.read_text(encoding="utf-8", errors="replace")).splitlines(), 1):
            self.text.append(ln)
            self.owner.append(rel)
            self.lineno.append(i)
            self.lane.append(lane)
        self.files[rel] = len(self.text) - n0

    def __len__(self) -> int:
        return len(self.text)


def build_live_corpus() -> tuple[Lines, list[tuple[str, int, int]]]:
    """① 机器侧语料 —— ⛔ 口径 = `LIVE_MACHINE_GLOBS`（不另抄）。
    → `(语料, 每路分组的 (标签, 文件数, 行数))`"""
    c = Lines()
    lanes: list[tuple[str, int, int]] = []
    for i, (glob, label, sufs) in enumerate(LIVE_MACHINE_GLOBS):
        n0f, n0l = len(c.files), len(c)
        for p in sorted(REPO_ROOT.glob(glob)):
            if p.is_file() and p.suffix in sufs and not _excluded(_rel(p)):
                c.add_file(p, lane=i)          # ⚠️ `lane=i` 漏了 ⇒ 逐路全 0 而总数不为 0
        lanes.append((label, len(c.files) - n0f, len(c) - n0l))
    return c, lanes


def build_doc_corpus() -> tuple[Lines, int]:
    """② 活文档侧语料 = `SCAN_GLOBS` **减** `LENIENT_GLOBS`（留痕区不算"口径引用"）
    **再减票目录**（票的引用**单列第三路** —— 同一件事算两遍，那个数就没意义了）。
    → `(语料, 被减掉的留痕件数)`"""
    lenient: set[str] = set()
    for g in LENIENT_GLOBS:
        lenient.update(_rel(p) for p in REPO_ROOT.glob(g) if p.is_file())
    c = Lines()
    for g in SCAN_GLOBS:
        for p in sorted(REPO_ROOT.glob(g)):
            if not p.is_file() or p.suffix not in DOC_SUFFIXES:
                continue
            rel = _rel(p)
            if rel in lenient or _excluded(rel) or rel.startswith(TICKET_PREFIX):
                continue
            c.add_file(p)
    return c, len(lenient)


def build_tickets() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """③ 票 —— ⛔ 销号判定与票目录都走 `audit_meta`（`TICKET_CLOSED` = 销号），不另抄。
    → `(未销号 [(票号, rel)], 已销号 [(票号, rel)])`

    ⚠️ **为什么连"已销号"一起返回**（`/code-review` 抓出的一处**方向性风险**）：
       票面口径是"**未销号**票"（这是对的：销号票的引用不构成"还有人要它"），
       但当天那起事故恰恰是「**票已销号、依据却悬空**」⇒ 只按未销号算**偏小**，
       而偏小会让人误判"没人要它"。⇒ 口径**不改**（按票面），
       **但把"只被已销号票引用"这件事单列一行报出来**（`_all_report` 末尾那行参考）。
    """
    out: list[tuple[str, str]] = []
    closed: list[tuple[str, str]] = []
    for p in sorted((REPO_ROOT / TICKET_DIR_REL).glob("*.md")):
        m = TICKET_NAME_RE.match(p.name)
        if not m:
            continue
        body = p.read_text(encoding="utf-8", errors="replace")
        st = TICKET_STATE_RE.search(body)
        # ⚠️ 状态读不到 ⇒ **按未销号算**（保守）并照样列出 —— 漏算比多算危险。
        if st and st.group(1) in TICKET_STATES and st.group(1) == TICKET_CLOSED:
            closed.append((m.group(1), _rel(p)))
            continue
        out.append((m.group(1), _rel(p)))
    return out, closed


# ------------------------------------------------------------------- 检索

class Blob:
    """把一份语料拼成**一个大字符串** ＋ 每行的起始偏移。

    ⭐ 为什么要拼：候选件上百个，逐行 `in` 是千万次 Python 循环；`str.find` 是 C 的
    整块扫描，**两个数量级**的差别。偏移表用来把命中位置换回「哪件哪行」。
    """

    def __init__(self, corpus: Lines) -> None:
        self.corpus = corpus
        self.text = "\n".join(corpus.text)
        self.starts: list[int] = []
        off = 0
        for ln in corpus.text:
            self.starts.append(off)
            off += len(ln) + 1

    def find(self, needle: str) -> list[int]:
        out: list[int] = []
        pos = self.text.find(needle)
        while pos >= 0:
            out.append(pos)
            pos = self.text.find(needle, pos + 1)
        return out

    def line_of(self, pos: int) -> int:
        return bisect.bisect_right(self.starts, pos) - 1


def find_refs(blob: Blob, target_rel: str, target_name: str,
              skip: frozenset[str] = frozenset()) -> list[tuple[int, str, int]]:
    """在语料里找这一件 —— → `[(lane, 所属件, 行号)]`（**全路径优先**，同一行只计一次）。

    ⚠️ **为什么要两个 needle**：文档里两种写法都有 —— 写全路径的（`ops/xxx.md`）与
    只写裸文件名的（`xxx.md`）。只认一种 ⇒ 引用数偏小 ⇒ **偏小比偏大危险**
    （偏小会让人以为"没人引用"）。
    """
    hits: dict[tuple[str, int], int] = {}
    for needle in (target_rel, target_name):
        for pos in blob.find(needle):
            if not _boundary_ok(blob.text, pos, len(needle)):
                continue
            i = blob.line_of(pos)
            rel = blob.corpus.owner[i]
            if rel in skip:
                continue
            hits.setdefault((rel, blob.corpus.lineno[i]), blob.corpus.lane[i])
    return [(lane, rel, no) for (rel, no), lane in sorted(hits.items(), key=lambda kv: kv[0])]


# ------------------------------------------------------------------- 分母与盘点

def iter_doc_files() -> list[str]:
    """仓内**文档件全集**（盘点对象）—— 根散件 ＋ `TOP_DIRS` 递归 **剪枝**
    （⛔ 不 `rglob`：那会走进虚拟环境，上万文件白扫一遍）。

    ⚠️ **根目录那两件也要收**（`README.md` · `AGENTS.md`）：`TOP_DIRS` 只管子目录，
    漏掉它们 ⇒ 最该被看见的两份入口件不在盘点表里。
    """
    out: list[str] = [p.name for p in sorted(REPO_ROOT.glob("*"))
                      if p.is_file() and p.suffix in DOC_SUFFIXES]
    stack = [REPO_ROOT / d for d in TOP_DIRS]
    while stack:
        try:
            entries = sorted(os.scandir(stack.pop()), key=lambda e: e.name)
        except OSError:
            continue
        for e in entries:
            rel = Path(e.path).as_posix()[len(str(REPO_ROOT).replace("\\", "/")) + 1:]
            if e.is_dir(follow_symlinks=False):
                if not _excluded(rel + "/"):
                    stack.append(Path(e.path))
            elif e.is_file(follow_symlinks=False) and Path(e.name).suffix in DOC_SUFFIXES:
                if not _excluded(rel):
                    out.append(rel)
    return sorted(out)


def _resolve(target: str, docs: list[str]) -> tuple[str, str, str]:
    """用户给的东西 → `(仓内相对路径, 裸文件名, 提示)`。

    ⚠️ 解析不出唯一的一件**照实说**，并退回"只按裸文件名找" —— ⛔ 不猜
    （猜错 ⇒ 报一个看着很确切的错数，比"匹配到多件"坏得多）。
    """
    t = _norm(target).strip().lstrip("./")
    if "/" in t:
        return t, t.rsplit("/", 1)[-1], ""
    hit = [d for d in docs if d.rsplit("/", 1)[-1] == t]
    if len(hit) == 1:
        return hit[0], t, ""
    if not hit:
        return "", t, "（仓内没有同名件 ⇒ 只按裸文件名找）"
    return "", t, "（同名 %d 件：%s ⇒ 只按裸文件名找 ⇒ 引用数会偏大）" % (
        len(hit), "、".join(h[:38] for h in hit[:4]))


def _head(live: Lines, lanes, doc: Lines, lenient_n: int,
          open_tickets, closed, tick: Lines) -> list[str]:
    """分母那一段 —— ⭐ **每个数都要带着分母出现**（2026-10-05 教训：先问「分母是什么」）。"""
    lane_txt = " ｜ ".join("%s %d 件/%d 行" % (lab, nf, nl) for lab, nf, nl in lanes)
    return [
        "refs · 引用盘点（**只读** · 本件不改任何文件）",
        "=" * 78,
        "分母（先看分母，再看数）",
        "  ① 活机器语料 %d 个文件 / %d 行" % (len(live.files), len(live)),
        "       %s" % lane_txt,
        "  ② 活文档语料 %d 件 / %d 行（`SCAN_GLOBS` 减留痕区 %d 件、再减票目录）"
        % (len(doc.files), len(doc), lenient_n),
        "  ③ 未销号票 %d 张（**已销号 %d 张另有一行参考**，见末尾）/ 票正文 %d 行"
        % (len(open_tickets), len(closed), len(tick)),
        "  ⛔ 已排除的目录（分母之外，各有理由）：" + " · ".join(
            "%s（%s）" % (pre.rstrip("/"), why) for pre, why in EXCLUDE_PREFIXES),
        "  ⚠️ **引用数是保守偏大的**：凡本仓任何文件（含**尺子与本工具自己**）里写了那个路径，"
        "就算一处 ⇒ 偏大安全（宁可多看一处），偏小会让人误判「没人要它」。",
        "",
    ]


def build_ticket_corpus(tickets: list[tuple[str, str]]) -> Lines:
    """③ 一批票的正文（逐行）—— ⚠️ **传哪一批由调用方决定**：未销号那批进第三路；
    已销号那批**只**作末尾那行"参考"（口径按票面，方向靠这一行补）。"""
    c = Lines()
    for _tid, rel in tickets:
        c.add_file(REPO_ROOT / rel)
    return c


# ------------------------------------------------------------------- 报告

def _one_report(rel: str, name: str, note: str, lb: Blob, db: Blob, tb: Blob,
                tid_of: dict[str, str]) -> list[str]:
    skip = frozenset({rel}) if rel else frozenset()
    live_hits = find_refs(lb, rel, name, skip)
    doc_hits = find_refs(db, rel, name, skip)
    tick_hits = find_refs(tb, rel, name, skip)
    L = ["目标件：%s" % (rel or "（未解析出唯一件）"), "裸文件名：%s" % name]
    if note:
        L.append("提示：%s" % note)
    L.append("")
    per: dict[int, list[tuple[str, int]]] = {}
    for lane, o, n in live_hits:
        per.setdefault(lane, []).append((o, n))
    L.append("① 机器引用：%d 处（逐路 —— **六路都在，别只看总数**）" % len(live_hits))
    for i, (_glob, label, _sufs) in enumerate(LIVE_MACHINE_GLOBS):
        hits = per.get(i, [])
        tail = "" if not hits else "   " + " · ".join("%s:%d" % (o, n) for o, n in hits[:4])
        L.append("     %-30s %2d 处%s" % (label, len(hits), tail))
    L.append("② 活文档口径引用：%d 处%s" % (
        len(doc_hits), "" if not doc_hits else "   " + " · ".join(
            "%s:%d" % (o, n) for _lane, o, n in doc_hits[:6])))
    L.append("③ 未销号票引用：%d 处%s" % (
        len(tick_hits), "" if not tick_hits else "   " + " · ".join(
            "%s(%s:%d)" % (tid_of.get(o, "?"), o.rsplit("/", 1)[-1], n) for _lane, o, n in tick_hits[:6])))
    L.append("")
    if not (live_hits or doc_hits or tick_hits):
        L.append("三路全 0 —— ⚠️ **这只是信号，不是「可以删」的结论**（下面那三问仍然要答）")
    L.append("⚠️ 删 / 搬任何一件之前必答三问（口径 = `docs/guides/document-governance.md` §三）："
             "① 结论落到哪里去了（说出文件名）② 还有谁引用它（三路都要报）"
             "③ 仓外归档索引登记了吗")
    return L


def _all_report(docs: list[str], lb: Blob, db: Blob, tb: Blob, cb: Blob) -> list[str]:
    keep: list[tuple[int, int, int, int, str]] = []
    zeros: list[str] = []
    only_closed: list[str] = []
    for rel in docs:
        name = rel.rsplit("/", 1)[-1]
        skip = frozenset({rel})
        a = len(find_refs(lb, rel, name, skip))
        b = len(find_refs(db, rel, name, skip))
        c = len(find_refs(tb, rel, name, skip))
        if a or b or c:
            keep.append((a + b + c, a, b, c, rel))
        else:
            zeros.append(rel)
            if find_refs(cb, rel, name, skip):
                only_closed.append(rel)
    keep.sort(key=lambda x: (-x[0], x[4]))
    zeros.sort()
    L = ["⛔ 不动的 N 件（三路里任一路 > 0 ⇒ 删 / 搬之前先看这里）—— **这份表就是覆盖面自检**",
         "-" * 78]
    for _tot, a, b, c, rel in keep:
        L.append("  %-56s 机器 %2d · 文档 %2d · 票 %2d" % (rel, a, b, c))
    L.append("")
    L.append("不动的 %d 件 ＋ 各自引用数（上表）｜ 文档件共 %d 件 ｜ 三路全 0 的 %d 件（**候选**）"
             % (len(keep), len(docs), len(zeros)))
    L.append("⚠️ 参考：**只被已销号票引用**的 %d 件（⛔ 不计入上面的判定）—— 销号票的引用不构成"
             "「还有人要它」，但 2026-10-05 那起事故正是「票已销号、依据却悬空」⇒ 这一行是给你"
             "看这个方向的：%s"
             % (len(only_closed), "、".join(only_closed[:6]) if only_closed else "（无）"))
    if zeros:
        L.append("")
        L.append("三路全 0 的件（**候选 ≠ 可删** —— 2026-10-05 实测：机器引用 0 的母本被四张票当唯一依据）")
        L.append("-" * 78)
        for rel in zeros:
            L.append("  %s" % rel)
    return L


def collect(target: str | None) -> str:
    """盘点一份**完整报告**（纯读；⛔ 不打印时间戳/耗时 —— 那会让自测的"两遍字节相同"永远失败）。"""
    live, lanes = build_live_corpus()
    doc, lenient_n = build_doc_corpus()
    open_tickets, closed = build_tickets()
    tick = build_ticket_corpus(open_tickets)
    lb, db, tb = Blob(live), Blob(doc), Blob(tick)
    cb = Blob(build_ticket_corpus(closed))          # 已销号票：只作"参考"那一行
    tid_of = {rel: tid for tid, rel in open_tickets}
    docs = iter_doc_files()
    out = _head(live, lanes, doc, lenient_n, open_tickets, closed, tick)
    out += (_all_report(docs, lb, db, tb, cb) if target is None
            else _one_report(*_resolve(target, docs), lb, db, tb, tid_of))
    out.append("")
    return "\n".join(out)


# ------------------------------------------------------------------- 自测

def _fingerprint() -> tuple:
    """扫描面（活机器 ＋ 活文档 ＋ 未销号票）的 `(相对路径, 字节数, **内容哈希**)`。

    ⭐⭐ **为什么必须用内容哈希、不能用 mtime**（`/code-review` 当场抓出来的）：
       票面验收写的是「**字节级** no-op」—— 而 `(大小, mtime)` **证明不了内容没变**：
       ① 同大小不同内容它照样绿；② 单纯 touch 一下它会假红。
       ⇒ 只认内容哈希这一种凭据。
    """
    live, _ = build_live_corpus()
    doc, _n = build_doc_corpus()
    tick, _closed = build_tickets()
    fps = []
    for rel in sorted(set(live.files) | set(doc.files) | {r for _t, r in tick}):
        raw = (REPO_ROOT / rel).read_bytes()
        fps.append((rel, len(raw), hashlib.md5(raw).hexdigest()))
    return tuple(fps)


def _receipt(text: str) -> list[str]:
    """**第二遍回执要贴的那几行**（票面第 2 批验收 2 的凭据）：
    分母三行 ＋ **不动件逐件表**（含各自引用数）＋ 汇总行。

    ⚠️ `/code-review` 抓到的缺陷：首版只回执了**汇总行**，而汇总行里写着"（上表）"
    ⇒ **那张表根本没打出来** ⇒ 验收要的「不动的 N 件 ＋ 各自引用数」其实**没给全**。
    """
    lines = text.splitlines()
    out = [ln for ln in lines
           if ln.startswith(("  ① 活机器", "  ② 活文档", "  ③ 未销号票"))]
    try:
        i = next(k for k, ln in enumerate(lines) if ln.startswith("⛔ 不动的"))
        j = next(k for k, ln in enumerate(lines) if ln.startswith("⚠️ 参考："))
    except StopIteration:                      # 单件模式没有那张表 ⇒ 只给分母
        return out
    return out + lines[i:j + 1]


def selftest() -> int:
    """**连跑两遍，断言第二遍字节级 no-op** —— 治「只读命令其实在改东西 / 不确定」。

    ⚠️ 三个断言缺一不可：
      ① 两遍输出**逐字节相同**（⇒ 报告里没有时间戳、耗时这类每次都变的字）
      ② 扫描面文件的 `(大小, mtime)` 前后一致（⇒ 真没写任何文件）
      ③ 分母三路都 > 0（⇒ 语料非空，"全 0"不是因为扫空集 —— `T18`/`T23` 那族假绿）
    """
    ok = 0
    fp0 = _fingerprint()
    first = collect(None)
    fp1 = _fingerprint()
    same_fp_1 = fp0 == fp1
    print("  %s 第 ① 遍：扫描面 %d 个文件，前后**内容指纹**%s"
          % ("✅" if same_fp_1 else "⛔", len(fp0), "一致" if same_fp_1 else "**变了**（本件在写东西！）"))
    ok += bool(same_fp_1)

    second = collect(None)
    fp2 = _fingerprint()
    same_out = first.encode("utf-8") == second.encode("utf-8")
    same_fp_2 = fp1 == fp2
    print("  %s 第 ② 遍：输出与第 ① 遍%s（%d 字节）"
          % ("✅" if same_out else "⛔", "逐字节相同" if same_out else "**不同**",
             len(second.encode("utf-8"))))
    print("  %s 第 ② 遍：扫描面**内容指纹**%s（大小 ＋ md5 ⇒ 真的是字节级 no-op）"
          % ("✅" if same_fp_2 else "⛔", "一致" if same_fp_2 else "**变了**"))
    ok += int(same_out) + int(same_fp_2)

    live, lanes = build_live_corpus()
    doc, _n = build_doc_corpus()
    open_tickets, _c = build_tickets()
    non_empty = len(live) > 0 and len(doc) > 0 and len(open_tickets) > 0
    print("  %s 三路语料非空（活机器 %d 行 · 活文档 %d 行 · 未销号票 %d 张）"
          % ("✅" if non_empty else "⛔", len(live), len(doc), len(open_tickets)))
    ok += bool(non_empty)

    bound_ok = BOUND_CHARS_LEN == 64 + (0x9FFF - 0x4E00 + 1)
    print("  %s 名字边界集合完整（%d 个字符 ＝ ASCII 64 ＋ 中文 %d）"
          % ("✅" if bound_ok else "⛔", BOUND_CHARS_LEN, 0x9FFF - 0x4E00 + 1))
    ok += bool(bound_ok)

    # ⭐⭐ 2026-10-05 当场抓到：**首版自测只跑全量分支** ⇒ 单件分支里一个解包 bug
    #   （三元组当二元组解）**全绿通过**。教训：**自测没覆盖到的分支 = 没有守卫的分支**。
    #   ⛔ 探针用英文件名 —— 中文件名当 argv 传会被 PowerShell 吃掉（当天栽过）。
    probe = "AGENTS.md"
    one = collect(probe)
    one_ok = all(s in one for s in ("目标件：", "① 机器引用", "② 活文档口径引用", "③ 未销号票引用"))
    print("  %s 单件分支也跑得通（探针 `%s` · 三路小标题齐全）" % ("✅" if one_ok else "⛔", probe))
    ok += bool(one_ok)

    # ⭐⭐ 2026-10-05 当场抓到第二个：首版 `build_live_corpus` **漏了 `lane=i`**
    #   ⇒ 输出的「① 机器引用 2 处」而**逐路全 0**（总数不减、逐路不减，两边对不上）。
    #   ⚠️ 这类 bug **只有"总数 == 逐路之和、且 lane 落在合法范围"这条断言能抓** ——
    #   眼睛看输出只会觉得"逐路都是 0，挺好"。⇒ 做成常设断言。
    live_c, lane_rows = build_live_corpus()
    lblob = Blob(live_c)
    probe2 = "tools/audit/audit_common.py"          # ⛔ 挑一个**保证有机器命中**的探针
    rel2, name2, _note2 = _resolve(probe2, iter_doc_files())
    hs = find_refs(lblob, rel2, name2, frozenset({rel2}) if rel2 else frozenset())
    by_lane: dict[int, int] = {}
    for lane, _o, _n in hs:
        by_lane[lane] = by_lane.get(lane, 0) + 1
    lane_ok = (bool(hs) and sum(by_lane.values()) == len(hs)
               and all(0 <= k < len(LIVE_MACHINE_GLOBS) for k in by_lane))
    print("  %s 机器引用**总数 == 逐路之和**（探针 `%s` · %d 处 · 落在 %s 路）"
          % ("✅" if lane_ok else "⛔", probe2.rsplit("/", 1)[-1], len(hs),
             ("第 " + "·".join(str(k) for k in sorted(by_lane)) + " 路")
             if by_lane else "（无）"))
    ok += bool(lane_ok)

    # ⭐ 票面 Testing Decisions「缝 B」要的是「**六路活机器口径齐全**」——
    #   `/code-review` 指出首版只断言了"命中落在合法 lane 区间"，**没断言每一路都有文件**
    #   ⇒ 那正是"空扫"（`T18`/`T23` 半边② 在报的同一族病）能从自测这边溜过去的原因。
    empty_lanes = [lab for lab, nf, _nl in lane_rows if nf == 0]
    six_ok = not empty_lanes
    print("  %s 活机器**六路逐路都有文件**（%d 路 · 空的路：%s）"
          % ("✅" if six_ok else "⛔", len(lane_rows),
             "、".join(empty_lanes) if empty_lanes else "无"))
    ok += bool(six_ok)

    print()
    print("  自测 %d/8" % ok)
    print("  —— 第二遍回执（票面第 2 批验收 2 的凭据：**不动的 N 件 ＋ 各自引用数**）")
    for line in _receipt(second):
        print("  " + line)
    return 0 if ok == 8 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="refs：某件还有谁在引用（三路计数 · 只读）")
    ap.add_argument("target", nargs="?", default=None, help="件名或路径片段（中文请写进脚本、别靠 argv）")
    ap.add_argument("--all", action="store_true", help="全量盘点：自报「不动的 N 件 ＋ 各自引用数」")
    ap.add_argument("--selftest", action="store_true", help="连跑两遍 ＋ 断言第二遍字节级 no-op")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.selftest:
        print("refs · 自测（只读）")
        print("=" * 78)
        return selftest()
    if a.target is None and not a.all:
        ap.print_usage()
        print("\n给一件（件名 / 路径片段），或用 `--all` 做全量盘点，或 `--selftest` 跑自测。")
        return 2
    print(collect(None if a.all or a.target is None else a.target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
