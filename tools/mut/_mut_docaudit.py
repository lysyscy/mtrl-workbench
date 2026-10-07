"""**反向灵敏度**：证明 `doc_audit` 的 `T1`–`T19` ＋ **`T24`/`T25`** ＋ `T4` 计数锚点（含 `T5`/`T10`/`T12` 等黄档）**真有区分力**。

背景（为什么非做不可）：
- `T4` 原实现只看「当前版本」行**后 8 行**里的**第一处**四态数字 ⇒ 实测漏过一次真漂移
  （简略版某处还写着 `521 = 绿 447`，而 `T4` 报"必须修 0"）。已改成**两份活文档的每一处**都核对。
- `T6` 原来查「简略版 §③ 必读清单里有没有计划名」；简略版改成**给用户看的一页**后那段没了
  ⇒ 检查落点改为「**简略版里必须指向计划**」。落点一改，就得重新证明它还能红。

⭐⭐ 2026-09-24 **第一次扩面（`M4`–`M8`）**：此前本件**只覆盖 `T4` 扩面 ＋ `T6` 落点**，
   而 `doc_audit` 的其余检查**从没被证明过"内容改坏了它会不会报"**（`mut_cover` 表 B 第 1 行就是这条）。
   补上最常用的**三条红档**（`T1` 幽灵用例号 / `T2` 已废术语 / `T3` 幽灵路径）
   ＋ **两条最易退化的黄档**（`T5` 代码行数 / `T10` 文档预算 —— 它们不进「必须修」，
   ⇒ 判据必须换成"输出里出现那条"，⛔ 拿 red 判会得到"永远没命中"）。

⭐⭐ 2026-09-24 **第二次扩面（`M9`–`M14`）**：把剩下的 `doc_audit` 红档也钉住 ——
   `T17`（**闸门清单活性**，当天新立：一天内核出**四例僵尸闸门**，其中三例**从来没有 `__main__`**）·
   `T9`（纪律的「口径出处」标记）· `T11`（建议类报告必须有「待办登记回执」）·
   `T16`（`T7a` 登记册必须在位）· `T18`（**常量体检**：登记在册的路径 / glob 常量必须解析得到真东西
   —— 治"搬目录后常量失效 ⇒ 检查静默扫空集"，本仓最贵的假绿）·
   `T19`（**文档指针（节号）守卫**：`X.md` §N 必须真有那一节 —— 立起来的当天就抓到 1 处真引用错误）。
   ⇒ 至此 `doc_audit` 的**红档**（`T1`–`T4`/`T6`/`T8`/`T9`/`T11`/`T16`/`T17`/`T18`/`T19`）都有反向灵敏度
   ⇒ 本件共 **31 条**（`M1`–`M31`；`T22` 的自证在 `tools/mut/_mut_injectsplice.py`，⛔ 不在本件）。

⭐⭐⭐ 2026-10-05 **第五批（`M21`–`M23` · `TAIL-235` 丁-1）**：`T3` 的**三个新分支** ——
   仓外标记不再被洗掉 · 仓外白名单真核存在 · 治理区（`.codebuddy/`）纳入扫描面。
   ⚠️ **`M23` 存在的理由最硬**：当天扩面时先把 `.codebuddy/` 加进 `TOP_DIRS`、量测却报「0 处命中」，
   看着像"治理区本来就干净" —— 真因是 **`_PATH_RE` 的首字符类不含 `.`** ⇒ 以点开头的路径整条不匹配。
   那就是**加了半边的守卫**：判据登记在册、实际一行没扫，而它看上去是绿的。
   ⇒ 本批三条**一起**把"常量 ＋ 正则"这对**配对**钉住。

⭐⭐⭐ 2026-10-05 **第六批（`M27`–`M30` · `TAIL-236` 同批修 ①b/③）**：两场真事故的机器眼 ——
   · `M27` = `T24`（**仓库根白名单**）：根上造一个白名单外的**目录** ⇒ 必须报。
     起因：照着 `.gitignore` 注释里的旧落点**把 `work/` 建在了仓库根**，而
     `T3` / `T12` / `T14` **四层守卫没一层拦**（那片地方**不在任何扫描面内**）。
   · `M28` = `T25`（**`.gitignore` 里的落点必须真存在**）：往 `.gitignore` 追加一条含
     核不到落点的注释 ⇒ 必须报。⚠️ `T3` **拦不住**这一类（它只认**带后缀**的引用，而落点多是**目录**）。
   · `M29` = `T10` 的**字节档**：把注入档补到 > 14,400 B ⇒ 必须报。
     ⚠️ 它同时钉住 **`_pad_bytes` 的两条约束**（填充行必须短、且不带标点 —— 否则惊动 `T21`/`T22`，
     报的就不是 `T10` 了）。
   · `M30` = **承重自证**：`work/xxx.md` 这类引用**必须被逼出来** ⇒ 证明"把 `work/` 加进
     `TOP_DIRS`"这半边不是装饰（同 `M23`：**判据与靶必须配对**，常量加了而扫描面没跟 = 等于没加）。

⭐⭐⭐ 2026-10-06 **第七批（`M31` · `TAIL-236` 第 4 批）**：`SCAN_GLOBS` 新增**仓内归档索引**那一格 ——
  降档动作把"可逆"做成「仓外留原文 ＋ 仓内索引留一行（写着**仓外绝对路径**）」⇒ `OUTSIDE_ROOTS`
  那套「仓外白名单**真核存在**」本该为它服务，可 `SCAN_GLOBS` 只有**非递归**的
  `.codebuddy/plans/*.md` ⇒ **索引件压根没被扫**（实测：扫描面里带 `archive` 的件 = 0）
  ⇒ 仓外那份被清掉 ⇒ **指针变死而无人喊**（墓碑 ≠ 守卫）。
  `M31` 钉的就是"那一格真在扫描面里"：往索引里塞一个**核不到的仓外路径** ⇒ 必须报（黄）。
  ⚠️ 判据是**三元组**（`[T3]` ＋ `仓外白名单根下找不到` ＋ 注入的那个路径名）——
  那份索引头部本来就写着别的真仓外路径，判据太宽会在基线里就命中（⇒ 本件开头当场拒跑整支）。

⭐⭐ 2026-09-29 **第三批（`M15`）**：`T9` 当天长出**第二半** —— **注入档里别复述守卫的阈值**（`TAIL-59` 的
   量测逼出来的：`MEMORY.md` 写「`T13`（行数预算 1700）」而真源已 1800，**没有任何尺子看得见**）。
   ⚠️ 它是**黄档** ⇒ 判据必须写成 `needle`（元组），⛔ 拿"变红"判会得到"永远没命中"（同 `M7`/`M8`）。

⭐⭐ 2026-10-01 **第四批（`M16`/`M17`）**：
- `M16` = `T5`**第二半**（`>600` 的件必须被阈值表点名 ⇒ 黄）；
- `M17` = **`T17` 第二半**（`TAIL-204` 入场实测）：**「入门口令」里逐行列出的闸门命令也要"真有入口"** ——
  实测口令列着 `tools\audit\audit_work.py`，而那件**从来没有 `__main__`** ⇒ 单跑 **0 行输出**、
  `rc` 恒 0 = **第五例僵尸闸门**，只因口令不是 `foreach` 而**整批漏网** ⇒ 判据已扩进 `T17`。
- ⚠️ 同一轮**换掉了 `M7` 的靶**：原靶 `mod01_projects/router.py` **自己长到了 401 行** ⇒ 那条判据
  **基线里就已命中** ⇒ 本件开头"基线已含该判据"当场**拒跑整支** —— **静默烂掉的又一例**
  （它不在任何闸门清单里 ⇒ 没人会发现；判据换靶见 `T5_TARGET` 上方注释）。

做法：逐条把实现**改坏** → 确认 `doc_audit` **报出来了** → 全部复原（**MD5 逐字节校验**）。
⚠️ 一律走 bytes ＋ 按目标文件行尾归一（`.md` 可能是 CRLF，`write_text` 会静默换成 LF ⇒ MD5 假 BAD）。
⚠️ 2026-09-24：**跑一半被取消** ⇒ `finally` 不执行 ⇒ `M11` 的临时靶**留在盘上**（当天实测一次：
   `artifacts/_mut_建议_临时.md` 残留 ⇒ 基线多一条 `T11` 红 ⇒ 本件拒绝跑，提示语看着像"文档里真有漂移"）
   ⇒ 已在 `main()` 开头加**中断自愈**（`create` 式靶若在位 ⇒ 先清）。
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLANS = ROOT / ".codebuddy" / "plans"
#: 「给人看的那一页」= **根 `README.md`**（⭐ 2026-10-01 `TAIL-204` 第 6 步换件：原 `plans/执行情况-主文档.md`
#:   已"只留待办"并进 `README.md` §〇 ⇒ ⛔ 旧路径不存在；见 `audit_common.HANDBOOK_REL` 的说明）。
HAND = ROOT / "README.md"
PLAN = PLANS / "开发计划-主文档.md"
MEM = ROOT / ".codebuddy" / "memory" / "MEMORY.md"
REGISTRY = ROOT / "tools" / "t7_expected.txt"
GUARD_SRC = ROOT / "tools" / "audit" / "audit_meta.py"      #: `T18` 的靶（常量定义处）
COMMON_SRC = ROOT / "tools" / "audit" / "audit_common.py"    #: `M25`/`M26` 的靶（`OUTSIDE_ROOTS` 所在件）
IDE = ROOT / ".codebuddy" / "memory" / "IDE-细节.md"        #: `M24` 的靶（豁免词表的**实测承重件**）
RUNNER = ROOT / "tools" / "oneoff" / "_run_rulers.py"
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"


def _b(s: str) -> bytes:
    return s.replace("\r\n", "\n").encode("utf-8")


def _fit(frag: bytes, sample: bytes) -> bytes:
    if b"\r\n" in sample:
        return frag.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return frag.replace(b"\r\n", b"\n")


#: ⚠️⚠️ 2026-09-23（`TAIL-77`）：M1/M3 原先**把当时的四态数字与尾巴计数写死在锚点里**
#:    （`**528 = 绿 454…**` / `A 类 **10** 条 … 已销号 **41** 条`）⇒ **每批一改文档就 SKIP＝静默失效**：
#:    脚本一个"未验证"打出来、退出码却是 1，看起来跟"变异没命中"**长得一模一样**。
#:    ⇒ 改成**动态锚点**：从**当前文档**正则取那处数字，再把捕获到的那个数改小 1（⛔ 别再写死）。
_四态PAT = r"绿 (\d+) · 红 (\d+) · 待建 (\d+) · 未绑定 (\d+)"
_尾巴PAT = r"A 类 \*\*\d+\*\* 条 · B 类 \*\*\d+\*\* 条 · C 类 \*\*\d+\*\* 条 · 已销号 \*\*(\d+)\*\* 条"
#: `T9` 段界（真源 = `audit_meta.RULE_SECTION_RE`；⛔ 两处同改，理由见 `_dyn_rule_line`）
_RULE_SEC_RE = re.compile(r"^##\s*八[、.]\s*工程纪律")


def _dyn(pat: str, text: str) -> tuple[bytes, bytes]:
    """按正则从**当前文档**取锚点，并把**捕获到的那个数字**改小 1（`T4` / `T6` 必须因此变红）。"""
    m = re.search(pat, text)
    assert m, f"动态锚点没找到（文档又改写法了）：{pat}"
    old = m.group(0)
    return _b(old), _b(old.replace(m.group(1), str(int(m.group(1)) - 1), 1))


def _dyn_rule_line(text: str) -> tuple[bytes, bytes]:
    """从 `MEMORY.md` 的 **§八「工程纪律」段内**取**第一条「出处标记只有 `[助手自定`」的纪律行**，
    把那个标记毁掉。

    ⚠️ 为什么不能直接替换文件里**第一处** `[助手自定`：`§八` 的**引言块**里也写着这个词
    （那是"讲这条规矩"的文字，不是纪律行）⇒ 替换到它 ⇒ `T9` 根本不管 ⇒ 变异**假没命中**
    （2026-09-24 实测踩到）。⇒ 锚点必须**连整行一起取**（整行唯一 ⇒ 精确命中那一行）。
    ⚠️⚠️ **2026-10-05（`TAIL-235` 丁-1 加 `M21`–`M23` 时当场暴露）**：光"连整行一起取"**还不够** ——
       `MEMORY.md` 的 `§五`（协作习惯）里也有一条带 `[助手自定·2026-10-02]` 的条目行
       （"破坏性操作先查牵连…"），而它**排在 §八 前面** ⇒ 原实现挑中它 ⇒ 变异落在 `T9`
       **根本不扫的段**里 ⇒ **`M10` 静默失效、而它看上去是绿的**（实测"必须修 0"＝未命中）。
       ⇒ 现在**只在 §八 段内挑**。
       ⛔ 段界口径的真源 = `audit_meta.RULE_SECTION_RE`（⛔ 本件不 import 尺子：
       `tools/audit/` 不在 `sys.path`，而为一处段界把尺子拖进变异件不值得）⇒
       **改那段标题时两处同改**。
    """
    lines = text.splitlines()
    start = next((k for k, l in enumerate(lines) if _RULE_SEC_RE.match(l.strip())), None)
    if start is None:
        raise AssertionError("MEMORY.md 里找不到 §八 段 ⇒ 本件需重定靶")
    end = next((k for k in range(start + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
    for line in lines[start + 1:end]:
        if not line.strip().startswith("- ") or "[助手自定" not in line:
            continue
        if any(o in line for o in ("[用户", "[交付面")):      # ⚠️ 还有别的标记 ⇒ 毁一个它照样过
            continue
        return _b(line), _b(line.replace("[助手自定", "（助手自定", 1))
    raise AssertionError("§八 里找不到「出处标记只有 `[助手自定`」的纪律行 ⇒ 本件需重定靶")


def _pad_lines(src: bytes, target: int) -> bytes:
    """追加**恰好**够到 `target` 行的换行 —— ⚠️ 末尾有没有换行**两种情形差 1 行**（⛔ 别写死 `b"\\n"`）。"""
    cur = len(src.decode("utf-8").splitlines())
    need = target - cur
    assert need > 0, f"目标 {target} 行 ≤ 现值 {cur} 行 ⇒ 本件需重定靶"
    return src + (b"\n" * need if src.endswith(b"\n") else b"\n" * (need + 1))


def _pad_bytes(src: bytes, target: int) -> bytes:
    """追加**刚好越过** `target` 字节的填充行 —— `M29`（`T10` 的**字节档**）用。

    ⚠️ 填充**只能是短行、且不带标点**（本次实测的两条约束）：
      · 单行 > 800 字会惊动 `T21`（字墙）⇒ 那报的就不是 `T10` 了；
      · 行尾标点紧跟列表符会惊动 `T22`（注入档粘连）⇒ 同上。
    ⚠️ 追加的**行数**必须仍在该档的行预算内（`MEMORY.md` 预算 200 行 ⇒ 这里只加几十行）。
    """
    need = target - len(src)
    assert need > 0, f"目标 {target} 字节 ≤ 现值 {len(src)} 字节 ⇒ 本件需重定靶"
    filler = b"mut-byte-pad\n"
    return src + filler * (need // len(filler) + 1)


# --------------------------------------------------- 追加式变异（M4–M8 · 2026-09-24 扩面之一）
#
#: `ops/*.md` ∈ `SCAN_GLOBS` ⇒ `ops/阈值表.md` 在 `T1/T2/T3` 的扫描面内（且它不是留痕档 ⇒ 命中即红）
THRESHOLD = ROOT / "ops" / "阈值表.md"
#: ⭐ `T25`（2026-10-05 立）靶：**仓根 `.gitignore`** —— 往里追加一条含「核不到的落点」的注释
#:   （用完**按 bytes 复原**）。⚠️ 它不在 `doc_audit` 的扫描面里 ⇒ 只有 `T25` 看得见它。
GITIGNORE = ROOT / ".gitignore"
#: ⭐ `M31`（2026-10-06 立）靶：**仓内归档索引件**（降档动作往它里面写仓外落点）——
#:   往里追加一行含「核不到的**仓外**路径」⇒ `T3` 的仓外白名单分支必须报（黄：该件在 `LENIENT_GLOBS`）。
#:   ⚠️ 它 2026-10-06 之前**不在** `SCAN_GLOBS` 里（只有非递归的 `.codebuddy/plans/*.md`）⇒ 本条
#:   **同时**钉住"那一格真在扫描面内"（同 `M23` 钉 `_PATH_RE` 那个配对：判据与靶必须成对）。
INDEX_LEDGER = ROOT / ".codebuddy" / "plans" / "archive" / "归档-留痕索引-20261005.md"
#: ⭐ `T24`（2026-10-05 立）靶：在**仓库根**造一个白名单外的目录（用完 `rmdir`）——
#:   复现的就是当天那场事故的形状（"根上多出一块没人看的地方"）。
ROOT_ZONE = ROOT / "_mut_root_zone"
#: `T5` 靶：挑一件**离 400 线还有余量**的件 ⇒ 补到 401 行即越线。
#:   ⚠️ 2026-10-01 **换靶**（`TAIL-204` 入场实测）：原靶 `mod01_projects/router.py` **自己长到了 401 行**
#:      ⇒ 它的「401 行」那条黄**基线里就有** ⇒ 本件开头那句"基线已含该判据 ⇒ 判据无效，先重定靶"
#:      **当场拒跑**。这正是本仓点名过的**变异件静默烂掉** —— 而它**不在任何闸门清单里**（`_run_rulers`
#:      不含 `tools/mut/**`）⇒ 烂了多久没人会知道，直到有人（本轮）真去跑它。
#:   ⇒ 换到 `mod05_flow/importer.py`（现值 **299** 行，留 ~100 行余量 ⇒ 不随日常改动再烂）。
T5_TARGET = ROOT / "backend" / "app" / "mod05_flow" / "importer.py"
#: `T17` 靶：随便挑**一把在闸门清单里的尺子** —— 把它的 `__main__` 段整段截掉
T17_TARGET = ROOT / "tools" / "audit" / "cover_gap.py"
#: ⭐ `T17` **第二半**的靶（2026-10-01 立）：「入门口令」里逐行列着的那件 —— 同款改坏（截掉入口）。
#:    ⚠️ 本件 2026-10-01 之前**根本没有入口**（单跑 0 行输出）；补齐后才有得截 ⇒ 靶才成立。
T17_REGISTERED_TARGET = ROOT / "tools" / "audit" / "audit_work.py"
#: ⭐ `T11` 靶：`artifacts/` 下**名字含「建议」**的 md 必须有「待办登记回执」⇒ 造一个**没有**的（用完删掉）
T11_TMP = ROOT / "artifacts" / "_mut_建议_临时.md"
#: ⭐⭐ 2026-10-04（`TAIL-225` 票体系）`T6` 的**票文件**靶：
#:   ① 把一张**在办票**的票文件挪开 ⇒ 必须报「没有票文件」（用完挪回）
#:   ② 造一张**幽灵票文件**（编号在台账里不存在）⇒ 必须报「幽灵票文件」（用完删掉）
TICKET = ROOT / ".codebuddy" / "work" / "50-tickets" / "TAIL-188-交付包与迁移.md"
GHOST_TICKET = ROOT / ".codebuddy" / "work" / "50-tickets" / "TAIL-9999-幽灵票.md"

#: ⚠️ 追加块**前后各留 3 空行**：`_hit` 的豁免窗口 = 命中行 **±2 行** ⇒ 贴着正文追加可能被邻行的
#:    「已删 / 改为 / 原」之类词**降档**（那就成了"变异没命中"，看着跟"检查瞎了"**一模一样**）。
#: 模式：`red` = 「必须修」必须由 0 变正（**红档**）｜`needle` = 输出里必须出现该串（**黄档**，不进「必须修」）。
#: `also` = 额外判据（元组 = **同一行里**要同时出现）—— ⚠️ 红档也要它：**红 ≠ 一定是这条报的**。
MUTS_APPEND: list[dict] = [
    {"desc": "M4 `T1` 幽灵用例号（验收基线里没有这个号）", "mode": "red", "needle": "",
     "path": THRESHOLD, "frag": lambda src: _fit(_b("\n\n\n判据归属：`ACC-PLAN-MANUAL-999`。\n\n\n"), src)},
    {"desc": "M5 `T2` 已废术语（2026-09-16 已改名的旧词「四金额」）", "mode": "red", "needle": "",
     "path": THRESHOLD, "frag": lambda src: _fit(_b("\n\n\n四金额字段说明\n\n\n"), src)},
    {"desc": "M6 `T3` 幽灵路径（仓里没有 `core/nope_ghost.py`）", "mode": "red", "needle": "",
     "path": THRESHOLD, "frag": lambda src: _fit(_b("\n\n\n参见 `backend/app/core/nope_ghost.py`。\n\n\n"), src)},
    {"desc": "M7 `T5` 代码行数越线（补到 401 ⇒ 须登记拆分计划）", "mode": "needle",
     "needle": ("backend/app/mod05_flow/importer.py", "401 行"),
     "path": T5_TARGET, "lines": 401, "frag": lambda src: _pad_lines(src, 401)},
    # ⚠️ 2026-10-01（`TAIL-204` 第 6 步）**换靶**：原靶 = `plans/执行情况-主文档.md`（预算 200），
    #    该件已取消（用户裁定「只留待办」⇒ 并进根 `README.md` §〇）⇒ 靶改成 **`README.md`（预算 240）**。
    #    ⭐ 与 `M7` 换靶同因：**靶必须跟着"那件还在不在、预算还是不是那个数"走**，否则判据静默失效。
    {"desc": "M8 `T10` 文档超预算（README 补到 241 > 240）", "mode": "needle",
     "needle": ("README.md", "241 行（预算 240"),
     "path": HAND, "lines": 241, "frag": lambda src: _pad_lines(src, 241)},
]

# --------------------------------------------------- 第二次扩面（M9–M12 · 2026-09-24）
MUTS_RED2: list[dict] = [
    # ⭐ `T17`（当天新立）：把靶的 `__main__` 段整段截掉 ⇒ 「跑它 = 空转」必须被判红
    {"desc": "M9 `T17` 闸门清单里的尺子**没有入口**（跑它 = 空转）", "mode": "red",
     "also": ("[T17]", "cover_gap"), "path": T17_TARGET, "truncate": 'if __name__ == "__main__":'},
    # ⭐ `T9`：把 §八 里某条纪律的出处标记去掉 ⇒ 必须红（动态取锚点 ⇒ 文档改了也不失效）
    {"desc": "M10 `T9` 某条纪律**没标口径出处**", "mode": "red",
     "also": ("[T9]", "这条纪律没标"), "path": MEM,
     "old_new": _dyn_rule_line(MEM.read_text(encoding="utf-8")), "all": False},
    # ⭐ `T11`：造一个「名字含建议、但没有登记回执」的报告 ⇒ 必须红（用完删掉）
    {"desc": "M11 `T11` 建议类报告**没有「待办登记回执」**", "mode": "red",
     "also": ("[T11]", "_mut_建议_临时.md"), "path": T11_TMP,
     "create": "# 临时建议件（本件用完即删）\n\n本文提几条建议，但**故意不写**「待办登记回执」段。\n"},
    # ⭐ `T16`：把 `T7a` 的登记册挪开 ⇒ 必须红（用完挪回）
    {"desc": "M12 `T16` `T7a` 登记册**读不到**", "mode": "red",
     "also": ("[T16]",), "path": REGISTRY, "rename_away": REGISTRY.with_suffix(".txt._mut_tmp")},
    # ⭐⭐ `T18`（2026-09-24 立）：把一个**登记在册的路径常量**改错 ⇒ 必须红。
    #    ⚠️ **为什么挑 `RECEIPT_DIR`**：它失效时 `T11` 会**静默返回空**（`check_report_receipts`
    #    开头就是 `if not root.is_dir(): return hits`）⇒ 这一族**只有 `T18` 抓得住** ——
    #    这正是立它的理由（"检查在跑、其实扫空集"）。
    {"desc": "M13 `T18` 路径常量指错（`RECEIPT_DIR` 少一个字）", "mode": "red",
     "also": ("[T18]", "RECEIPT_DIR"), "path": GUARD_SRC,
     "old_new": (_b('RECEIPT_DIR = "artifacts"'), _b('RECEIPT_DIR = "artifacts_typo"')), "all": False},
    # ⭐⭐ `T19`（2026-09-24 立 · `TAIL-84`）：造一处**指到不存在的节**的引用 ⇒ 必须报（红）。
    #    ⚠️ 靶选 `ops/阈值表.md`（`ops/*.md` ∈ 扫描面 ⇒ 命中即红）；⚠️ 引用必须**紧贴**
    #    （本守卫只认「`X.md` 与 `§N` 相距 ≤8 字符」—— 松散写法是刻意排除的，见其注释）。
    {"desc": "M14 `T19` 文档指针**指到不存在的节**（`ops/阈值表.md` 里没有 §九九）", "mode": "red",
     "also": ("[T19]", "§九九"), "path": THRESHOLD,
     "frag": lambda src: _fit(_b("\n\n\n另见 `ops/阈值表.md` §九九。\n\n\n"), src)},
    # ⭐⭐ `T9`②（2026-09-29 立 · `TAIL-59` 量测）：在**注入档**里复述一个守卫的阈值 ⇒ 必须报（**黄**）。
    #    ⚠️ 为什么只盯这一个形态：量测证明"数字级"扫描**噪音压倒信号**（阈值表 27 行里 26 行"命中"，
    #      绝大多数是巧合 —— `6`/`300`/`1000` 在任何文档里都会自然出现）⇒ 只有"**指名复述**"
    #      （`T<n>` ＋ 括号里的数字）**自带上下文**、判得准。
    {"desc": "M15 `T9`② 注入档里**复述守卫阈值**（造一句 `T13`（行数预算 9999））", "mode": "needle",
     "needle": ("[T9]", "复述了守卫的阈值"), "path": MEM,
     "frag": lambda src: _fit(_b("\n\n\n⭐ 归档守卫 = `T13`（行数预算 9999 ＋ 过程标题词）。\n\n\n"), src)},
    # ⭐⭐ `T5` 第二半（2026-09-29 立 · `TAIL-06` 量测）：把阈值表里**某个 >600 件的文件名抹掉**
    #    ⇒ 必须报「阈值表没点名本件」（**黄** ⇒ 判据写成 `needle` 元组）。
    #    ⚠️ **靶必须挑"在表里只出现一次"的名字**：第一次挑的 `_shell_smoke.py` **当场没命中** ——
    #      因为那句"为什么不拆"的历史叙事里**还留着**它（`（671 行）`）⇒ 判据的认法是"文件名出现即可"
    #      ⇒ 抹掉一处它仍然算"被点名" ✗（⭐ 教训：**变异的靶要先确认"唯一"**）。
    {"desc": "M16 `T5`② `>600` 的件**没被阈值表点名**（抹掉 `mod06_proc/importer.py`）", "mode": "needle",
     "needle": ("importer.py", "阈值表没点名本件"), "path": THRESHOLD,
     "old_new": (_b("`backend/app/mod06_proc/importer.py` **668**"),
                 _b("`backend/app/mod06_proc/importer_zzz.py` **668**")), "all": False},
    # TAIL-245：注册项入口与空扫仍要证伪，靶从历史口令迁到唯一 CMDS。
    {"desc": "M17 `T17` CMDS 登记项没有入口（跑它 = 空转）", "mode": "red",
     "also": ("[T17]", "闸门里的", "audit_work"), "path": T17_REGISTERED_TARGET,
     "truncate": 'if __name__ == "__main__":'},
    {"desc": "M18 `T17` CMDS 定义锚消失 ⇒ 空扫必须判红", "mode": "red",
     "also": ("[T17]", "空扫"), "path": RUNNER,
     "old_new": (_b("CMDS: list[tuple[str, list[str]]] = ["),
                 _b("CMDS_MISSING: list[tuple[str, list[str]]] = [")), "all": False},
    # ⭐⭐ 2026-10-04（`TAIL-225` 票体系）：`T6` 新长的两查 —— **票文件必须在位** ＋ **不许幽灵票**。
    #    ⚠️ 靶必须挑**在办的**票（`§一`），因为这两查只对在办生效（`§四` 存量按留痕口径不追改）。
    {"desc": "M19 `T6` 在办票**没有票文件**（把 `TAIL-188` 的票文件挪开）", "mode": "red",
     "also": ("[T6]", "没有票文件"), "path": TICKET,
     "rename_away": TICKET.with_suffix(".md._mut_tmp")},
    {"desc": "M20 `T6` 票仓里有**幽灵票文件**（造一张台账里没有的编号）", "mode": "red",
     "also": ("[T6]", "幽灵票文件"), "path": GHOST_TICKET,
     "create": "# TAIL-9999: 幽灵票（本件用完即删）\n\n**What to build:** x\n\n**Blocked by:** None\n\n"
               "**Status:** ready-for-agent\n\n- [ ] x\n"},
    # ⭐⭐⭐ 2026-10-05（`TAIL-235` 丁-1）：`T3` **三个新分支**的反向灵敏度。
    #   背景：当天扩面（治理区进扫描面 ＋ 仓外走显式白名单）之后，`.codebuddy/` 整片**第一次**有守卫，
    #   而扩面**当场捞出 24 处真幽灵** ⇒ 这三条就是钉住"新加的那半边真有牙"。
    # ⚠️ M21 是本轮**最要紧的一条**：它证明「`〔已归档〕` 前缀不再能把坏路径洗掉」。
    #   2026-10-05 实测过那个失效：`_PATH_RE` 首字符限 `[A-Za-z0-9_]` ⇒ 加中文前缀整条不匹配
    #   ⇒ 而那 3 条的 `ops/` **本来在 `TOP_DIRS` 内**（`T3` 该照到）⇒ **保护被消掉了、闸门还全绿**。
    {"desc": "M21 `T3` **仓外标记不再是豁免**（加 `〔已归档〕` 前缀 ⇒ 仍必须报）", "mode": "needle",
     # ⚠️ 2026-10-05（`TAIL-236` 同批修 轮）：判据串**必须再窄一格**（加上注入的那个坏路径名）。
     #   本条原先只判 `("[T3]", 带仓外标记的引用核不到)` ⇒ `TAIL-235` 票面第 24 行那句**探针字面**
     #   在基线里就报了同一条消息 ⇒ 本件开头的"基线不许含该判据"当场拒跑**整支**
     #   （＝ 本件的 `M27`–`M30` 也跟着没法验）。⇒ 加 `nope_ghost` 把判据钉到**注入的那一处**。
     #   ⭐ 这正是本件 `M7` 那条注释早就写过的纪律：**黄/needle 判据一律写元组、且够窄**。
     "needle": ("[T3]", "带仓外标记的引用核不到", "nope_ghost"), "path": THRESHOLD,
     "frag": lambda src: _fit(_b("\n\n\n留档指针：`〔已归档〕ops/nope_ghost.py`。\n\n\n"), src)},
    # ⚠️ ② 仓外白名单：文档里写**仓外绝对路径** ⇒ `T3` 到那个根下**真核存在**
    #   （此前这类引用对所有尺子隐形 —— 不是因为合法，而是因为路径含中文、正则压根不匹配）。
    {"desc": "M22 `T3` **仓外白名单真核存在**（仓外根下点名一份不存在的件）", "mode": "needle",
     "needle": ("[T3]", "仓外白名单根下找不到"), "path": THRESHOLD,
     "frag": lambda src: _fit(_b("\n\n\n归档件见 `D:\\dev\\.归档-mtrl\\ops\\nope_ghost.md`。\n\n\n"), src)},
    # ⚠️ ③ `TOP_DIRS` 新增 `.codebuddy/` 那一项**是不是承重**：
    #   ⚠️⚠️ 当天真的踩过"加了半边"：先把 `.codebuddy/` 加进 `TOP_DIRS`，量测却报"0 处命中"，
    #   看着像"治理区本来就干净"，真因是 **`_PATH_RE` 首字符类不含 `.`** ⇒ 压根不匹配。
    #   ⇒ 这条就是**专门钉那个正则与那个常量配得上对**（判据与靶是一对，本仓老话）。
    {"desc": "M23 `T3` 治理区纳入扫描面（`.codebuddy/…` 的幽灵路径必须报红）", "mode": "red",
     "also": ("[T3]", "nope_ghost"), "path": THRESHOLD,
     "frag": lambda src: _fit(_b("\n\n\n另见 `.codebuddy/work/50-tickets/nope_ghost.md`。\n\n\n"), src)},
    # ⚠️ `M24`–`M26` 是 `/code-review`（2026-10-05）补的：审查指出三处「判据装了但没人证伪」
    #   —— 豁免词表没有靶、仓外白名单登记没有靶、`T18` 新增的两档没有靶。
    # ⚠️ `M24` 钉的是**距离闸**：提示词挪到**行尾远处** ⇒ 那个路径**必须仍报红**
    #   （否则"整行命中就算"就回来了 ⇒ 泛词迟早巧合命中 ⇒ 又一次假绿）。
    {"desc": "M24 `T3` 旧路径豁免**必须贴着那个路径**（提示词挪到行尾 ⇒ 仍须报红）", "mode": "red",
     "also": ("[T3]", "models_registry"), "path": IDE,
     "old_new": (_b("⛔ 旧路径 `app/core/models_registry.py` 不存在了"),
                 _b("`app/core/models_registry.py` ⛔ 这条早已不是现在的落点（当年行内的标注写的是：旧路径）")), "all": False},
    # ⚠️ `M25`/`M26` 钉 `T18` 的两个**新档**（`GUARDED` 加了它们，却没人为它们写靶）。
    {"desc": "M25 `T18` 仓外根登记**在盘上不存在**（`outside_prefix` 档）", "mode": "red",
     "also": ("[T18]", "仓外根"), "path": COMMON_SRC,
     "old_new": (_b('OUTSIDE_ROOTS: tuple[str, ...] = ("D:/dev/.归档-mtrl",)'),
                 _b('OUTSIDE_ROOTS: tuple[str, ...] = ("D:/dev/.归档-mtrl_typo",)')), "all": False},
    {"desc": "M26 `T18` 豁免词表**不许有空项**（`nonempty` 档 · 空表 = 判据等于没有）", "mode": "red",
     "also": ("[T18]", "空项"), "path": COMMON_SRC,
     "old_new": (_b('    "旧路径", "已不存在", "已退场", "已搬走", "已移出", "不在仓内",\n'),
                 _b('    "旧路径", "已不存在", "已退场", "已搬走", "已移出", "不在仓内", "",\n')),
     "all": False},
    # ⭐⭐⭐ 2026-10-05（`TAIL-236` 同批修 ①b/③）：**三条新判据**的反向灵敏度（`M27`–`M29`）
    #   ＋ 一条**承重自证**（`M30`）。背景是当天两场真事故：
    #   ① 照着 `.gitignore` 注释里的旧落点，**把 `work/` 建在了仓库根** —— `T3`/`T12`/`T14`
    #      四层守卫**没一层拦**（那片地方不在任何扫描面内）；
    #   ② 注入档**字节超顶**却被宿主**静默截断**，而只查行数的 `T10` **看不见它**。
    #   `M30` 钉的是另一件事：**把 `work/` 加进 `TOP_DIRS` 这半边是不是真承重**
    #   （同 `M23`：判据与靶必须配对 —— 常量加了、扫描面没跟，就等于没加）。
    {"desc": "M27 `T24` 仓库根多出白名单外的**目录**（`_mut_root_zone/`）", "mode": "red",
     "also": ("[T24]", "_mut_root_zone"), "path": ROOT_ZONE, "mkdir": "_mut_root_zone"},
    {"desc": "M28 `T25` `.gitignore` 里写着**核不到的落点路径**", "mode": "red",
     "also": ("[T25]", "nope_zone"), "path": GITIGNORE,
     "frag": lambda src: _fit(_b("\n# 落点：`.codebuddy/work/nope_zone/`（变异注入 · 用完即复原）\n"), src)},
    {"desc": "M29 `T10` **字节档**（注入档补到 > 14400 B ⇒ 必须报）", "mode": "needle",
     "needle": ("MEMORY.md", "字节（预算 14400）"), "path": MEM,
     "frag": lambda src: _pad_bytes(src, 14401)},
    {"desc": "M30 `T3` 的 `work/` 前缀**承重**（`work/xxx.md` 这类引用必须被逼出来）", "mode": "red",
     "also": ("[T3]", "work/nope_ghost.md"), "path": THRESHOLD,
     "frag": lambda src: _fit(_b("\n\n\n另见 `work/nope_ghost.md`。\n\n\n"), src)},
    # ⭐⭐⭐ 2026-10-06（`TAIL-236` 第 4 批）：**仓内归档索引**那一格进扫描面（`M31`）。
    #   背景：降档动作把"可逆"做成「仓外留原文 ＋ 仓内索引留一行」，而那一行里写的是**仓外绝对路径**
    #   —— `audit_common.OUTSIDE_ROOTS` 那套「仓外白名单**真核存在**」本来就是为它准备的。
    #   ⚠️ 但 `SCAN_GLOBS` 只有**非递归**的 `.codebuddy/plans/*.md` ⇒ **索引件根本没被扫**
    #   （实测：扫描面里带 `archive` 的件 = 0）⇒ 仓外那份被清掉 ⇒ **指针变死，没任何人喊**。
    #   ⇒ 本条钉的就是「那一格真在扫描面里」：**造一个核不到的仓外路径进索引 ⇒ 必须报**。
    {"desc": "M31 `T3` 仓外白名单真核**扫得到仓内索引**（索引里写个不存在的仓外路径）", "mode": "needle",
     "needle": ("[T3]", "仓外白名单根下找不到", "nope_outside"), "path": INDEX_LEDGER,
     "frag": lambda src: _fit(_b("\n\n\n留档指针见 `D:\\dev\\.归档-mtrl\\nope_outside_幽灵件.md`。\n\n\n"), src)},
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_doc_audit() -> tuple[int, str]:
    """→ (`必须修 N`, 全量输出)。⚠️ **不看退出码** —— `doc_audit` 的 rc 还含黄档与其它档，两回事。"""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    # ⚠️ 2026-09-23（`TAIL-77`）：尺子已随 `TAIL-58` 搬进 `tools/audit/` —— 旧路径 ⇒ 子进程根本没起
    #    来 ⇒ `必须修 N` 一处都搜不到 ⇒ 返回 `-1` ⇒ 每条变异都"看起来变红"（**全是假红**）。
    # ⚠️ 2026-09-24：**必须带 `-v`** —— 默认只把黄档**按件聚合**成「N 条 <路径>」，
    #    于是"某条黄档编报了什么"在输出里**根本看不见** ⇒ 黄档的判据会**永远不命中**（假绿）。
    r = subprocess.run([str(PY), str(ROOT / "tools" / "audit" / "doc_audit.py"), "-v"],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"必须修 (\d+)", out)
    return (int(m.group(1)) if m else -1), out


def doc_audit_red() -> int:
    return run_doc_audit()[0]


#: ⚠️ **判据串要够窄**：`T5` 的报法是「黄 <路径> <N> 行」⇒ 单拿 `"401 行"` 会撞上**别的** 401 行件
#:    （2026-09-24 实测：基线里已有两件 401 行 ⇒ 那句判据**永远为真**、这条变异就成了假绿）。
#:    ⇒ 黄档的判据一律写**元组** = 「**同一行里**必须同时出现这几个串」。
def _needle_hit(needle: str | tuple[str, ...], out: str) -> bool:
    if isinstance(needle, tuple):
        return any(all(x in ln for x in needle) for ln in out.splitlines())
    return needle in out


def _apply(c: dict) -> None:
    """把一条变异**落地**（写成"坏"的状态）。"""
    p = c["path"]
    src = p.read_bytes() if p.exists() else b""     # ⚠️ `create` 式的靶**初始不存在**
    if "mkdir" in c:
        p.mkdir()                                   # `M27`：在根上造一个白名单外的目录
    elif "create" in c:
        p.write_text(c["create"], encoding="utf-8", newline="")
    elif "rename_away" in c:
        p.rename(c["rename_away"])
    elif "frag" in c:
        p.write_bytes(_fit(c["frag"](src), src))
    elif "truncate" in c:
        idx = src.find(c["truncate"].encode("utf-8"))
        assert idx > 0, f"被截断的锚点没找到：{c['truncate']}（靶件改写法了 ⇒ 本件需重定靶）"
        p.write_bytes(src[:idx])                      # 从入口那行起**整段截掉**（含它自己）
    else:
        old, new_lf = c["old_new"]
        old, new = _fit(old, src), _fit(new_lf, src)
        n = src.count(old)
        many = c.get("all") or c.get("first")       # `first` 也只改一处，但**允许多次命中**
        assert n >= 1 if many else n == 1, \
            f"锚点命中 {n} 次（期望 {'≥1' if many else '1'}）⇒ **未验证**"
        p.write_bytes(src.replace(old, new, 1 if c.get("first") else -1))


def _restore(c: dict, src: bytes) -> None:
    p = c["path"]
    if "mkdir" in c:
        p.rmdir()
        assert not p.exists(), "mkdir 式靶复原后目录仍在"
    elif "create" in c:
        p.unlink(missing_ok=True)
    elif "rename_away" in c:
        c["rename_away"].rename(p)
        assert p.read_bytes() == src, "rename 复原后内容不一致"
    else:
        p.write_bytes(src)


def main() -> int:
    # ⭐ M1 / M3 的锚点**现取**（见 `_四态PAT` / `_尾巴PAT` 上方注释）
    cases: list[dict] = [
        {"desc": "M1 简略版的四态数字改错（原 T4 看不见这一处 —— 扩面后才抓得到）", "mode": "red",
         "needle": "", "path": HAND, "old_new": _dyn(_四态PAT, HAND.read_text(encoding="utf-8")), "all": False},
        {"desc": "M2 简略版里不再指向计划文档（台账就没人看得见）", "mode": "red", "needle": "",
         "path": HAND, "old_new": (_b("开发计划-主文档"), _b("某份计划文档")), "all": True},
        {"desc": "M3 台账顶部计数与实际不符（人按错的数判断尾巴有多少）", "mode": "red", "needle": "",
         "path": PLAN, "old_new": _dyn(_尾巴PAT, PLAN.read_text(encoding="utf-8")), "all": False},
        *MUTS_APPEND,
        *MUTS_RED2,
    ]
    # ⭐⭐ 2026-09-24：**中断自愈** —— 本件跑一半被取消（`Ctrl-C` / 进程被杀）⇒ `finally` 不执行 ⇒
    #   `create` 式靶（`M11`）会**留在盘上**；症状 = 基线里多一条 `T11` 红 ⇒ 本件**拒绝跑**，
    #   而提示语是"先把红清了再来"（**不指向真相** —— 当天实测踩过一次）。
    #   ⇒ 按定义"本件跑之前它不该存在" ⇒ 这儿先清掉，让脚本**自愈**而不是卡住人。
    for c in cases:
        if "create" in c and c["path"].exists():
            print(f"  ⚠️ 发现上次中断的残留靶：{c['path'].name} ⇒ 先清掉（本件跑之前它不该存在）")
            c["path"].unlink()
        if "mkdir" in c and c["path"].exists():
            print(f"  ⚠️ 发现上次中断的残留靶目录：{c['path'].name} ⇒ 先删掉（本件跑之前它不该存在）")
            c["path"].rmdir()

    #: ⚠️ 有的靶**初始不存在**（如 `M11` 那个临时报告 —— 它要"从无到有"地造出来）⇒ 只记**在位的**
    before = {c["path"]: c["path"].read_bytes() for c in cases if c["path"].exists()}
    created = [c["path"] for c in cases if "create" in c or "mkdir" in c]

    base_red, base_out = run_doc_audit()
    print(f"基线（未改坏）doc_audit 必须修 {base_red}（应为 0）· 输出 {len(base_out)} 字符")
    for c in cases:
        n = c.get("needle") or c.get("also")
        if n and _needle_hit(n, base_out):
            print(f"  ⛔ 基线的输出里**已经**有「{n}」⇒ 本件这条判据无效，先重定靶")
            return 1
    if base_red != 0:
        print("  ⛔ 基线就有「必须修」⇒ 先把红清了再来跑本件")
        return 1

    hit = 0
    for c in cases:
        src = c["path"].read_bytes() if c["path"].exists() else b""   # ⚠️ `create` 式的靶**初始不存在**
        try:
            _apply(c)
            if "lines" in c:                                   # 自检：追加式必须**恰好**到目标行数
                got_lines = len(c["path"].read_text(encoding="utf-8").splitlines())
                assert got_lines == c["lines"], f"追加后 {got_lines} 行 ≠ 目标 {c['lines']} 行"
            red, out = run_doc_audit()
        finally:
            _restore(c, src)                                   # ⭐ 逐条立刻按原 bytes 还原
        if c["mode"] == "red":
            ok = red > 0
            tail = f"必须修 {red}（变红）"
        else:
            ok = _needle_hit(c["needle"], out)
            tail = "输出里出现该条（黄档）"
        if ok and c.get("also"):
            ok = _needle_hit(c["also"], out)
            if not ok:
                tail += " ⚠️ **但报的不是这条**（`also` 判据未命中）"
        print(("  ✅ " if ok else "  ⛔ 未命中 ") + c["desc"] + "  → " + tail)
        hit += bool(ok)

    print()
    dirty = [p for p, b in before.items() if md5(p) != hashlib.md5(b).hexdigest()]
    leftover = [p for p in created if p.exists()]
    ok = not dirty and not leftover
    print(f"  命中 {hit}/{len(cases)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 全部复原' if not dirty else '❌ 未复原：' + '、'.join(map(str, dirty))}"
          f" · 临时件残留：{'✅ 无' if not leftover else '❌ ' + '、'.join(map(str, leftover))}")
    return 0 if (hit == len(cases) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
