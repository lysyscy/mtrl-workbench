"""`MOD-01` API 出入参（项目档案）。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ProjectOut(BaseModel):
    id: int
    project_type: str
    name_full: str
    warehouse_name: str | None = None
    disp: str
    phid: str
    status: str
    ord: int
    parent_shell_id: int | None = None
    match_keywords: list[str] = Field(default_factory=list)
    is_placeholder: bool = False


class CandidateOut(BaseModel):
    """项目候选（§2.7.4）：**键 = 仓库名 · 显示 = 展示名**；含归档排最后并标注。"""

    key: str
    display: str
    archived: bool = False
    placeholder: bool = False


class ProjectExportIn(BaseModel):
    """导出请求（`TAIL-04` · §7.1）。

    ⚠️ **收 id 列表，⛔ 不收"筛选条件"** —— 页面的筛选（状态 / 类型 / 全名·仓库名·展示名模糊搜）
      与**排序**（`pjSort`：自定义 `ord` ＋ 归档后置）都是**前端**算的 ⇒
      传条件就得在后端**再实现一遍** ⇒ **两套口径必打架**（本项目的旧账）。
      ⭐ 传 id 还顺带把**顺序**带上了（导出的行序 = 屏幕上的行序）。
    """

    ids: list[int] = Field(default_factory=list)


class CreateProjectRequest(BaseModel):
    project_type: Literal["normal", "shell", "small"]
    name_full: str = Field(..., description="项目全名")
    warehouse_name: str | None = Field(None, description="仓库名（壳不传；普通项目/小微不传则取占位名）")
    disp: str = ""
    phid: str = ""
    parent_shell_id: int | None = None
    match_keywords: list[str] = Field(default_factory=list)


class StatusRequest(BaseModel):
    status: Literal["active", "archived"]
    changed_by: str = ""


class OrdRequest(BaseModel):
    to_position: int | None = Field(None, description="填序号 = 插到那个位置（1-based）")
    direction: Literal["up", "down"] | None = Field(None, description="上移 / 下移 = 与相邻一行对调")


class UpdateProjectRequest(BaseModel):
    name_full: str | None = None
    disp: str | None = None
    match_keywords: list[str] | None = None
    changed_by: str = ""


class TypeRequest(BaseModel):
    """人工改**类型**（`TAIL-42`）—— 三类判定的**人工覆盖**路径。

    ⚠️ 合法域 = `normal` / `shell`（= 判定唯一出口 `classify_name` 的 `manual_override` 域）：
       **`small`（具体小微）不由人工指定** —— 它得挂在一个壳下面、还占一个仓库名，由链路产生。
    ⚠️ 改成「普通项目」时**必须**给 `warehouse_name`（普通项目靠仓库名做候选键，§2.7.4）——
       壳本身没有仓库名，⛔ 不许猜一个填上。
    """

    project_type: Literal["normal", "shell"]
    warehouse_name: str | None = Field(
        None, description="改成「普通项目」时必须给（该行挂哪个仓库；壳 → 普通只有这一条路）"
    )
    changed_by: str = ""


class LogOut(BaseModel):
    id: int
    field: str
    old_value: str
    new_value: str
    note: str
    changed_by: str
    changed_at: str


class TrailOut(BaseModel):
    """字段留痕（**最近若干条**，供 `m01` 页「修改留痕」卡）。

    ⚠️ 只含 §9.3 规定的两处：**项目全名 / 项目状态**（展示名与 `ord` 不留痕）。
    """

    at: str
    project: str = Field(..., description="展示名优先的项目标签")
    field: str = Field(..., description="name_full / status")
    field_label: str = Field(..., description="中文列名（前端表格直接显示）")
    before: str = ""
    after: str = ""
    by: str = ""
    note: str = ""


class OwnershipRequest(BaseModel):
    name_full: str = Field(..., description="付款通知书的「付款项目」全名（i8 只给全名）")
    doc_name: str = Field("", description="单据名称（壳全名时用它匹配关键词）")


class OwnershipResponse(BaseModel):
    kind: str
    target_id: int | None = None
    shell_id: int | None = None
    matched_ids: list[int] = Field(default_factory=list)
    keyword_to_add: str | None = None
    reason: str = ""
    settled: bool = False
    candidates: list[CandidateOut] = Field(default_factory=list, description="该壳下的具体小微候选")


class PromoteRowOut(BaseModel):
    """候选档案行（`TAIL-30`-③ 端点①）—— 人工指认要看见"有哪些行、都是什么"。"""

    id: int
    type: str = ""
    type_label: str = ""
    warehouse_name: str = ""
    disp: str = ""
    status: str = ""
    phid: str = ""
    is_placeholder: bool = Field(False, description="只有占位行能被扶正（§2.3.1 仓库名不可人工改）")


class PromoteCandidatesOut(BaseModel):
    full_name: str
    count: int = 0
    rows: list[PromoteRowOut] = Field(default_factory=list)


class PromotePendingOut(BaseModel):
    """`m01` 顶部入口的清单：**待人工指认的几条 ＋ 它来自哪一次抓取**。

    ⚠️ `source` 如实说明来源（⛔ 不装作"刚刚"）：清单来自**最近一次材料侧抓取**，
    而每一条的候选行与是否仍然成立，是**按当前档案现算**的（`dropped` = 已被解决而丢掉几条）。
    """

    found: bool = False
    items: list[dict] = Field(default_factory=list)
    source: dict = Field(default_factory=dict)
    dropped: int = 0


class PromoteRequest(BaseModel):
    """**人工指认的落库请求**（`TAIL-30`-③ 端点②）：把这条真实仓库名写到**指定的那一行**。

    ⚠️ `project_id` = **按 id 定位**（铁律 5/6：禁止用名字反查）；`full_name` 只是**一致性守卫**
    （防止"张冠李戴"把仓库名写到别的全名的行上），不用于定位。
    """

    project_id: int = Field(..., description="要写到哪一行（档案行 id）")
    warehouse_name: str = Field(..., description="本次报表里的**真实仓库名**（来自抓取回执，⛔ 不是人工编的）")
    full_name: str = Field("", description="本次指认的那个全名（一致性守卫用）")


class PromoteOut(BaseModel):
    """扶正结果（**成败都要给人话**：被拒时由 `MustReportError` 出一句中文原因）。"""

    ok: bool = True
    id: int
    old_warehouse_name: str = ""
    warehouse_name: str = ""
    disp: str = ""
    disp_followed: bool = Field(False, description="展示名原本沿用占位名 ⇒ 一并跟着换了")
    message: str = ""


class ArchivePendingOut(BaseModel):
    """`m01` 入口的「待人工建档」清单（`TAIL-45`）：**链路 A ③-b「≥2 个仓库」那一条**。

    ⚠️ `source` 如实说明来源（⛔ 不装作"刚刚"）：清单来自**最近一次「常用项目列表」同步**；
       `dropped` = 已被解决（人挑过 / 别处建过）而**当场丢掉**的条数。
    ⭐ `TAIL-190`（2026-09-29 真机报障）：丢掉的那几条**也要看得见** —— `dropped_items` 给出
       `{full_name, why, why_text, reason}`（**为什么丢 ＋ 该去哪**）。⚠️ 尤其是「壳下具体小微」那类：
       它**本来就不属本卡**（出路 = 建档向导）⇒ 只报一个 `dropped=2` 会让用户以为卡坏了。
    """

    found: bool = False
    items: list[dict] = Field(default_factory=list)
    dropped_items: list[dict] = Field(default_factory=list)
    source: dict = Field(default_factory=dict)
    dropped: int = 0


class ArchiveRowRequest(BaseModel):
    """**选定一个仓库 ⇒ 建行**（`TAIL-45`）。

    ⚠️ 这里**没有** `project_id`（行还不存在）；定位靠 `full_name` ＋ `warehouse_name` 这一对，
       而两者都**必须来自清单**（后端按当前档案现算后再校验，⛔ 不是"信前端传什么就写什么"）。
    """

    full_name: str = Field(..., description="要建哪一条（项目全名，来自「待人工建档」清单）")
    warehouse_name: str = Field(..., description="选定哪个仓库（**来自 i8 名单的候选**，⛔ 不许手填）")


class ArchiveRowOut(BaseModel):
    """建档结果（**成败都要给人话**：被拒时由 `MustReportError` 出一句中文原因）。"""

    ok: bool = True
    id: int
    name_full: str = ""
    warehouse_name: str = ""
    project_type: str = ""
    type_label: str = ""
    disp: str = ""
    message: str = ""
