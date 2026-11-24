"""设备位置和计租归属共用的项目引用。项目档案始终通过 MOD-01 读取。"""
from dataclasses import dataclass

from app.core.errors import DataConflictError
from app.mod01_projects import service as archive


def project_index(db):
    return {row.id: row for row in archive.all_projects(db) if not row.is_shell}


@dataclass(frozen=True)
class ProjectRef:
    legacy: str
    id: int | None = None
    custom: str | None = None

    @classmethod
    def from_row(cls, row, prefix):
        label = "project_name" if prefix == "project" else prefix
        return cls(getattr(row, label), getattr(row, f"{prefix}_id"), getattr(row, f"{prefix}_custom"))

    def fields(self, prefix, *, label=None):
        return {label or prefix: self.legacy, f"{prefix}_id": self.id, f"{prefix}_custom": self.custom}

    def display(self, projects):
        project = projects.get(self.id)
        return (self.custom or "").strip() or (project.disp if project else None) or self.legacy

    def key(self):
        return self.id if self.id is not None else (self.custom or "").strip() or self.legacy

    def rental_name(self, projects):
        project = projects.get(self.id)
        return (project.disp if project else None) or self.display(projects)

    def response(self, prefix, projects, *, rental=False):
        project = projects.get(self.id)
        return {
            "project_name" if rental else prefix: self.rental_name(projects) if rental else self.display(projects),
            f"{prefix}_id": self.id,
            f"{prefix}_disp": project.disp if project else None,
            f"{prefix}_custom": self.custom,
        }


def requested_project(projects, label=None, project_id=None, custom=None):
    if project_id is not None and project_id not in projects:
        raise DataConflictError("所选项目档案不存在或不能关联，请刷新项目列表")
    custom = (custom or "").strip() or None
    if project_id is None:
        custom = custom or label
    legacy = custom or (projects[project_id].disp if project_id is not None else None) or label
    if not legacy:
        raise DataConflictError("请选择项目或填写自定义项目名称")
    return ProjectRef(legacy, project_id, custom)
