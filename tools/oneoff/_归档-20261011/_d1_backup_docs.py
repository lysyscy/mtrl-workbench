"""文档审计 2026-09-29 队列：第 1 条（备份收到 5 份）＋ 第 4 条（changelog 补今天）＋ 第 6 条（两个家写明分工）。

**为什么一次做三条**：三条都是**机械改动**、互不相干、都不碰代码 ⇒ 一个脚本 + `--check` 先干跑。

① **第 1 条（`backups/` 收到"留 5 份"）**：口径 = `README.md:70/96`「留最近 5 份 · 超出的 ⇒ 移进
   `_旧快照归档-YYYYMMDD/`」（⛔ **不删**）。现状 21 个目录、**16 个产自 2026-09-29**（逐页 11 批各一份）。
   ⇒ 按 **mtime 最新 5 个**保留，其余目录与顶层散件**移进** `_旧快照归档-20260929/` ＋ 写 `README.txt` 清单。
   ⚠️ `T20`（`audit_work.check_retention`）只数**非归档**顶层目录 ⇒ 移完应转绿；⛔ **一件都不删**。

② **第 4 条（`docs/changelog.md` 补 2026-09-29）**：它的自述职责 =「只记**使用可感知**的变化」
   （09-28 刚补过 8+2 条，09-29 那 11 批**一条没进** ⇒ 病 3「同一天就复发」）。
   ⚠️ 只写**用户能看见的**：⛔ 不写内部重构（如"零行为改动的注释订正"）。

③ **第 6 条（两个 scratch 家 / 两个记忆家）**：⛔ **只加说明、不动内容** ——
   `work/00-scratch/`（`T14` · TTL 14 天）vs `.workbuddy/scratch/`（活区 · `T20` · 自有 `README.md`）；
   `.codebuddy/memory/journal/*.md`（≤2026-09-27 = **已归档留痕**）vs `.codebuddy/memory/YYYY-MM-DD.md`（现行日档）。
   ⚠️ 两处都**追加**一节（不插队、不重排），把"哪个是现行的"写死。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_d1_backup_docs.py --check`
      `… --write`
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BK = ROOT / ".workbuddy" / "backups"
ARCH = BK / "_旧快照归档-20260929"
CHANGELOG = ROOT / "docs" / "changelog.md"
WORK_README = ROOT / ".workbuddy" / "work" / "README.md"
IDE_MEMORY = ROOT / ".codebuddy" / "memory" / "MEMORY.md"

KEEP = 5                      #: 口径：留最近 5 份
STAMP = "2026-09-29"


def crlf(text: str) -> str:
    return "CRLF" if "\r\n" in text else "LF"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", newline="")      # ⚠️ newline="" 锁字节（本仓血泪）


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="", errors="surrogateescape")


def nl(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


# --------------------------------------------------------------------- ① 备份收 5
def plan_backups() -> tuple[list[Path], list[Path]]:
    """**只动目录、⛔ 不动顶层散件** —— 实测（`tools/audit/shell_verify.py:24/72/89`）：
    `.workbuddy/backups/*_壳单文件基线.html` 是那把尺子的**默认基准**（它自己 `--snapshot` 时只留 5 份
    ⇒ 份数由它管）；顶层那 2 个 json 是 09-26 的留痕。⚠️ 把它们搬进子目录 ⇒ `glob`（非递归）扫不到
    ⇒ **尺子会判红"没有基线、要你建基线"** ✗。⇒ 本条只管 `T20` 数的那件东西 = **顶层目录数**。"""
    dirs = [d for d in BK.iterdir() if d.is_dir() and not d.name.startswith("_")]
    dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)     # 最新在前
    loose = sorted(f for f in BK.iterdir() if f.is_file())
    return dirs[KEEP:], loose


def do_backups(move: list[Path], loose: list[Path], apply: bool) -> None:
    """⭐ 2026-09-29 实修：**先把 mtime 抄下来再搬** —— 搬完再 `stat()` 会 `FileNotFoundError`
    （本脚本第一次跑就是这么崩的：目录已经移走了、清单还没写 ⇒ **半途而废**，
    ⇒ 凡"先动文件再写清单"的脚本，清单数据必须在动之前取完）。"""
    print(f"\n① `backups/` 收到「留 {KEEP} 份」"
          f"\n   保留（按 mtime 最新 {KEEP} 个）：")
    dirs = [d for d in BK.iterdir() if d.is_dir() and not d.name.startswith("_")]
    dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for d in dirs[:KEEP]:
        print(f"     ✓ {d.name}  （{datetime.fromtimestamp(d.stat().st_mtime):%Y-%m-%d %H:%M}）")
    mt = {p.name: p.stat().st_mtime for p in move}        # ⚠️ 搬家前取完
    print(f"   移进 `{ARCH.name}/`：{len(move)} 个目录")
    if loose:
        print(f"   ⛔ **顶层散件 {len(loose)} 个一律不动**（`*_壳单文件基线.html` 是 `shell_verify` 的默认基准"
              f"，它自留 5 份；json 是 09-26 留痕）")
    for p in move:
        print(f"     → {p.name}  （{datetime.fromtimestamp(mt[p.name]):%Y-%m-%d %H:%M}）")
    if not apply:
        return
    ARCH.mkdir(exist_ok=True)
    for p in move:                                    # ⚠️ **只搬目录**（散件是尺子的基准，见上）
        shutil.move(str(p), str(ARCH / p.name))
    have = sorted(x for x in ARCH.iterdir() if x.is_dir())      # 清单**按归档区实况**写（可重复跑）
    lines = [f"# 旧快照归档 · {STAMP}",
             "",
             "> 依据：`README.md:70/96`「留最近 5 份 · 超出的 ⇒ 移进 `_旧快照归档-YYYYMMDD/`」"
             "（`T20` 守上限）。",
             "> ⛔ **一件都没删** —— 全是 `shutil.move`；要还原就原路移回上一层。",
             f"> 归档于 `{datetime.now():%Y-%m-%d %H:%M}`（文档审计 2026-09-29 队列 · 第 1 条）。",
             "",
             f"共 **{len(have)}** 个快照目录（⚠️ 顶层散件 `*_壳单文件基线.html` / `*.json` **没动** ——"
             f" 前者的最新那份是 `shell_verify` 的**默认基准**，它自己自留 5 份）：",
             ""]
    for d in have:
        when = datetime.fromtimestamp(d.stat().st_mtime)
        lines.append(f"- `{d.name}/`（mtime {when:%Y-%m-%d %H:%M}）")
    (ARCH / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    print(f"   ✅ 已搬 {len(move)} 个（⛔ 未删）＋ 清单按归档区实况写（现有 {len(have)} 个目录）")


# ------------------------------------------------------- ② changelog 补 2026-09-29
LOG_BLOCK = [
    "## 2026-09-29",
    "",
    "- **月度会大表：往右填表不再丢行身份**（`TAIL-175`）：表头与数据行的「下标区」（序号 ＋ 项目名称）固定不滚走；",
    "  20 列横表往右填 6 个手填列时，能一眼看出在给哪个项目填。",
    "- **月度会大表 0 行时给空态**（`TAIL-174`）：不再是一张只剩三级表头的大空表，而是「为什么空 ＋ 下一步」。",
    "- **集采台账：往右填表不再丢行身份**（`TAIL-180`）：勾选框 / 序号 / 合同日期 / 材料名固定；",
    "  4 个可编辑列（付款方式 / 备注 / 存档号 / 寄回日期）在最右，横滚时行身份留在视野里。",
    "- **集采台账那枚「抓取采购合同信息」写清了后果**（`TAIL-181`）：点之前就知道它会登录 i8、**可能顶掉该账号的在线会话**",
    "  （同事正在用 i8 时要先择时）—— 此前它一个字提示都没有。",
    "- **「导出」页卡头只留真入口**（`TAIL-185`）：那枚点了必然空转的朴素导出已撤下（同卡的「导出（含数据透视表）」是真下载）。",
    "- **启动失败的提示条不再盖住页首**（`TAIL-182`）：原来它压在最上层，页首的卡头按钮**点不着**；现在它进正常布局、把内容往下推。",
    "- **`m01` 的「删除」不再假装能删**（`TAIL-177`）：点「确认删除」此前只说一句「尚未接通后端」；现在按钮置灰、",
    "  原因写在弹窗里看得见的地方。`m03` / `m05` 的同类说法一并订正（`TAIL-179`），并修掉一处「删了还能恢复」的错说法（其实**真删**）。",
    "- **两处状态色改回普通说明**（`TAIL-184` / `TAIL-186`）：`m08` 那句「系统会怎么表现」不再用成功绿、`m14` 那句口径说明不再用危险红",
    "  （红只给危险 / 错、绿只给「这一步已经做完」）。",
    "",
]


def do_changelog(apply: bool) -> None:
    text = read(CHANGELOG)
    print(f"\n② `docs/changelog.md` 补 {STAMP}（{crlf(text)} · {len(text.splitlines())} 行）")
    if f"## {STAMP}" in text:
        print("   ⏭ 已经有这一天了 ⇒ 跳过")
        return
    anchor = "## 2026-09-28"
    if anchor not in text:
        print(f"   ⛔ 找不到锚点 `{anchor}` ⇒ 停手（别猜）")
        sys.exit(2)
    eol = nl(text)
    block = eol.join(LOG_BLOCK) + eol
    print(f"   在 `{anchor}` **之前**插 {len(LOG_BLOCK)} 行（8 条使用可感知的变化）")
    if apply:
        write(CHANGELOG, text.replace(anchor, block + anchor, 1))
        print("   ✅ 已插")


# ----------------------------------------------------- ③ 两个 scratch 家 / 两个记忆家
WORK_NOTE = """
## 五、两个 scratch 家 / 两个记忆家（⭐ 2026-09-29 写明，防"不知道哪个是现行的"）

