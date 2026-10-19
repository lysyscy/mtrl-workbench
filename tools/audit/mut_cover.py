"""**变异覆盖台账生成器**（`TAIL-57` · 2026-09-21）。

## 它解决什么

本仓的判据有两层：① **判据本身**（全套 pytest — ⚠️ 条数**别写死**，会涨；＋ **13 把尺子**）；② **判据的反向灵敏度**
（变异脚本 `tools/**/_mut_*.py`：把实现**故意改坏** ⇒ 对应断言必须变红，否则是**假绿**）。
⚠️② 这一层**没有台账** ⇒ "哪些代码区被变异验过、哪些**从没验过**"没人答得上来 ——
   且已有实测教训：`_mut_boot` / `_mut_m03pay` 曾因 `pick()` 签名变化**静默崩掉**（**守卫自己烂了**）。
⇒ 本件把 ② 生成成一张台账（`var/state/verification/变异覆盖台账.md`），每条变异件列出：
   **守什么 / 改坏谁 / 用哪条判据验 / 怎么跑**；并列出**登记在案的"尚未有变异覆盖"的守卫**。

## 用法

    backend/.venv/Scripts/python.exe tools/audit/mut_cover.py            # 重新生成台账（覆盖写）
    backend/.venv/Scripts/python.exe tools/audit/mut_cover.py --check    # 只比对，变了 ⇒ rc=1（可挂闸门）

## 设计约束

- 递归查找现行变异，排除 `_归档-*` 子树；归档不是现行覆盖或可执行证明；
- 台账是**生成物**（`artifacts/`，⛔ 不手改）—— 手改会被下次生成覆盖；要改内容去改本件；
- ⛔ **只读源码**，本件不执行任何变异（跑变异请逐个跑对应脚本）。
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "var/state/verification" / "变异覆盖台账.md"

#: ⭐ **登记在案：还没有变异覆盖的守卫**（⛔ 手工维护 —— 加一条守卫时来这里登记，
#:    补了变异脚本就从这里删掉；**这条清单本身是台账的一半**，只生成"有 _mut 的"会漏掉这一半）。
#: 判"有没有"的方法：守卫文件名 / 守的代码区 是否出现在某个 `_mut_*.py` 的目标或说明里。
UNCOVERED: tuple[tuple[str, str, str], ...] = (
    # ⭐⭐ 2026-09-24：`doc_audit 的 T9/T11/T16` 那行**已整行删掉** —— `_mut_docaudit.py` 从 3 条扩到
    #   **14/14**（`M4`–`M8` = `T1`/`T2`/`T3`/`T5`/`T10` · `M9`–`M14` = **`T17`**/`T9`/`T11`/`T16`/**`T18`**/**`T19`**）
    #   ⇒ `doc_audit` 的**红档全都有反向灵敏度**了（黄档里的 `T12` 由 `_mut_t12.py` 管、其余为登记档）。
    #   ⚠️ 扩面过程**又抓到两个真问题**（留痕见 `journal/2026-09-24.md` ㉕）：
    #    ① `T17`（新立）的第一版判据是**子串** `"__main__" in src` ⇒ 把靶的入口整段截掉**它居然不报**
    #       —— 因为**件说明里也写着 `__main__` 这个词** ⇒ 改成**入口行正则**才有效；
    #    ② `T9` 的变异一开始改的是文件里**第一处** `[助手自定` —— 那是 §八 **引言块**里的词
    #       （讲规矩的文字），换成"整行锚点"才命中 ⇒ **变异没命中 ≠ 判据没牙**，先怀疑锚点。

    # ⭐⭐ 2026-10-10（用户裁定）：`cover_gap`（`T7a`/`T7b` 口径覆盖）**重新登记回表 B** ——
    #   原 `_mut_covergap.py` 已删除。它是**唯一一支拿产品资料当临时靶**的变异：往 `MOD-*.md`
    #   能力表追加一行再复原。产品资料 2026-10-10 迁入仓内后有两处新风险（改的是受版本管理的件；
    #   交付面尚未提交时复原失败没有第二份可回退）⇒ 用户裁定直接删掉，不改造。
    #   ⇒ 代价照实记：`T7a`/`T7b` **从此没有反向灵敏度**（判据本身仍在闸门里跑，见 `CMDS`）。
    ("cover_gap.py（T7a/T7b）", "能力行末列没写 `ACC-*` ⇒ 报『无判据承载』（T7a）· 口径 `§9.9.9` 无人 cover（T7b）",
     "⚠️ 2026-10-10 起无变异覆盖 —— 原自证以产品资料为临时靶，已按用户裁定删除",
     "要补的话：照 `tools/mut/_mut_docaudit.py` 的隔离手法（复制件/临时目录 + rc 断言），⛔ 别再直接改 `delivery/` 正文"),

    # ⭐⭐ 2026-09-24：`syntax_audit` / `cover_gap` 那两行**已整行删掉** —— 两把都补上了反向灵敏度
    #   （`_mut_syntax.py` **4/4** · `cover_gap` 当时 **2/2**；用户当天放行交付面变异：
    #    「云同步也没那么蠢，只要别同时大量连续改文件」）。⚠️ `cover_gap` 那支已于 2026-10-10 删除（见上）。
    #   ⚠️ 补的过程**各挖出一个真问题**，留痕见 `journal/2026-09-24.md` ㉔：
    #   ① `syntax_audit` **自带 `--selftest` 却没人跑**（休眠的自证 ⇒ 写了、能过、此后没人碰）；
    #   ② `cover_gap` **没有 `__main__`** ⇒ 独立跑是**空转**（0 行输出、rc 恒 0）—— **僵尸闸门第二例**
    #      （第一例 = `shell_verify`）⇒ 已补真出口（交付面找不到 / 登记册读不到 ⇒ `rc=1`）。
    # ⭐ 口径（2026-09-24 用户裁定 `A`）：`claim_audit` **已上真出口** —— 现在是**清零式闸门**（有黄 ⇒ rc=1），
    #   与 `shell_verify` 的**盖章式**（差异 ⇒ 红、`--snapshot` 盖章归零）并列 ⇒ ⛔ 两者都不是僵尸闸门。
    #   ⇒ `_mut_claim.py` 的判据已从"该行出现在清单里"**升级为 `rc=1`**（原"黄不判红"时期只能看清单）。
    # ⭐⭐ 2026-09-24（用户裁定 **A**）：`sticky_probe` 那行也**整行删掉** —— 它此前 `main()` 末尾是
    #   `os._exit(0)` ⇒ **`rc` 恒 0**，而它**每轮都在闸门清单里跑** ⇒ **同族第五例"僵尸闸门"**
    #   （前四例：`shell_verify` · `cover_gap` · `audit_drift` · `audit_meta`）。
    #   ⇒ 当天给它装了**窄判据**：只钉「**我们在用的那条 `E`** ＋ 两个备选 `D`/`C` 必须有效」，
    #   ⛔ **刻意不断言 `A` 必须失败**（那是"我们为什么没选它"的记录，浏览器哪天修好了我们不该红）
    #   ⇒ 自证 = `tools/mut/_mut_sticky.py` **2/2**（把 `E`/`D` 的 sticky 抹掉 ⇒ 必须 `rc=1`）。
    #   📌 至此 **表 B 为空**：`tools/audit/` 的每一把尺子都有反向灵敏度（或明确的"为什么没有"）。


)

#: ⚠️ **「找不到」里的误报登记** —— 这些路径**故意不在位**，⛔ 别去"修"它们：
#: 判据 = 脚本**自己创建**（临时探针件 / 副本）或**故意构造**（变异后的假目标名）。
#: ⭐ 2026-09-24 加（接手核验轮）：当时"找不到"共 6 条 —— 其中 **4 条是误报**、**2 条是真过期**
#:    （`tools/prg_form_audit.py` 搬迁后没跟改 · `mod04_plan/view.py` 已随旧页删除 ⇒ 那两件**整支失效**，已修）。
#:    ⇒ 不登记误报的话，这行告警常年挂着噪音，**真过期反而被淹没**。
IGNORED_REFS: tuple[str, ...] = (
    "backend/app/mod07_setl/extract_MISSING.py",   # `_mut_asset.py`：变异后的**假目标名**（专测 `asset_audit` 的落点真伪）
    "_t14_probe_tmp.py",                            # `_mut_t14t15.py`：脚本**自己 write_text** 的探针件
    "_t8_probe_tmp.py",                             # `T8` 反向灵敏度脚本：自建探针（造在 mod08_inv 下、finally 里删）
    "_u5_proto_copy.html",                          # `_mut_u5.py`：脚本**自己复制**的原型副本
    # ⭐ 2026-10-04（`TAIL-225` 票体系）：`_mut_docaudit.py` 的 `M19`/`M20` 靶是**票文件**（`.scratch/tails/issues/`）——
    #   ⚠️ 本件的 `_file_index()` 只索引 `.py/.js/.html`（**md 本来就不在里面**）⇒ 不登记就会常挂两条假"找不到"（噪音淹信号）。
    "TAIL-188-交付包与迁移.md",                      # M19：**真在**的票文件（只是不在 idx 的三种后缀里）
    "TAIL-9999-幽灵票.md",                           # M20：脚本**自己 create** 的幽灵票（用完删）
    # ⭐ 2026-10-06（`TAIL-239`）：`_mut_keycover.py`（选集机器眼）**故意造**两个不存在的件名 ——
    #   ① `_mut_tmp_unlisted_probe.py`：它**自己 write_text** 出来证明"缺口会被报红"，`finally` 里删；
    #   ② `_mut_tmp_never_existed_probe.py`：只作为**字符串**插进 `KEEP_OUT` 字典体（证明"陈旧会被报红"），
    #      从来不落盘。⇒ 不登记就会在台账里挂两条**永久假**「⚠️找不到」，而真过期的目标会被淹没
    #   （这正是 `IGNORED_REFS` 存在的理由）。
    "_mut_tmp_unlisted_probe.py",
    "_mut_tmp_never_existed_probe.py",
    # ⭐ 2026-10-06（`TAIL-241` 第 4 步）：`_mut_pytestscope.py` 同样**故意**往 `SELF_ONLY`
    #   里塞一个不存在的件名（证明「名单陈旧」那半边会报红，不是死代码）⇒ 不登记就会在台账里
    #   挂一条**永久假**「⚠️找不到」，而真过期的目标会被淹没（同上两支的道理）。
    "_mut_pytestscope_never_existed.py",
)


def _docstring_head(t: str, n: int = 130) -> str:
    """docstring 的**第一行**当「守什么」⇒ ⛔ 不抓整段（变异件的 docstring 常带 Markdown 表格，
    里面的 `|` 会把台账的表格撑破 —— 2026-09-21 首版就栽在这）。"""
    m = re.search(r'"""(.{0,600})', t, re.S)
    if not m:
        return "（无 docstring —— ⛔ 补一段「守什么」）"
    line = m.group(1).splitlines()[0] if m.group(1).splitlines() else ""
    line = line.replace("|", "／").strip()
    return line[:n] + ("…" if len(line) > n else "")


