# -*- coding: utf-8 -*-
"""§四 契约同步（一次性）：① 改 `ACC-SETL-FETCH-001/001-10` ② 新增 `ACC-PRJ-AUTO-001`（链路 B）。

⚠️ 走**结构操作**（`json.load` → 改 → `dump(ensure_ascii=False, indent=2)`），禁手改 JSON 文本。
"""
import json
import pathlib

BASE = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\PRD\验收\验收基线.json")

CLAIM_001_10 = (
    "**陌生仓库**（导出里有、项目档案里没有）⇒ **自动建档 / 扶正**（§2.4.2 链路 B）："
    "能扶正就扶正（占位行 → 真实仓库名）、扶不了按全名新建行；结果**逐条显式列出**在抓取回执里；"
    "⚠️ 取不到仓库名单 / 单条建不了 ⇒ **降级不阻断**（数据照常落库，说明可稍后重抓）；"
    "⛔ 判定不了的一律**列出来要人看**、不臆造 —— 原「⛔ 不自动建档」的写法与《说明书》§2.4.2 相反，已作废"
)

AUTO = {
    "req": "—",
    "module": "MOD-01",
    "cover": ["§2.4.2", "§2.5", "§2.3.1"],
    "source": "**需新建**（2026-09-17 · `MOD-01` 能力 4「占位行扶正（链路 B）」原挂 `ACC-PRJ-LIST-001`，"
              "而该用例 7 点全是「候选 / 展示名」口径、无一条讲扶正 ⇒ 属**幽灵判据**；"
              "规则主人 =《说明书》§2.4.2 · §2.5 ＋《全自动建档-实施计划》§三 链路 B / §1.2 安全绳）",
    "criterion": "材料报表（收发结存 / 库存单据）遇陌生仓库时**自动**同步仓库名单并建档/扶正，"
                 "**不要求用户点任何东西**；能扶正就扶正、扶不了就建、判不了就列出来 —— 全程禁静默，"
                 "且建档失败不得拖垮抓取",
    "points": [
        {"id": "001-01", "kind": "outcome", "cover": "§2.4.2",
         "claim": "材料报表遇陌生仓库 ⇒ **自动**跑一次仓库名单同步并建档 / 扶正 —— "
                  "**不要求用户点任何东西**（原「报错、要求先手工同步项目」已废止）"},
        {"id": "001-02", "kind": "outcome", "cover": "§2.4.2",
         "claim": "**能扶正就扶正**：全名命中**占位行**（`未建仓-N`）⇒ 仓库名换成真实名；"
                  "展示名若沿用占位名，**一并跟着换**（否则屏幕上一直挂「未建仓-1」）"},
        {"id": "001-03", "kind": "outcome", "cover": "§2.5",
         "claim": "**扶不了就新建**：全名命中**壳** ⇒ 新建**具体小微**行（`parent_shell_id` = 该壳，"
                  "关键词留空待付款侧链路 C 补）；全名是**普通项目**且无行 ⇒ 新建**普通**行、带真实仓库名"},
        {"id": "001-04", "kind": "must-report", "cover": "§2.5",
         "claim": "⛔ **判不了的一律列出、不臆造**：全名查不到所属项目 / 该全名还没建档 / "
                  "同一全名命中 ≥2 条非壳档案（疑似没带「小微」的壳）/ "
                  "已有真实仓库名与本次不符（普通项目 ↔ 仓库 = 1 : 1）"},
        {"id": "001-05", "kind": "must-report", "cover": "§2.4.2",
         "claim": "**只对「已建档项目名下」的仓库建档** —— 未建档 ⇒ 不建、提示先跑一次"
                  "「同步常用项目列表」（安全绳：挡住 i8 里历史老项目被污染进档案）"},
        {"id": "001-06", "kind": "outcome", "cover": "§2.3.1",
         "claim": "⛔ **人工不得改仓库名**：扶正**只由系统对占位行**执行；"
                  "拿到真实仓库名的行再扶正 ⇒ **拒绝**（不静默改）"},
        {"id": "001-07", "kind": "must-report", "cover": "§2.4.2",
         "claim": "**建档失败不得拖垮抓取**：取不到仓库名单 / 单条建不了（如壳已归档）⇒ "
                  "**降级进回执**并说明，数据已落库不受影响；结果**逐条列出**（禁静默）"},
    ],
}


def main() -> int:
    d = json.loads(BASE.read_text(encoding="utf-8"))

    hit = False
    for p in d["cases"]["ACC-SETL-FETCH-001"]["points"]:
        if p["id"] == "001-10":
            p["claim"] = CLAIM_001_10
            hit = True
            break
    if not hit:
        print("!! 没找到 ACC-SETL-FETCH-001/001-10")
        return 1

    if "ACC-PRJ-AUTO-001" in d["cases"]:
        print("!! ACC-PRJ-AUTO-001 已存在（幂等：只改 001-10）")
    else:
        rebuilt: dict = {}
        for k, v in d["cases"].items():
            rebuilt[k] = v
            if k == "ACC-PRJ-NAME-001":
                rebuilt["ACC-PRJ-AUTO-001"] = AUTO
        if "ACC-PRJ-AUTO-001" not in rebuilt:
            print("!! 插入点没命中（ACC-PRJ-NAME-001 不存在？）")
            return 1
        d["cases"] = rebuilt

    # ⚠️ newline="\n"：本仓交付面文件是 **LF**；不写这个参数，Windows 上 write_text 会把 \n 翻成 \r\n
    #    ⇒ 整文件被 diff 掉（实测踩到）。同 MEMORY 那条「行尾不统一」纪律。
    BASE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

    # 复核：结构可读 + 改动落地
    back = json.loads(BASE.read_text(encoding="utf-8"))
    pts = back["cases"]["ACC-PRJ-AUTO-001"]["points"]
    old = [p for p in back["cases"]["ACC-SETL-FETCH-001"]["points"] if p["id"] == "001-10"][0]
    print("cases 数:", len(back["cases"]))
    print("ACC-PRJ-AUTO-001 点数:", len(pts))
    print("001-10 含「自动建档」:", "自动建档" in old["claim"],
          "· 仍含「不自动建档」:", "不自动建档" in old["claim"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
