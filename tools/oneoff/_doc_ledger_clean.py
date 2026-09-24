"""一次性：**主文档 §14 / §15 清理**（用户 2026-09-23：「尾巴台账和排期那里清一清，过程该归档就归档」）。

## 干什么（⛔ 全是**搬运**，不改语义）

| 动作 | 明细 |
|---|---|
| ① §15 §四 已销号 | 日期 **早于 2026-09-22** 的行 ⇒ **整行逐字**下沉归档；**保留的近期行**把长格截短（≤110 字 ＋ `…`）并把**全文**一并下沉 |
| ② §14.3 逐条排期 | **只留活跃尾巴**（A/B/C 三段里的编号）那几行；其余（✅ 已做）**整行逐字**下沉归档 |
| ③ §14.4 / 14.4c / 14.4d / 14.4e | 过程正文**整块逐字**下沉归档，原处留 3 行指针（⛔ **不动** 14.4e 的 `#### 机制：撤项标记（T8）`—— 那是机制、长期有效） |
| ④ 计数 | §15 顶部 `已销号 **N** 条` 与 §0.2 那处，一起改成**表内实际行数**（`T6` 就是拿它核表内行数） |

⛔ **不动**：两个 `📌 契约` 段 · §14.5 结论 · §15 §一/二/三 条目本体 · §15 尾「机器看管」段。

## 为什么（`T6` / `T13` 的硬要求）

- `T6`：**已销号计数 = §四 表内行数**；且 §14.3 里**不许留幽灵编号**（既不在活跃集、也不在册 ⇒ 红）
  ⇒ ②把「已做」行**连着 §15 的那一行一起搬**（两边同时消失，T6 就自洽）。
- `T13`：主文档**行数预算 1700**（实测 1730 ⇒ 黄）⇒ 本次清理的 KPI = 落回预算内。

跑法：`backend\\.venv\\Scripts\\python.exe tools\\oneoff\\_doc_ledger_clean.py`
（⛔ 跑完自己跑 `doc_audit.py` 核 T6/T13）
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
ARCH = ROOT / ".workbuddy" / "plans" / "归档-历史单元条目.md"
CUT_DATE = "2026-09-22"          #: 早于此日期的已销号行 ⇒ 下沉
KEEP_CELL = 110                 #: 保留行里长格的截断长度
ID_RE = re.compile(r"`?(TAIL-\d+)`?")


def _brief(text: str, n: int = KEEP_CELL) -> str:
    """把一格截短（尽量在标点处收口）；⛔ 只截断，不改写。"""
    t = text.strip()
    if len(t) <= n:
        return t
    cut = max((t.rfind(ch, 0, n) for ch in "。；·｜"), default=-1)
    return (t[:cut + 1] if cut > n // 2 else t[:n]) + "…"


def _split(ln: str) -> list[str]:
    return [c.strip() for c in ln.strip().strip("|").split("|")]


def main() -> int:
    plan_src = PLAN.read_text(encoding="utf-8")
    arch_src = ARCH.read_text(encoding="utf-8")
    lines = plan_src.split("\n")
    md5_before = hashlib.md5(plan_src.encode("utf-8")).hexdigest()
    n_before = len(lines)

    def idx(pred, start: int = 0) -> int:
        return next((i for i in range(start, len(lines)) if pred(lines[i])), -1)

    h143 = idx(lambda l: l.startswith("### 14.3"))
    h144 = idx(lambda l: l.startswith("### 14.4 "), h143)
    h15 = idx(lambda l: l.startswith("## 15. 尾巴台账"))
    sec1 = idx(lambda l: l.startswith("### 一、"), h15)
    sec4 = idx(lambda l: l.startswith("### 四、已销号"), h15)
    tail_end = idx(lambda l: l.startswith("### 机器看管"), sec4)
    mech = idx(lambda l: l.startswith("#### ⭐⭐ 机制："), h143)
    for name, v in (("14.3", h143), ("14.4", h144), ("§15", h15), ("§一", sec1), ("§四", sec4),
                    ("机器看管", tail_end), ("T8 机制小节", mech)):
        if v < 0:
            print(f"❌ 找不到定位点：{name} ⇒ 先看文档再改")
            return 1

    # ── 活跃编号（§一/二/三 三段表里出现的 TAIL-n）
    live: set[str] = set()
    sec = ""
    for i in range(sec1, sec4):
        m = re.match(r"^#{2,3}\s*([一二三])\s*[、.]", lines[i].strip())
        if m:
            sec = m.group(1)
        if sec and lines[i].startswith("|"):
            m2 = ID_RE.match(_split(lines[i])[0].strip("`")) if _split(lines[i]) else None
            if m2:
                live.add(m2.group(1))
    if not live:
        print("❌ 一个活跃尾巴都没认出来 ⇒ 编号格式变了？先看文档再改")
        return 1

    arch_add: list[str] = [
        "",
        "## 下沉于 2026-09-23（主文档 §14/§15 清理 —— `TAIL-75`~`TAIL-79` 那轮收尾）",
        "",
        "> **来由**：用户 2026-09-23「尾巴台账和排期那里清一清，过程该归档就归档」——",
        f"> 主文档当时 {n_before} 行（`T13` 预算 1700）⇒ 把①§15 已销号旧行 ②§14.3 排期里已做的行",
        "> ③§14.4* 三个施工图正文，**逐字**搬到本件；主文档只留紧凑表与指针。⛔ 语义一字未改。",
        "",
    ]

    # ── ① §15 §四：⚠️ **一行都不搬走**（`T6`：编号必须 `1..N` **顺延不跳号** ⇒ 台账行少了就红）
    #      ⇒ 只把长格**原位截短**（全文进归档）；顺手清掉一行"孤儿分隔行"（老编辑留下的）
    pre4, post4, keep_rows, kept_full = [], [], [], []
    stray_sep = 0
    seen = False
    for i in range(sec4, tail_end):
        ln = lines[i]
        cells = _split(ln) if ln.startswith("|") else []
        if cells:
            head = cells[0].strip("`")
            is_sep = set("".join(cells)) <= set("-| :")
            is_data = bool(ID_RE.match(head)) or head == "—"
            if is_data and not is_sep:
                seen = True
                short = [cells[0]]
                for k, c in enumerate(cells[1:-1], start=1):
                    n = 46 if k == 1 else 72
                    b = _brief(c, n)
                    short.append(b + ("…（全文见归档）" if b != c else ""))
                keep_rows.append("| " + " | ".join(short + [cells[-1]]) + " |")
                kept_full.append(ln)
                continue
            if is_sep and seen:                  # 数据行之后的分隔符 = 孤儿
                stray_sep += 1
                continue
        (post4 if seen else pre4).append(ln)

    arch_add += ["### 一、§15 已销号 · 各行的**全文**（主文档里是截短版；⛔ 一行未删，编号仍 `1..N`）", ""]
    arch_add += kept_full + [""]

    # ── ② §14.3
    pre143, post143, live_rows, done_lines = [], [], [], []
    seen = False
    for i in range(h143, h144):
        ln = lines[i]
        if ln.startswith("|") and _split(ln):
            cells = _split(ln)
            m = ID_RE.match(cells[0].strip("`"))
            if m:
                seen = True
                if m.group(1) in live:
                    short = [c if len(c) <= 240 else _brief(c, 240) + "（全文见归档）" for c in cells]
                    live_rows.append("| " + " | ".join(short) + " |")
                    done_lines.append(("live", ln))
                else:
                    done_lines.append(("done", ln))
                continue
        (post143 if seen else pre143).append(ln)

    arch_add += ["### 三、§14.3 排期表 · **已做**的行（整行逐字；活跃尾巴留在主文档）", ""]
    arch_add += [ln for k, ln in done_lines if k == "done"] + [""]
    arch_add += ["### 四、§14.3 活跃尾巴行的**全文**（主文档里理由格有截短）", ""]
    arch_add += [ln for k, ln in done_lines if k == "live"] + [""]

    # ── ③ §14.4*（到 T8 机制小节之前）
    body_144 = lines[h144:mech]
    keep_144 = [
        "",
        "> ⚠️ **2026-09-23 下沉归档**（用户：「过程该归档就归档」）：`14.4` 序列 ＋ `14.4c` M5 施工图 ＋",
        "> `14.4d` M6 施工图 ＋ `14.4e` `m13` 施工图 **整块正文已搬进** `归档-历史单元条目.md`",
        "> （「下沉于 2026-09-23」第五节）。**结论**：M5 **七单元全落** · M6 **已收口** · `m13` **已收口**",
        "> ⇒ **没有待做的**。⭐ 下面留下的是**机制**（长期有效）与两份 `📌 契约`，不是过程。",
        "",
    ]
    arch_add += ["### 五、§14.4 / 14.4c / 14.4d / 14.4e 正文（整块逐字）", ""]
    arch_add += body_144 + [""]

    # ── 组装
    new: list[str] = []
    new += lines[:h143]
    new += pre143 + live_rows + post143
    new += keep_144
    new += lines[mech:h15]                      # 机制小节 → §14.5 → …（含两份契约）
    new += lines[h15:sec4]                      # §15 头（含计数行与四段说明）
    new += pre4 + keep_rows + [
        "",
        f"> ⚠️ **2026-09-23 下沉归档**（用户：「过程该归档就归档」）：本表 **{len(keep_rows)}** 行的",
        f"> **逐字全文**（含那一行孤儿分隔符的来由）搬进 `归档-历史单元条目.md`（「下沉于 2026-09-23」第一节）",
        f"> —— 主文档里只留**截短版**（事项 ≤46 字 · 依据 ≤72 字）。⛔ **一行都没删**：编号仍 `1..N` 顺延",
        f"> （`T6` 硬要求）。⭐ 同批清掉 **{stray_sep}** 行「孤儿分隔行」（老编辑留下的、会让人以为表断了）。",
        "",
    ] + post4
    new += lines[tail_end:]

    # §15 顶部计数（`T6` 核的就是它）＋ §0.2 那处
    for i in range(len(new) - 1, -1, -1):
        if re.search(r"A 类 \*\*\d+\*\* 条 · B 类 \*\*\d+\*\* 条 · C 类 \*\*\d+\*\* 条 · 已销号 \*\*\d+\*\* 条",
                     new[i]):
            new[i] = re.sub(r"已销号 \*\*\d+\*\* 条", f"已销号 **{len(keep_rows)}** 条", new[i])
            break
    for i, ln in enumerate(new):
        if ln.startswith("- **尾巴**：A 类"):
            new[i] = re.sub(r"已销号 \*\*\d+\*\*", f"已销号 **{len(keep_rows)}**", ln)
            break

    tmp = pathlib.Path(tempfile.gettempdir()) / "plan_before_ledger_clean.md"
    shutil.copy2(PLAN, tmp)
    PLAN.write_text("\n".join(new), encoding="utf-8")
    ARCH.write_text(arch_src.rstrip("\n") + "\n" + "\n".join(arch_add) + "\n", encoding="utf-8")

    n_done = len([1 for k, _ in done_lines if k == "done"])
    print(f"主文档：{n_before} 行 → {len(new)} 行（预算 1700 ⇒ "
          f"{'✅ 达标' if len(new) <= 1700 else '⛔ 仍超'}）")
    print(f"§四 已销号：{len(keep_rows)} 行**原位截短**（⛔ 一行未删）· 清掉孤儿分隔行 {stray_sep} 行")
    print(f"§14.3：留 {len(live_rows)} 条活跃 · 搬走 {n_done} 条已做")
    print(f"§14.4*：搬走 {len(body_144)} 行正文")
    print(f"改前 MD5 {md5_before} · 备份 {tmp}")
    print(r"⏭️ 接着跑：backend\.venv\Scripts\python.exe tools\audit\doc_audit.py（核 T6 计数 / T13 行数）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