def _file_index() -> dict[str, list[str]]:
    """`文件名 → [相对路径]`（一次建好；裸文件名的目标靠它解析）。"""
    idx: dict[str, list[str]] = {}
    for base in ("backend/app", "backend/tests", "tools", ""):
        for p in (ROOT / base).glob("**/*") if base else ROOT.glob("*.html"):
            if p.is_file() and p.suffix in (".py", ".js", ".html") and not any(x.startswith("_归档") for x in p.parts):
                idx.setdefault(p.name, []).append(str(p.relative_to(ROOT)).replace("\\", "/"))
    return idx


def scan() -> list[dict]:
    idx = _file_index()
    rows: list[dict] = []
    for p in sorted(ROOT.glob("tools/**/_mut_*.py")):
        if any(x.startswith("_归档") for x in p.parts):
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        raw = sorted({x.replace("\\", "/") for x in
                      re.findall(r'["\']([\w\-\\/\.]+\.(?:py|html|js))["\']', t)
                      if not x.startswith("tests/")})
        exists: list[tuple[str, bool]] = []
        for x in raw:
            if "/" in x:
                ok = (ROOT / "backend" / x).exists() or (ROOT / x).exists()
            else:
                ok = x in idx                       # 裸文件名 ⇒ 全站按名找（⛔ 不是"必须带路径"）
            exists.append((x, ok))
        rows.append({
            "name": p.name,
            "rel": rel,
            "guards": _docstring_head(t),
            "targets": raw,
            "exists": exists,
            "tests": sorted(set(re.findall(r"(tests/[\w\.]+\.py)", t))),
        })
    return rows