| 家 | 它是谁的活区 | 保留期 / 机器眼 | ⛔ 别搞混 |
|---|---|---|---|
| `.workbuddy/work/00-scratch/` | 我（Agent）在本区的草稿（`tmp-YYYYMMDD-主题.*` / `CB_MSG.txt`） | **TTL 14 天** · `T14` | 它是**本区**的，出区就按 §一 表升档 |
| `.workbuddy/scratch/` | 仓级**活区**（各尺子输出 / 一次性脚本 / 交付面取证） | **14 天** · `T20` · 索引 = 该目录 `README.md` | ⛔ 它不是文档层；**先看那边 `README.md` 再动手** |

**两个"记忆家"**（⛔ 都属留痕，只追加）：

| 家 | 是什么 | 现状 |
|---|---|---|
| `.codebuddy/memory/journal/*.md` | **早期**逐日日志（历史） | **停在 2026-09-27** ⇒ 视作**已归档留痕**，⛔ 别往里续写 |
| `.codebuddy/memory/YYYY-MM-DD.md` ＋ `MEMORY.md` | **现行**逐日日志 ＋ 长期记忆（IDE 侧） | ⭐ **要写日志就写这里**（当天的那个 `YYYY-MM-DD.md`） |
| `.workbuddy/memory/MEMORY.md` ＋ `MEMORY-细则.md` | 会话**注入档**（另一条线 · `journal/` 同家） | 口径/纪律的主人；⚠️ 与上面那家**不是同一份** |
"""

IDE_NOTE = """
---

