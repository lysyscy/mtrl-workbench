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


class LogOut(BaseModel):
    id: int
    field: str
    old_value: str
    new_value: str
    note: str
    changed_by: str
    changed_at: str


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
