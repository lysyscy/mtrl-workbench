"""文档审计 2026-09-29 队列 · 第 3 条：`归档-历史单元条目.md`（**13415 行 / 858 KB**）切分。

## 为什么切

该件是 append-only 下沉归档（`## 下沉于 YYYY-MM-DD …` 共 44 节）。它**一天翻倍**（6487 → 13415 行，
2026-09-29 那批逐页 ＋ 各批下沉占了后半）。⚠️ 它**不是"文档病"**（只追加是对的，⛔ 不按内容审它）——
是**单文件规模**问题：搜一次要穿过 13415 行、单文件风险都在一处。

## 切在哪、切完放哪（⚠️ 两处都讲究）

- **切点 = 第一节 `## 下沉于 2026-09-23`**（它之前 = ≤ 2026-09-22 的下沉：5723 行）。
- **新件放 `plans/归档-历史单元条目-至20260922.md`**（⭐ **同级、同名系**）——
  ⚠️ 这是**故意的**：各尺子按 `.workbuddy/plans/*.md` / `.workbuddy/plans/归档-*.md` 这类 **glob** 认件
  （`tools/audit/audit_common.py`），同级同名 ⇒ 新件**自动落在同一套规矩里**（留痕档的宽免也照旧）；
  ⛔ 若塞进 `plans/archive/` 反而可能掉到白名单外。
- **两份都留指针**：新件末尾指向现行件；现行件**顶部补回标题 ＋ 索引**（原标题与前言随前半段留在新件里）。

## 字节纪律

⚠️ 该件含历史遗留的 `\r\r\n`（`_prune_ui_expected.py` 里记过的写盘坑）⇒ **一律 `newline=""` 读、原样写**，
⛔ 不做任何行内改写；本脚本只做「切 + 加头 + 加尾」。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_d3_archive_split.py --check` / `--write`
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLANS = ROOT / ".workbuddy" / "plans"
ARCH = PLANS / "归档-历史单元条目.md"
NEW = PLANS / "归档-历史单元条目-至20260922.md"
CUT_MARK = "## 下沉于 2026-09-23"          #: 第一节 09-23 之前 ⇒ 归新件


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    apply = a.write and not a.check

    raw = ARCH.read_text(encoding="utf-8", newline="")
    lines = raw.splitlines(keepends=True)
    print(f"现行件：{len(lines)} 行 · {len(raw) / 1024:.0f} KB · "
          f"{'CRLF' if chr(13) + chr(10) in raw else 'LF'}")

    if NEW.exists():
        print(f"⏭ `{NEW.name}` 已存在 ⇒ 视为已切过（幂等，⚠️ 要重切先手工处理）")
        return 0

    hit = [i for i, l in enumerate(lines) if l.startswith(CUT_MARK)]
    if not hit:
        print(f"⛔ 找不到切点标记 `{CUT_MARK}` ⇒ 停手（别猜）")
        return 2
    k = hit[0]
    head, tail = lines[:k], lines[k:]
    print(f"   切点：第 {k + 1} 行（第一节 `{CUT_MARK}…`）⇒ 前半 {len(head)} 行 · 后半 {len(tail)} 行")

    eol = "\r\n" if "\r\n" in raw else "\n"
    idx = [l.strip() for l in tail if l.startswith("## ")]
    new_tail = (eol + "---" + eol + eol
                + f"> ⚠️ **本件承接 ≤ 2026-09-22 的下沉**（`2026-09-29` 切分：文档审计第 3 条 ——"
                  f" 单件 13415 行 ⇒ 按切点一分为二，⛔ **一行未删**）。" + eol
                + f"> ⭐ **2026-09-23 起的下沉在现行件** = `.workbuddy/plans/归档-历史单元条目.md`。" + eol)
    new_head = (f"# 历史单元条目（归档 · append-only · **前半段**：至 2026-09-22）" + eol + eol
                + f"> ⚠️ `2026-09-29` 按文档审计第 3 条切分：本件 = 原 `归档-历史单元条目.md` 的"
                  f" **前 {len(head)} 行**（≤ 2026-09-22 的下沉）；⛔ **一行未删、一字未改**。" + eol
                + f"> ⭐ 2026-09-23 起 ⇒ `.workbuddy/plans/归档-历史单元条目.md`（搜「下沉于」两件都能搜到）。" + eol + eol)
    kept_head = (f"# 历史单元条目（归档 · append-only · **现行件**：2026-09-23 起）" + eol + eol
                 + f"> ⚠️ `2026-09-29` 按文档审计第 3 条切分：本件 = 原件的**后半 {len(tail)} 行**；"
                   f"原件的**前半段（≤ 2026-09-22）** 已移到同目录 `归档-历史单元条目-至20260922.md`"
                   f"（⛔ **一行未删、一字未改**，只是换了文件）。" + eol
                 + f"> ⭐ **本件包含以下下沉节（{len(idx)} 节）**：" + eol + eol
                 + "".join(f"- `{s}`" + eol for s in idx))

    if not apply:
        print(f"   🧪 干跑：新件 = 头部 {len(new_head)} 行 + 原前 {len(head)} 行 + 尾注 {len(new_tail.splitlines())} 行")
        print(f"   现行件 = 新头 {len(kept_head.splitlines())} 行（含 {len(idx)} 节索引）+ 原后 {len(tail)} 行")
        return 0

    NEW.write_text(new_head + "".join(head) + new_tail, encoding="utf-8", newline="")
    ARCH.write_text(kept_head + "".join(tail), encoding="utf-8", newline="")
    print(f"   ✅ 已切：`{NEW.name}` {len((new_head + ''.join(head) + new_tail).splitlines())} 行 · "
          f"现行件 {len((kept_head + ''.join(tail)).splitlines())} 行")
    print("   下一步：`doc_audit`/`audit_meta`/`audit_drift` 必须修 0 ＋ 抽查两件对「下沉于 2026-09-2x」都能搜到")
    return 0


if __name__ == "__main__":
    sys.exit(main())