## 附录 · 记忆家的分工（⭐ 2026-09-29 写明，文档审计第 6 条）

- ⭐ **要写今天的日志 ⇒ 写本目录当天的 `YYYY-MM-DD.md`**（现行日档）。
- `journal/*.md`（≤ **2026-09-27**）＝ **已归档留痕**：⛔ 别往里续写、别按它当现状读（税务：留痕里出现旧术语/旧数字是对的）。
- ⚠️ 另一条线：`.workbuddy/memory/MEMORY.md` ＋ `MEMORY-细则.md`（**注入档**，口径/纪律的主人）—— 与本目录**不是同一份**，
  ⛔ 别把纪律写进日档、也别把流水写进注入档。
"""


def do_memory_homes(apply: bool) -> None:
    for path, block, label in ((WORK_README, WORK_NOTE, "work/README.md（两个 scratch 家）"),
                               (IDE_MEMORY, IDE_NOTE, ".codebuddy/memory/MEMORY.md（两个记忆家）")):
        text = read(path)
        print(f"\n③ {label}：{crlf(text)} · {len(text.splitlines())} 行")
        if "2026-09-29 写明" in text:
            print("   ⏭ 已经写过了 ⇒ 跳过")
            continue
        eol = nl(text)
        print(f"   追加 {len(block.strip().splitlines())} 行（⛔ 只加说明、不动正文）")
        if apply:
            write(path, text.rstrip("\r\n") + eol + block.replace("\n", eol))
            print("   ✅ 已追加")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    apply = a.write and not a.check

    move, loose = plan_backups()
    do_backups(move, loose, apply)
    do_changelog(apply)
    do_memory_homes(apply)

    print("\n" + ("🔧 --write 已落盘" if apply else "🧪 --check（干跑，未落盘）"))
    print("   下一步：`tools/audit/audit_work.py`（看 `T20` 是否转绿）＋ `doc_audit`/`audit_meta`/`audit_drift` 必须修 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
