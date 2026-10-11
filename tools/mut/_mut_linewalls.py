"""`T21`（文档「字墙」· 单行 >800 字）**反向灵敏度** —— 证明这条判据真有牙。

背景（为什么非做不可）：
- `T21` 2026-10-04 立（`TAIL-224` · 文档重构方案 §六-4 甲案 · 用户裁定「④按推荐」）。
  它治的是「**行数在预算内、单行上万字**」那一类 —— `T10`（读预算）/`T13`（行数）**都看不见**。
- ⚠️ 它带一道**老账基线**（`audit_meta.LINE_WALL_BASELINE` · **只许变短**）⇒ 判据有**三种**报法
  ⇒ 三种都得证明"改坏了它真会报"，否则那半是**没牙的**（本仓：判据存在 ≠ 被看见）：
    ① 新出现的字墙件（没在基线里）② 超基线（**又长回来了**）③ 低于基线（基线该下调 ⇒ 防"闸越来越松"）。
- ⚠️ 它是个**黄档** ⇒ 判据必须写成 `needle`（同一行里同时出现的串），⛔ 拿"必须修变红"判会得到
  "永远没命中"（同 `_mut_docaudit.py` 的 `M7`/`M8`/`M15`）。
- ⚠️ 必须给 `doc_audit` 带 **`-v`** —— 默认只把黄档**按件聚合成「N 条 <路径>」** ⇒ 判据串在输出里
  **根本看不见**（`_mut_docaudit.py` 2026-09-24 踩过：黄档判据"永远不命中" = 假绿）。

做法：逐条把场景**造出来** ⇒ 确认 `doc_audit -v` **报出来了** ⇒ 逐字节复原（MD5 校验）。

⚠️ 靶**动态取**（从 `audit_meta.LINE_WALL_BASELINE` 现读，⛔ 不把各件的基线条数写死在这里）——
   否则"下沉几行字墙 ⇒ 基线该下调"这件事一发生，本件就**静默失效**（本仓的老课：写死的锚点必烂）。

⚠️⚠️ **2026-10-06（`TAIL-233`）修：案例② 原来把"基线输出里没有『又长回来了』"当前置，
   而那条前置在 2026-10-06 就已经不成立了** —— 主文档的字墙**真的涨到了 90 行**（基线登记 88）
   ⇒ `T21` **诚实报黄**（`字墙又长回来了：90 行`）⇒ 异件一进门就自我否决（`基线的输出里已经有…`）
   ⇒ 案例②**从没被验过**。⚠️ 这不是"判据坏了"，是**判据把自己的前置条件写成了基线的绝对状态**
   ⇒ 主文档一正常地长行，它就哑。⇒ 改法（`_mut_uicheck` 那次是同族：**靶打偏**）：
   **判据改成相对的** —— 记下基线里那条**数**，塞一行之后断言**恰好 +1**（而不是断言"报法原本不存在"）
   ⇒ 基线有没有那一条、有几条，都不影响它有牙。⭐ 另外三条（①③④）是**特有报法**（含"新出现"/
   "基线过期"/"不在扫描面内"这类**只可能由本次变异造出**的措辞）⇒ 仍保留"基线里不得已有"的前置。
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
META = ROOT / "tools" / "audit" / "audit_meta.py"
PLAN = ROOT / ".codebuddy" / "plans" / "开发计划-主文档.md"
#: 靶件①：一件**当前没有字墙**的活文档（`ops/README.md` ∈ `SCAN_GLOBS` 且不在基线里）
CLEAN_DOC = ROOT / "ops" / "README.md"

sys.path.insert(0, str(ROOT / "tools" / "audit"))
from audit_meta import LINE_WALL_BASELINE, LINE_WALL_CHARS   # noqa: E402

#: 造一条超线长行（比阈值多 100 字 ⇒ 稳稳越线）
LONG = "字" * (LINE_WALL_CHARS + 100)


def _fit(frag: bytes, sample: bytes) -> bytes:
    """按目标文件的行尾风格给 frag 换行（`.md` 可能是 CRLF；⛔ 别静默写成 LF ⇒ MD5 假 BAD）。"""
    if b"\r\n" in sample:
        return frag.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return frag.replace(b"\r\n", b"\n")


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_doc_audit() -> str:
    """跑 `doc_audit -v`，全量输出（⚠️ 不看退出码 —— rc 还含黄档，两回事）。"""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([str(PY), str(ROOT / "tools" / "audit" / "doc_audit.py"), "-v"],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    return (r.stdout or "") + (r.stderr or "")


def _needle_hit(needle: tuple[str, ...], out: str) -> bool:
    """判据 = **同一行里**必须同时出现这几个串（黄档一律写元组 —— 单串会撞上别的命中）。"""
    return any(all(x in ln for x in needle) for ln in out.splitlines())


#: 「又长回来了」后面那个数 —— ⛔ 宽松匹配（`：**` 与 `：90` 之间只隔 0~10 个非数字字符）
_COUNT_RE = re.compile(r"又长回来了[^\d]{0,10}(\d+)")


def _wall_count(out: str, name: str) -> int | None:
    """`doc_audit -v` 输出里，某件「字墙**又长回来了**」报的**那个数**（取不到 ⇒ `None`）。

    ⭐ 2026-10-06（`TAIL-233`）新增：案例② 因此从"绝对存在性"改成"**相对递增**"——
    基线里有没有那一条、有几条，都**不影响它有牙**。
    """
    for ln in out.splitlines():
        if "[T21]" in ln and "又长回来了" in ln and name in ln:
            m = _COUNT_RE.search(ln)
            if m:
                return int(m.group(1))
    return None


def _append_long(src: bytes) -> bytes:
    """在文件末尾追加"一个空行 ＋ 一条超线长行"（按目标文件的行尾风格）。"""
    return src + _fit(b"\n\n" + LONG.encode() + b"\n", src)


def _make_cases() -> list[dict]:
    """⭐ 动态取靶（见文件头「靶动态取」的说明）。"""
    rel0, n0 = LINE_WALL_BASELINE[0]                       #: 头一件（主计划；⚠️ 别把它的条数写死在这儿）
    return [
        # ① 一件**没在基线里**的活文档长出字墙 ⇒ 必须报「新出现的「字墙」件」
        {"desc": f"新出现的字墙件（往 `{CLEAN_DOC.name}` 塞一行 {len(LONG)} 字）", "mode": "needle",
         "needle": ("[T21]", "ops/README.md", "新出现的「字墙」件"),
         "path": CLEAN_DOC, "frag": _append_long},
        # ② 基线件**又长回来了**（超基线）⇒ 必须报「又长回来了」⭐ **相对判据**（见文件头 2026-10-06）
        {"desc": f"字墙又长回来（往基线件 `{Path(rel0).name}` 塞一行 {len(LONG)} 字）", "mode": "count",
         "count_name": Path(rel0).name,
         "path": PLAN, "frag": _append_long},
        # ③ 基线**该下调了**（把基线件的数上调 ⇒ 实际 < 基线）⇒ 必须报「基线过期」
        {"desc": "基线过期（把基线件的数上调 100 ⇒ 实际低于基线）", "mode": "needle",
         "needle": ("[T21]", "基线**过期**", Path(rel0).name),
         "path": META,
         "old_new": ((f'("{rel0}", {n0})').encode(), (f'("{rel0}", {n0 + 100})').encode())},
        # ④ 基线里的件**已不在活文档扫描面内**（改名成一件不存在的）⇒ 必须报「不在活文档扫描面内」
        {"desc": "基线里的件成了幽灵（把条目改名成不存在的件）", "mode": "needle",
         "needle": ("[T21]", "不在活文档扫描面内"),
         "path": META,
         "old_new": ((f'("{rel0}", {n0})').encode(),
                     (f'("ops/_mut_linewalls_ghost.md", {n0})').encode())},
    ]


def main() -> int:
    cases = _make_cases()
    before = {c["path"]: c["path"].read_bytes() for c in cases}
    base_out = run_doc_audit()
    for c in cases:
        if c["mode"] == "count":
            # ② 相对判据：记下基线里那个「数」（没有就当 0 ⇒ 塞一行后必须是 1）
            c["base_n"] = sum(len(line) > LINE_WALL_CHARS for line in c["path"].read_text(encoding="utf-8").splitlines())
        elif _needle_hit(c["needle"], base_out):
            print(f"  ⛔ 基线的输出里**已经**有「{c['needle']}」⇒ 本件这条判据无效，先重定靶")
            return 1

    hit = 0
    for c in cases:
        p: Path = c["path"]
        src = p.read_bytes()
        try:
            if "frag" in c:
                p.write_bytes(_fit(c["frag"](src), src))
            else:
                old, new = c["old_new"]
                old, new = _fit(old, src), _fit(new, src)
                n = src.count(old)
                assert n == 1, f"锚点命中 {n} 次（期望 1）⇒ **未验证**（靶件改写法了 ⇒ 需重定靶）"
                p.write_bytes(src.replace(old, new, 1))
            out = run_doc_audit()
        finally:
            p.write_bytes(src)
        if c["mode"] == "count":
            got = _wall_count(out, c["count_name"])
            ok = got == c["base_n"] + 1
            tail = f"  （报的数 {c['base_n']} → {got}，期望 {c['base_n'] + 1}）"
        else:
            ok = _needle_hit(c["needle"], out)
            tail = ""
        print(("  ✅ " if ok else "  ⛔ 未命中 ") + c["desc"] + tail)
        hit += bool(ok)

    print()
    dirty = [p for p, b in before.items() if md5(p) != hashlib.md5(b).hexdigest()]
    print(f"  命中 {hit}/{len(cases)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 全部复原' if not dirty else '❌ 未复原：' + '、'.join(map(str, dirty))}")
    return 0 if (hit == len(cases) and not dirty) else 1


if __name__ == "__main__":
    sys.exit(main())
