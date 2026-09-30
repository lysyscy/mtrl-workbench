#!/usr/bin/env python
r"""`TAIL-202`（i8 凭证「未绑即拒」）的**契约面 ＋ 台账**同批落纸（2026-09-30）。

**为什么要同批**（本仓铁律）：`TAIL-202` 改的是**用户可见的行为**（有身份却没绑 i8 ⇒ 抓取被拒）
⇒ ① 交付面那条 claim（`001-13`②）说的还是「查无此人 / 未登录 ⇒ 回落」，**不改成"有身份未绑 ⇒ 拒"
它就跟实现打架**（`T4/T7`＋`claim_audit` 的活）；② 尾巴做掉了要**三处同批销号**（§14.3 / §15 §一 / §15 §四）
＋ 两处计数（文头 ＋ §15 顶部）；③ `T6` 查「排期表里的编号必须能在台账里找到」。

**改什么**：
 1. 备份交付面那两个文件（⛔ 动交付面先备份）⇒ `.workbuddy/backups/交付面-<日期>-<时分>/`；
 2. `PRD/验收/验收基线.json` 的 `ACC-USR-MGMT-001/001-13` ⇒ **只改 claim 的 ② 那一段**（结构操作 ＋ round-trip 逐字节自检）；
 3. `PRD/验收/用例索引.md` 的 `ACC-USR-MGMT-001` 行 ⇒ 追加一句变更说明；
 4. 计划：`TAIL-202` **销号**（§14.3 改 ✅ / §15 §一 删行 / §15 §四 补行）＋ 两处计数 ＋ §0.4 ＋ §13.6 那句。

用法：`python tools/oneoff/_tail202_docs.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
FACE = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用")
ACC = FACE / "PRD" / "验收" / "验收基线.json"
IDX = FACE / "PRD" / "验收" / "用例索引.md"
BAK = ROOT / ".workbuddy" / "backups" / f"交付面-{_dt.datetime.now():%Y%m%d-%H%M}"

#: claim 里被替换的那一段（② 那半）＋ 换成什么
CLAIM_OLD = ("② 查无此人 / 未登录的路径 ⇒ 回落 `.env`（**过渡期口径**：定时抓取 / 命令行 / 测试进程都走这里）")
CLAIM_NEW = ("② ⭐⭐ **有身份（账号表里查得到这个人）却没绑 i8 ⇒ 拒绝抓取并给人话提示、⛔ 不回落**"
             "（2026-09-30 `TAIL-202` 起 —— 回落等于拿共享账号去登录 ⇒ **把同事的在线 i8 会话顶掉**、"
             "执行记录还记错人）；**没有身份**（未登录 / 查无此人 / 命令行 / 测试进程）⇒ 仍回落 `.env`"
             "（那里没有「人」）")

IDX_OLD = ("| `ACC-USR-MGMT-001` | — | 可移植 `_smoke` §9x　（⭐ **2026-09-25** 补判据点 `001-14`："
           "**未登录 ⇒ 写动作一律拒**、读放行 —— 用户裁定 A · §1.5.1） |")
IDX_NEW = ("| `ACC-USR-MGMT-001` | — | 可移植 `_smoke` §9x　（⭐ **2026-09-25** 补判据点 `001-14`："
           "**未登录 ⇒ 写动作一律拒**、读放行 —— 用户裁定 A · §1.5.1）"
           "　（⭐ **2026-09-30** `TAIL-202`：`001-13`② 的 claim 由「查无此人 / 未登录 ⇒ 回落」改成"
           "「**有身份却没绑 i8 ⇒ 拒绝抓取并提示、⛔ 不回落**；**没有身份** ⇒ 仍回落」—— 用户「全部按推荐」"
           "· 依据 =《说明书》§7.8） |")

# ── 计划 ────────────────────────────────────────────────────────────────
P1_OLD = "A 类 **3** 条 · B 类 0 · C 类 **0** · 已销号 **202**"
P1_NEW = "A 类 **2** 条 · B 类 0 · C 类 **0** · 已销号 **203**"
P2_OLD = ("A 类 **3** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **202** 条\n"
          "> ⭐ **2026-09-30**：`TAIL-64` 收口**销号**（⇒ §四）＋ **新立 `TAIL-202`**（i8 凭证「未绑即拒」）"
          "⇒ A 类**仍是 3 条**（`TAIL-188` / `TAIL-195` / `TAIL-202`）。")
P2_NEW = ("A 类 **2** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **203** 条\n"
          "> ⭐ **2026-09-30**：`TAIL-64`（收口）＋ `TAIL-202`（i8 凭证「未绑即拒」，**当日立、当日办**）"
          "**都已销号**（⇒ §四）⇒ A 类 **2 条**（`TAIL-188` / `TAIL-195`）。")
P3_OLD = ("② **尾巴 A 类剩 3 条**：`TAIL-188` / `TAIL-195` / **`TAIL-202`**（i8 凭证「未绑即拒」· M8）"
          "—— ⭐ `TAIL-64` 已于 **2026-09-30 收口销号**（⇒ §15 §四）")
P3_NEW = ("② **尾巴 A 类剩 2 条**：`TAIL-188` / `TAIL-195`"
          "—— ⭐ `TAIL-64`（收口）与 `TAIL-202`（i8 凭证「未绑即拒」）已于 **2026-09-30 销号**（⇒ §15 §四）")
P4_OLD = ("| `TAIL-202` i8 凭证「未绑即拒」 | M8（⭐ **必须在产包之前**） | **四问**：① **是前置**")
P4_NEW = "| `TAIL-202` i8 凭证「未绑即拒」 | ✅ **已办（2026-09-30）** ⇒ 见 §15 §四 | **四问**：① **是前置**"
DEL_ROW_202 = "| `TAIL-202` | "
HDR_SOLD = "| # | 事项 | 销号依据 | 日期 |"
TAIL_202_SOLD = (
    "| `TAIL-202` | ⚠️ **i8 凭证「未绑即拒」**：**有身份**（账号表里查得到这个人）却没绑 i8 ⇒ "
    "**拒绝抓取并给人话提示**，⛔ 不再回落 `.env` 的共享账号（i8 登录含**强踢** ⇒ 回落会把同事的在线会话顶掉、"
    "执行记录还记错人）；**没有身份**（未登录 / 查无此人 / 命令行 / 测试进程）⇒ **仍回落** | "
    "**销号依据** = 用户 2026-09-30「全部按推荐」选 `A` 案：① 依据 =《说明书》**§7.8**"
    "（「登录体系落地后…**未填即拒绝抓取并提示、不回落**」）—— 是**实现没跟上**，不是口径没定；"
    "② 落点 = `core/identity.py`（一处分支 ＋ 一处人话提示 · 消息里**不提** `.env`/变量名，守则 §3.1）"
    "＋ 壳两处「未绑定」说法（改密弹窗／查看密码弹窗 —— 原文写「回落 `I8_USER`」）；"
    "③ **契约面同批**：`验收基线.json` 的 `001-13`② claim ＋ `用例索引.md` 补变更说明（改前已备份）；"
    "④ 判据 = `tests/test_acc_usr_i8.py`（④ 新断言「有身边未绑 ⇒ 抛 `MustReportError`」＋ 墓碑两条："
    "壳上⛔ 不许再出现「回落 `.env`」；改前已跑：受影响 6 件 **53/53 绿**）| 2026-09-30 |")
Q_OLD = ("⭐ **口径已定（2026-09-30「全部按推荐」）**：i8 回落按 **A** 案 ⇒ 立 **`TAIL-202`**"
         "（**有身份但没绑 i8 ⇒ 拒绝抓取并提示**；**无身份**（脚本 / 测试）仍回落 `.env`）"
         "⇒ 已进 §15 §一 ＋ §14.3；✅ 小尾巴已修（`ops/selfcheck.ps1` 的注释**不再写条数** —— 免得再过期）。")
Q_NEW = ("✅ **i8 回落已办（2026-09-30）**：**有身份却没绑 i8 ⇒ 拒绝抓取并提示**（⛔ 不回落），"
         "**无身份**（脚本 / 测试 / 查无此人）**仍回落** ⇒ `TAIL-202` **当日立、当日办、当日销号**（⇒ §15 §四）；"
         "✅ 小尾巴已修（`ops/selfcheck.ps1` 的注释**不再写条数** —— 免得再过期）。")


def rd(p: pathlib.Path) -> tuple[str, str]:
    raw = p.read_text(encoding="utf-8", newline="")
    return raw.replace("\r\n", "\n"), ("\r\n" if "\r\n" in raw else "\n")


def wr(p: pathlib.Path, text: str, nl: str) -> None:
    p.write_text(text if nl == "\n" else text.replace("\n", nl), encoding="utf-8", newline="")


def sub1(text: str, old: str, new: str, what: str) -> str:
    n = text.count(old)
    assert n == 1, f"⛔ {what}：命中 {n} 次（期望 1）"
    print(f"   ✅ {what}")
    return text.replace(old, new, 1)


def del_line(text: str, prefix: str, what: str) -> str:
    lines = text.split("\n")
    hit = [i for i, ln in enumerate(lines) if ln.startswith(prefix)]
    assert len(hit) == 1, f"⛔ {what}：命中 {len(hit)} 行（期望 1）"
    print(f"   ✅ {what}（删第 {hit[0] + 1} 行）")
    del lines[hit[0]]
    return "\n".join(lines)


def ins_after(text: str, prefix: str, new_line: str, what: str) -> str:
    lines = text.split("\n")
    hit = [i for i, ln in enumerate(lines) if ln.startswith(prefix)]
    assert len(hit) == 1, f"⛔ {what}：锚行命中 {len(hit)} 行（期望 1）"
    print(f"   ✅ {what}（插在第 {hit[0] + 1} 行之后）")
    lines.insert(hit[0] + 1, new_line)
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    # ── 交付面：改前先备份（⛔ 铁律）
    if args.write:
        BAK.mkdir(parents=True, exist_ok=True)
        for src in (ACC, IDX):
            dst = BAK / src.name
            assert not dst.exists(), f"⛔ 备份已存在（不覆盖）：{dst}"
            shutil.copy2(src, dst)
        print(f"   ✅ 交付面已备份 ⇒ {BAK.relative_to(ROOT)}（2 件）")

    # ── 验收基线.json（⭐ 结构操作 ＋ round-trip 逐字节自检）
    raw = ACC.read_text(encoding="utf-8", newline="")
    obj = json.loads(raw)
    assert json.dumps(obj, indent=2, ensure_ascii=False).replace("\n", "\r\n") + "\r\n" == raw, \
        "⛔ round-trip 与原文**不是逐字节相同** ⇒ 格式假设错了，拒改（读法：newline=''）"
    # ⚠️ `cases` 是 **dict**（键＝用例号），而 `001-13` 这种**判据点号在各自用例下会重号**
    #    ⇒ 必须先定位到 `ACC-USR-MGMT-001` 再看它的 points（第一版按"遍历所有用例找 001-13"
    #    当场撞出 `AttributeError` —— 顺带证明"先看结构再写脚本"这条不是废话）。
    _case = obj["cases"].get("ACC-USR-MGMT-001")
    assert _case is not None, "⛔ `验收基线.json` 里找不到用例 `ACC-USR-MGMT-001`"
    hit = 0
    for pt in _case.get("points", []):
        if pt.get("id") == "001-13":
            assert CLAIM_OLD in pt["claim"], "⛔ 001-13 的 claim 里找不到要改的那一段"
            pt["claim"] = pt["claim"].replace(CLAIM_OLD, CLAIM_NEW, 1)
            hit += 1
    assert hit == 1, f"⛔ `001-13` 命中 {hit} 次（期望 1）"
    print("   ✅ 验收基线.json：`ACC-USR-MGMT-001/001-13` 的 ② 那半已改（＋round-trip 自检通过）")
    out = json.dumps(obj, indent=2, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"

    # ── 用例索引.md
    idx, nl_idx = rd(IDX)
    idx = sub1(idx, IDX_OLD, IDX_NEW, "用例索引.md：`ACC-USR-MGMT-001` 行补变更说明")

    # ── 计划：销号三处同批 ＋ 计数两处 ＋ §0.4 ＋ §13.6
    plan, nl_plan = rd(PLAN)
    plan = sub1(plan, P1_OLD, P1_NEW, "计划 文头计数（A 类 2 · 已销号 203）")
    plan = sub1(plan, P2_OLD, P2_NEW, "计划 §15 顶部计数 ＋ 说明")
    plan = sub1(plan, P3_OLD, P3_NEW, "计划 §0.4 的 A 类")
    plan = sub1(plan, P4_OLD, P4_NEW, "§14.3 `TAIL-202` 行 ⇒ ✅ 已办")
    plan = del_line(plan, DEL_ROW_202, "§15 §一 删 `TAIL-202` 行（已移进 §四）")
    plan = ins_after(plan, HDR_SOLD, TAIL_202_SOLD, "§15 §四 补 `TAIL-202` 销号行")
    plan = sub1(plan, Q_OLD, Q_NEW, "§13.6：i8 那条「未决」⇒ 已办")

    if not args.write:
        print("\n（干跑：⛔ 未写）")
        return 0
    ACC.write_text(out, encoding="utf-8", newline="")
    assert ACC.read_text(encoding="utf-8", newline="") == out, "⛔ 验收基线写回不一致"
    assert json.loads(ACC.read_text(encoding="utf-8"))["cases"], "⛔ 验收基线改坏了（解析不出）"
    wr(IDX, idx, nl_idx)
    assert rd(IDX)[0] == idx, "⛔ 用例索引写回不一致"
    wr(PLAN, plan, nl_plan)
    assert rd(PLAN)[0] == plan, "⛔ 计划写回不一致"
    print("\n✅ 已落盘：交付面 2 件（含备份）＋ 计划（计数×2 · §0.4 · §15 §一/§四 · §14.3 · §13.6）")
    print("⚠️ 接着必跑：`doc_audit.py`（T4 四态数字 / T6 排期↔台账）＋ `doc_audit.py --ui`（交付面四检）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
