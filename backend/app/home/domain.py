"""看板（默认落地页）= 待办页 —— 9 项待办的**口径出口**（**纯函数**）。

判据 → `PRD/验收/验收基线.json` 的 `cases["ACC-HOME-TODO-001"]`。

⚠️ **本页不占模块号**：原型导读明写「看板 = 默认落地页，**不占模块号、不进附录 F**」
   ⇒ 没有 `MOD-*` 文件；**交互规格主人 = 原型 `V.home`**（`demo/`）。
⭐ **本页只做汇总**：每项数字**必须来自对应数据域的出口**（本模块**不重算**任何域的口径）。
"""

from __future__ import annotations

#: 9 项待办 —— **键 / 标签 / 去向 / 口径节**（键 = 与原型 `data-todo` 一致的把手名）
TODOS: tuple[dict, ...] = (
    {"key": "ntUnapproved", "label": "未审批通知书", "target": "/m03", "domain": "MOD-03",
     "cover": "§4.2.3", "todo": "去付款通知书页核验审批状态"},
    {"key": "ownership", "label": "归属待判定", "target": "/m01", "domain": "MOD-01",
     "cover": "§2.5.1", "todo": "去项目档案指定具体小微"},
    {"key": "planUnmatched", "label": "计划未匹配", "target": "/m04", "domain": "MOD-04",
     "cover": "§4.3.4", "todo": "去付款计划页核对未匹配行"},
    {"key": "jcPending", "label": "集采待确认", "target": "/m11", "domain": "MOD-11",
     "cover": "§6.5.3", "todo": "去集采台账确认三态标记"},
    {"key": "dfPending", "label": "差异待核对", "target": "/m12", "domain": "MOD-12",
     "cover": "§5.8.3", "todo": "去差异登记页核对"},
    {"key": "placeholder", "label": "占位行（待扶正）", "target": "/m01", "domain": "MOD-01",
     "cover": "§2.4.2", "todo": "去项目档案扶正（补真实仓库名）"},
    {"key": "fetchDue", "label": "本月尚未抓取", "target": "/m02", "domain": "MOD-02",
     "cover": "§3.1.3", "todo": "去抓取页按月抓取"},
    {"key": "fetchFail", "label": "最近一次抓取失败", "target": "/m02", "domain": "MOD-02",
     "cover": "§3.1.3", "todo": "看失败的表名与时间，重抓或走手动导入"},
    {"key": "printFail", "label": "打印投递失败", "target": "/m02", "domain": "MOD-03",
     "cover": "§4.6", "todo": "看失败的单据与时间，重新投递"},
)

#: ⚠️ 这些域**尚未实现**（M5 / M6 切片）⇒ 计数**记 0 并显式标注**，
#:    ⛔ **不得臆造、也不得把该项从看板上藏起来**（判据 `001-09`）。
UNIMPLEMENTED: tuple[str, ...] = ("jcPending", "dfPending")


def todo_keys() -> tuple[str, ...]:
    """9 项把手名（**顺序固定** —— 顺序也是契约：看板按此序展示）。"""
    return tuple(t["key"] for t in TODOS)


def normalize(counts: dict | None) -> dict[str, int]:
    """补齐缺失项为 0（**9 项恒在**：把手集合固定、不重不漏）。

    ⭐ **未实现域在这里被强制归 0**（不是靠调用方自觉）—— 判据 `001-09`：
       那两项必须记 0 并标注，⛔ 不得被任何外部传值绕过。
    """
    src = counts or {}
    return {
        k: (0 if k in UNIMPLEMENTED else int(src.get(k) or 0))
        for k in todo_keys()
    }


def dashboard(counts: dict | None) -> list[dict]:
    """→ 9 行待办：`{key,label,target,domain,cover,todo,count,unsupported}`（顺序 = `TODOS`）。"""
    fixed = normalize(counts)
    return [
        {**t, "count": fixed[t["key"]], "unsupported": t["key"] in UNIMPLEMENTED}
        for t in TODOS
    ]


__all__ = ["TODOS", "UNIMPLEMENTED", "todo_keys", "normalize", "dashboard"]
