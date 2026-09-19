"""集采供应商**自动匹配**（§6.6.3 · `DEV-J-01` 2026-09-14 改裁）—— 拿**候选池**去探测**单据名**。

⚠️ **反着匹配**：不是"先从单据名里切出简称、再拿去比全名"，而是 **拿候选池去探测单据名** ——
   因为单据名格式不受约束，**"简称在哪、多长"事先不可知**，只能反过来试。

⭐ 2026-09-19（`M5-5`）：本判定**原先在壳里**（`index.html` 的 `supPool` / `supFrags` / `supMatch`）
   ⇒ 搬到后端，两个理由：
   ① 它是**业务判定**（决定"预填 / 让选 / 手动"三条分叉）⇒ 按本仓纪律「判定一律后端」；
   ② 它含一条**曾经写错、且写错不报错**的规则（见 `frags_of`）—— 那种"悄悄换了语义"的规则
      只有在后端才钉得住（前端没有断言）。

⚠️ 准确**不靠算法**，靠"**多命中必须问人**"这道闸 —— 假阳性的代价只是**多问一次**，不会填错。
"""

from __future__ import annotations

#: 等级名（**给人看**；索引即等级 ⇒ 0 是"没命中"）。
LVL_NAMES: tuple[str, ...] = ("", "全名", "4 字片段", "3 字片段", "2 字片段")

#: ⚠️ **片段长度 = `FRAG_LEN_OFFSET - level`** 的那个 6。⛔ 改名 / 改值前先读 `frags_of` 的警告。
FRAG_LEN_OFFSET = 6

#: 探测等级数（① 全名 ② 4 字 ③ 3 字 ④ 2 字）。
MAX_LEVEL = len(LVL_NAMES) - 1


def frags_of(full: str, level: int) -> list[str]:
    """全名 → 该等级的**连续片段**（`level=1` ⇒ **全名整体**；否则**定长滑窗**）。

    ⚠️⚠️ **片段长度 = `6 - level`**（② 4 字 / ③ 3 字 / ④ 2 字）—— 写错这里会**静默改变等级语义**：
       壳里**曾经**写成 `level + 2` ⇒ ③ 变 5 字、④ 变 6 字 ⇒ **等级越高片段越长** ⇒
       "先长后短"的探测顺序**失去意义**（却照样能跑、不报错 ⇒ 这类错最贵）。
    ⚠️ 长度不足（全名比片段还短）⇒ 返回**空列表** ⇒ 该等级**天然不可能命中**
       （⛔ 不是"退化成全名"、也不是"拿全名去比"）。
    """
    s = str(full or "")
    if level == 1:
        return [s]
    n = FRAG_LEN_OFFSET - level
    if n <= 0 or len(s) < n:
        return []
    return [s[i:i + n] for i in range(len(s) - n + 1)]


def pool_of(rows, *, project_key: str) -> list[str]:
    """候选池 = **本项目**集采合同的「供应商」，按**全名去重**。

    `rows` 是**普通 dict**（`{"project_key":…, "supplier":…}`）—— 纯函数，不碰库（好测）。

    ⚠️ 去重**必需**：同一供应商常有多份合同 ⇒ 不去重就会"一家被数成多家" ⇒
       多命中弹窗里出现重复项、把"歧义"变成假的。
    ⚠️ 项目键 = **仓库名**（§2.7.4）—— 与 `jc_contract.project_id → project.warehouse_name` **同一键空间**。
    """
    k = str(project_key or "").strip()
    seen: set[str] = set()
    out: list[str] = []
    for r in rows:
        if str(r.get("project_key") or "").strip() != k:
            continue
        s = str(r.get("supplier") or "").strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def match_of(doc: str, pool) -> dict:
    """拿候选池探测单据名 ⇒ 命中的**最高等级那一批**。

    ⚠️ **先长后短**（level 1 → 4）：高等级**一命中就返回**，低等级**一律不看** ——
       否则"2 字片段"会把一大堆无关供应商扯进来（噪声随等级下降而爆炸）。
    ⚠️ 返回的 `cands` = **同等级内的全部命中**。多命中 = **歧义** ⇒ 由调用方**问人**；
       ⛔ 系统**绝不**取"最长的 / 第一个 / 最像的"（§6.6.3「明确不做」）。
    """
    d = str(doc or "")
    if not d:
        return {"level": 0, "level_name": "", "cands": []}
    for level in range(1, MAX_LEVEL + 1):
        hit = [full for full in pool if any(f and f in d for f in frags_of(full, level))]
        if hit:
            return {"level": level, "level_name": LVL_NAMES[level], "cands": hit}
    return {"level": 0, "level_name": "", "cands": []}


def row_pool_rows(session) -> list[dict]:  # pragma: no cover - 薄查库层，端点用
    """把 `jc_contract` 读成 `pool_of` 要的形状（`project_key` = 该合同所属项目的**仓库名**）。

    ⚠️ **一次查完**（⛔ 不逐行查项目名 = N+1）。
    """
    from sqlalchemy import select

    from app.mod01_projects.models import Project
    from app.mod11_jc.models import JcContract

    wh = {int(r[0]): str(r[1] or "") for r in session.execute(select(Project.id, Project.warehouse_name))}
    return [
        {"project_key": wh.get(int(c.project_id or 0), ""), "supplier": str(c.supplier or "")}
        for c in session.execute(select(JcContract)).scalars()
    ]


__all__ = ["LVL_NAMES", "FRAG_LEN_OFFSET", "MAX_LEVEL",
           "frags_of", "pool_of", "match_of", "row_pool_rows"]