def render(rows: list[dict]) -> str:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    L = [
        "# 变异覆盖台账（**生成物** · `tools/audit/mut_cover.py` 生成 ⛔ 不手改）",
        "",
        f"> 生成于 {now} · 变异件 **{len(rows)}** 个 · 判据线见计划 §0（本台账只管**反向灵敏度**这一层）。",
        "> ⭐ 读法：**表 A** = 已有的变异（改坏谁 ⇒ 哪条判据必须红）；**表 B** = 登记在案的**尚未覆盖**的守卫。",
        "> ⚠️ 已有实测教训：变异脚本会**静默烂掉**（`_mut_boot`/`_mut_m03pay` 因 `pick()` 签名变化崩过）",
        "> ⇒ **重构成批改了某模块后，把表 A 里涉及它的变异件重跑一遍**。",
        "",
        "## 表 A · 已有变异（按件）",
        "",
        "| 变异件 | 守什么 | 改坏谁（目标） | 验的判据 |",
        "|---|---|---|---|",
    ]
    for r in rows:
        tg = "、".join(f"`{x}`" + ("" if ok else "⚠️找不到") for x, ok in r["exists"]) or "（脚本内联）"
        ts = "、".join(f"`{x}`" for x in r["tests"]) or "（自验）"
        L.append(f"| `{r['rel']}` | {r['guards']} | {tg} | {ts} |")
    # ⚠️ 排除 `IGNORED_REFS`（脚本自建 / 故意构造的路径）—— 只报**真过期**，别让噪音淹掉信号。
    missing = [f"`{r['rel']}` 里引用的 `{x}`" for r in rows for x, ok in r["exists"]
               if not ok and x not in IGNORED_REFS]
    if missing:
        L += ["", f"⚠️ **{len(missing)} 个目标文件找不到**（多半是路径写法变了 ⇒ 该件可能**整支失效**，"
                  f"先把路径修对再谈反向灵敏度）：", ""] + \
             [f"- {m}" for m in missing]
    else:
        L += ["", "✅ 目标文件**全部在位**（脚本自建 / 故意构造的路径已登记进 `IGNORED_REFS`）。"]
    L += [
        "", "## 表 B · 尚未有变异覆盖的守卫（**手工登记**，源头 = `mut_cover.py::UNCOVERED`）", "",
        "| 守卫 | 守什么 | 现状 | 建议补法 |", "|---|---|---|---|",
    ]
    for name, what, why, how in UNCOVERED:
        L.append(f"| {name} | {what} | {why} | {how} |")
    if not UNCOVERED:
        #: ⭐ 2026-09-24：表 B **第一次变空**（最后一条 `sticky_probe` 也补上了）——
        #    留一行说明，免得读者以为台账坏了 / 以为这一节被删了。
        L.append("| **（无）** | —— | ✅ **2026-09-24 起表 B 为空**：`tools/audit/` 的每一把尺子"
                 "都有反向灵敏度（或明确的「为什么没有」，见各件 docstring） | —— |")
    L += [
        "", "## 怎么补一条变异", "",
        "1. 照任意表 A 件的骨架：**改坏 → 跑指定判据（期望红）→ 逐字节复原 → MD5 校验**；",
        "2. 脚本 docstring **第一段必须写「守什么」**（本台账的「守什么」列就是抓它）；",
        "3. 放 `tools/mut/`（`TAIL-58` 分目录后），名字 `_mut_<主题>.py`；",
        "4. 重跑本件 ⇒ 台账自动多一行；若它守的原来是表 B 里那条 ⇒ **把那行从 `UNCOVERED` 删掉**。",
        "",
        "---",
        f"_{len(rows)} 变异件 · {sum(len(r['tests']) for r in rows)} 条判据引用 · 生成器 `tools/audit/mut_cover.py`_",
        "",
    ]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="变异覆盖台账生成器")
    ap.add_argument("--check", action="store_true", help="只比对不写（变了 ⇒ rc=1）")
    a = ap.parse_args()
    rows = scan()
    text = render(rows)
    if a.check:
        # ⭐ 排除「生成于」行再比 —— 否则每过一分钟 --check 都会假报"不一致"（首版就栽在这）
        norm = lambda s: "\n".join(l for l in s.splitlines() if not l.startswith("> 生成于"))
        old = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if norm(old) != norm(text):
            print("⚠️ 台账与生成结果不一致 ⇒ 重跑 `tools/audit/mut_cover.py`")
            return 1
        print(f"台账一致 ✔（{len(rows)} 变异件）")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="")
    print(f"已生成 {OUT.relative_to(ROOT)}（{len(rows)} 个变异件 · {len(UNCOVERED)} 条未覆盖登记）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
