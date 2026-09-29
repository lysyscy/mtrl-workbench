#!/usr/bin/env python
"""`TAIL-175`（大表首列区固定）—— **交付面备份 ＋ 原型镜像** · 一次性（2026-09-29）。

**为什么必须镜像原型**：`BIG_THEAD` 是 `ui_parity` 的 **`U5` 逐字一致项**（原型 ⇄ 壳**各存一份**、
哈希比）⇒ 只改壳那一份 ⇒ `U5` 红；而 `U5` **没有"登记放行"这条机制**（它的设计就是"谁改一边 ⇒ 静默漂移"）。
⭐ 实测还多学一条：`U5` 的"段"= **一个顶层声明行起、到下一个声明行止**（末尾纯注释才削）⇒
   **加在 `EXT_THEAD` 与 `BIG_THEAD` 之间的那段注释也属于 `EXT_THEAD` 的段** ⇒ 注释也必须**两边同句**，
   否则报的是"`EXT_THEAD` 两边已不同"（第一次跑就是这么红的 —— 注释是段的一部分）。

**它做什么**（⛔ 只动这几处，逐字替换、每处**断言恰好命中一次**；已应用过的幂等跳过）：
  1. 原型 `BIG_THEAD` 的**前两个 `<th>`** 挂 `class="fl"`（与壳那一份**逐字一致**）；
  2. 原型样式块 `.fl` 那条之后补 `.fl + .fl{left:39px}`（第 2 列让开第 1 列的宽）——
     ⚠️ 原型**没有** `--fscale` 这一层（`TAIL-129` 只在壳侧）⇒ 这里写**定值 39px**（= 标准档的宽）；
     ⚠️ 原型那张表**没有** `data-sort-key` 属性（那是壳侧加的）⇒ 选择器⛔ 不能收窄（壳那份是 `.dt[data-sort-key=…]`）。
  3. `BIG_THEAD` 上方那段注释里的 `TAIL-175` 说明**逐字镜像**（理由见上）。
  4. **改前先备份**这 3 个文件到仓侧 `.workbuddy/backups/交付面-<时间戳>-TAIL175/`（本仓铁律）；
     ⚠️ 备份**不覆盖**已存在的（跑第二遍时若覆盖，就把"改前"的参照毁了）。

⚠️ 本件**改完不再用编辑器工具碰这个文件**（外部脚本写盘 ⇒ 编辑器里的旧副本会把改动盖回去）；
   跑完自校验：每处**恰好命中一次** ＋ 回读逐字比对 ＋ 字节增量 = 新增长度。

用法：`… _a175_proto.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
FACE = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用")
PROTO = FACE / "demo" / "材料报表自动化工作台-交互原型.html"
BASELINE = FACE / "PRD" / "验收" / "验收基线.json"
INDEX = FACE / "PRD" / "验收" / "用例索引.md"

COMMENT_OLD = (
    "      `applySorts` 按 `thead` 里 `<th>` 的下标定位列（`data-i`），两行表头会整体错位。 */\n"
    "const BIG_THEAD="
)
COMMENT_NEW = (
    "      `applySorts` 按 `thead` 里 `<th>` 的下标定位列（`data-i`），两行表头会整体错位。\n"
    "   ⭐⭐ `TAIL-175`（2026-09-29 用户裁定 `A`）：**首列区（序号 ＋ 项目名称）挂 `.fl`**（sticky-left）——\n"
    "      大表 `min-width:1620px`，往右填「机械费测算 / 合同价 / 产值累计」（手填 6 列正好在最右）时\n"
    "      首列区会跟着滚走 ⇒ **看不见自己在给哪个项目填**（会填错行）。\n"
    "      ⚠️ 两行表头 ⇒ 只有**第 1 行**的前两格是这两列（它们 `rowspan=\"2\"`，第 2 行里没有）；\n"
    "      ⚠️ 第 2 列必须让开第 1 列的宽，偏移规则在样式块 `.fl + .fl` 那一条（真机量过：两列严丝合缝）。\n"
    "      ⚠️ 本常量在**原型与壳各存一份**（`ui_parity` 的 `U5` 逐字一致项）⇒ **两边必须同改同句**。 */\n"
    "const BIG_THEAD="
)

#: （改哪件，说明，旧串，新串）—— ⛔ 每处都必须**恰好命中一次**；串里的 `{nl}` = 该件的换行符
EDITS: tuple[tuple[pathlib.Path, str, str, str], ...] = (
    (
        PROTO, "原型 BIG_THEAD 前两个 `<th>` 挂 `.fl`（与壳逐字一致）",
        'const BIG_THEAD=`<tr><th rowspan="2">序号</th><th rowspan="2">项目名称</th>',
        'const BIG_THEAD=`<tr><th rowspan="2" class="fl">序号</th><th rowspan="2" class="fl">项目名称</th>',
    ),
    (
        PROTO, "原型样式块补 `.fl + .fl` 偏移（本件无 `--fscale` ⇒ 定值 39px；选择器不收窄）",
        ".fl{position:sticky;left:0;background:var(--sf);z-index:1}",
        ".fl{position:sticky;left:0;background:var(--sf);z-index:1}{nl}"
        "/* 月度会大表的首列区（序号 ＋ 项目名称）两列一起钉 —— 第 2 列让开第 1 列的宽{nl}"
        "   （本件没有 `--fscale` 那一层 ⇒ 写标准档的定值；壳那份走 `calc(39px * var(--fscale))`） */{nl}"
        ".fl + .fl{left:39px}",
    ),
    (
        PROTO, "原型 BIG_THEAD 上方的 `TAIL-175` 注释**逐字镜像**（`U5` 的段含注释 ⇒ 必须同句）",
        COMMENT_OLD.replace("\n", "{nl}"),
        COMMENT_NEW.replace("\n", "{nl}"),
    ),
)


#: 跑坏过一次留下的**半成品**备份目录（`raw` 复用的 bug ⇒ 只应用了一半）—— 它们不是"改前"参照 ⇒ 清掉
HALF_BACKUPS: tuple[str, ...] = ("交付面-20260929-1014-TAIL175", "交付面-20260929-1015-TAIL175")


def verify() -> int:
    """逐条核**原型里现在到底什么样**（⛔ 不靠"脚本说写了"）。"""
    raw = PROTO.read_text(encoding="utf-8", newline="")
    checks = [
        ("BIG_THEAD 前两个 `<th>` 带 `fl`",
         'const BIG_THEAD=`<tr><th rowspan="2" class="fl">序号</th><th rowspan="2" class="fl">项目名称</th>'),
        ("样式块有 `.fl + .fl{left:39px}`", ".fl + .fl{left:39px}"),
        ("`TAIL-175` 注释已在", "⭐⭐ `TAIL-175`（2026-09-29 用户裁定 `A`）"),
    ]
    bad = 0
    for label, s in checks:
        n = raw.count(s)
        print(f"  {'✅' if n == 1 else '⛔'} {label}：命中 {n} 次")
        bad += 0 if n == 1 else 1
    return 1 if bad else 0


def tidy() -> int:
    """清掉半成品备份目录（⛔ 只删这两个具名目录；真正的"改前"参照是 `…-1013-TAIL175`）。"""
    for name in HALF_BACKUPS:
        p = REPO / ".workbuddy" / "backups" / name
        if p.exists():
            shutil.rmtree(p)
            print(f"✅ 已清半成品备份：{p.relative_to(REPO)}")
        else:
            print(f"⏭ 不在（已清）：{name}")
    keep = REPO / ".workbuddy" / "backups" / "交付面-20260929-1013-TAIL175"
    print(f"⭐ 保留的**改前**参照：{keep.relative_to(REPO)}（{'在位' if keep.exists() else '⛔ 不在'}）")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--verify", action="store_true", help="核原型现状（读盘逐条查）")
    ap.add_argument("--tidy", action="store_true", help="清半成品备份目录")
    args = ap.parse_args(argv)

    if args.verify:
        return verify()
    if args.tidy:
        return tidy()

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    backup = REPO / ".workbuddy" / "backups" / f"交付面-{stamp}-TAIL175"

    print(f"交付面：{FACE}")
    for p in (PROTO, BASELINE, INDEX):
        assert p.exists(), f"缺件：{p}"

    # ── 逐处核（⛔ 先核完再动任何一个文件）────────────────────────────────
    plan: list[tuple[pathlib.Path, str, str, str, str]] = []
    todo = 0
    for path, label, old_t, new_t in EDITS:
        raw = path.read_text(encoding="utf-8", newline="")
        nl = "\r\n" if "\r\n" in raw else "\n"          # ⚠️ 原型是 CRLF；按**它自己的**换行拼
        # ⚠️ 用 `str.replace`、⛔ 不用 `str.format` —— CSS 里的花括号会被当成占位符（`KeyError: 'position'`）
        old, new = old_t.replace("{nl}", nl), new_t.replace("{nl}", nl)
        if new in raw:                                   # 幂等：本处已应用
            print(f"  ⏭ 已应用：{label}")
            continue
        n = raw.count(old)
        assert n == 1, f"{label}：旧串命中 {n} 次（要**恰好 1 次**）—— 锚点已漂，先核再改"
        print(f"  ✅ 锚点唯一：{label}（换行 {'CRLF' if nl == chr(13) + chr(10) else 'LF'}）")
        plan.append((path, label, old, new, raw))
        todo += 1

    if not plan:
        print("\n（全部已应用 ⇒ 无事可做）")
        return 0
    if not args.write:
        print(f"\n（`--check`：⛔ 未写任何文件；要改 {todo} 处）")
        return 0

    # ── 备份（⛔ 改前；已存在则不覆盖 —— 覆盖会把"改前"的参照毁掉）──────────
    backup.mkdir(parents=True, exist_ok=True)
    for p in (PROTO, BASELINE, INDEX):
        dst = backup / p.relative_to(FACE)
        if dst.exists():
            print(f"  ⏭ 备份已在：{dst.relative_to(REPO)}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)
        print(f"  ✅ 已备份：{dst.relative_to(REPO)}")

    # ── 写盘（逐处，按字符长度核对）────────────────────────────────────────
    # ⚠️⚠️ **每处写前必须重读盘**（2026-09-29 实测踩到）：规划阶段读到的那份 `raw` 是**所有改动之前**的，
    #   拿它拼第二处 ⇒ **会把第一处的改动抹掉**（而"字符增量"自检照样过 —— 它比的也是那份旧 `raw`）。
    for path, label, old, new, _stale in plan:
        raw = path.read_text(encoding="utf-8", newline="")
        assert raw.count(old) == 1, f"{label}：重读后旧串命中 {raw.count(old)} 次"
        text = raw.replace(old, new, 1)
        path.write_text(text, encoding="utf-8", newline="")
        back = path.read_text(encoding="utf-8", newline="")
        assert back.count(old) == 0, f"{label}：写回后旧串仍在"
        assert back.count(new) == 1, f"{label}：写回后新串不是 1 次"
        assert len(back) == len(raw) + (len(new) - len(old)), f"{label}：字符增量不对"
        print(f"✅ 已写：{label}（+{len(new) - len(old)} 字符）")
        # ⚠️ 编辑器旧副本的坑：本件由脚本写盘 ⇒ 之后⛔ 别用编辑器工具再碰这个文件

    print("\n接着：`ui_parity`（`U5` 必须仍逐字一致）⇒ `pytest` ⇒ 全闸门")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
