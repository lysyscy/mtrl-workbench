# -*- coding: utf-8 -*-
"""§四 契约同步（一次性 · 2026-09-18）：两条尾巴的**补点**。

① `ACC-PRJ-OWN-001` **+2 点**（`TAIL-41`「未命中清单」的两层新鲜度）
② `ACC-CFG-RULE-001` **+3 点**（`TAIL-40` 剔除规则**落库**的写侧：库→默认 / 唯一出口 / 拒绝路径）

⚠️ 走**结构操作**（`json.load` → 追加 → `dump(ensure_ascii=False, indent=2)`），禁手改 JSON 文本；
⚠️ `newline="\n"` —— 交付面文件是 **LF**，不写这个参数会在 Windows 上把整份 diff 掉（前车之鉴）。
⚠️ **幂等**：点已存在 ⇒ 不重复追加（只补缺的那几条）。
"""

import json
import pathlib

BASE = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\PRD\验收\验收基线.json")

OWN_NEW = [
    {"id": "001-10", "kind": "outcome", "cover": "§2.5.1",
     "claim": "**「未命中清单」只认最近一次付款通知书抓取**（靠运行记录里的 `notice_fetch` 标记认人，"
              "⛔ 不看 `target` 猜；**i8 取数失败 / 归属未走完 / 抓取成功三种结局都必须写标记**）——"
              "它不是「未走完」⇒ **清单为空**，⛔ **不回溯更早的记录**（原实现回溯最近 20 条 ⇒ 抓取成功后"
              "用户仍会对着**已经解决**的清单去补词 / 建小微：白干一场，还会往档案里塞错行）；"
              "⭐ 反证同样要成立：最近一次**又**变未走完 ⇒ 清单**回来**（那个「空」必须是判出来的，不是恒空）"},
    {"id": "001-11", "kind": "outcome", "cover": "§2.5.1",
     "claim": "清单里每一条**按当前档案现算**：复用链路 C **同一个出口** `resolve_ownership`"
              "（⛔ 不另写一份「够不够格」）⇒ 用户刚补过词 / 刚建过小微的那些行**当场不再出现**；"
              "还没建档的（要人去同步常用项目列表）**照旧留着**；⚠️ **读端点必须过这层过滤**"
              "（⛔ 不许「读一份当时的判定、原样端出去」—— 那等于把过期清单端给用户）"},
]

CFG_NEW = [
    {"id": "001-06", "kind": "outcome", "cover": "§4.2.2",
     "claim": "**剔除规则落库**（不再是模块常量）：**库里有 ⇒ 以库为准；库空 ⇒ 回落 `DEFAULT_RULES`**"
              "（＝ §4.2.2 那张表）⇒ 首装行为即符合口径、不必人工录一遍；配置页首次读取**幂等**灌一次"
              "（库非空 ⇒ 写 0 行）；⛔ **抓取管线不调它**（抓取路径保持**纯读**，库空即用出厂默认 ⇒ "
              "不因本功能改变任何抓取行为）"},
    {"id": "001-07", "kind": "outcome", "cover": "§4.2.2",
     "claim": "**判定唯一出口不变**：规则**从库读**（`classify.match_exclude_rule` 吃的是库行转出的"
              "`ExcludeRule`），⛔ 不在编排层另写一份剔除判定；同一批抓取**只读一次、两处共用**"
              "（挑需校验的行 ＋ 落库打标记）；**依赖单向** `mod14_config → mod03_notice`"
              "（⛔ 不得反向 ⇒ 成环）；**改规则不重算历史**（已产生的 `exclude_source=rule` 标记不动）"},
    {"id": "001-08", "kind": "must-report", "cover": "§4.2.2",
     "claim": "⛔ **非法写法一律明确拒、且给人话**（不得静默忽略、更不得静默写进去）："
              "未知规则类别 / **按「收款单位」配置**（集采走分类、不走剔除）/ 命中值为空 / "
              "命中值＝「资产处集中采购」；⚠️ 写侧**恒 HTTP 200 ＋ `ok` 标志**（拒绝是可预期的，"
              "那句中文必须给用户看），4 个端点齐（`GET`/`POST` + `PUT`/`DELETE`）"},
]


def _append(case: dict, new: list[dict], key: str) -> int:
    have = {p["id"] for p in case["points"]}
    added = 0
    for p in new:
        if p["id"] in have:
            print(f"    （{key}/{p['id']} 已存在 ⇒ 跳过）")
            continue
        case["points"].append(p)
        added += 1
    return added


def main() -> int:
    d = json.loads(BASE.read_text(encoding="utf-8"))
    print("asof（改前）=", d.get("asof"))

    for key, new in (("ACC-PRJ-OWN-001", OWN_NEW), ("ACC-CFG-RULE-001", CFG_NEW)):
        c = d["cases"][key]
        print(f"\n--- {key} ---")
        print("  source   =", str(c.get("source"))[:200])
        print("  criterion=", str(c.get("criterion"))[:200])
        before = len(c["points"])
        n = _append(c, new, key)
        print(f"  points: {before} → {len(c['points'])}（+{n}）")
        print("  →", [p["id"] for p in c["points"]])

    d["asof"] = "2026-09-18"          # 本轮确实改了基线 ⇒ 如实回填
    BASE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

    back = json.loads(BASE.read_text(encoding="utf-8"))
    print("\n=== 复核 ===")
    print("asof（改后）=", back["asof"], "| cases 数 =", len(back["cases"]))
    for key in ("ACC-PRJ-OWN-001", "ACC-CFG-RULE-001"):
        ids = [p["id"] for p in back["cases"][key]["points"]]
        print(f"  {key}: {len(ids)} 点 {ids}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
