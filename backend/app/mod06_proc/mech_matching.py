"""机械报表项目名规则；只按仓库名、展示名及可编辑别名匹配。"""

from sqlalchemy import select

from app.core.errors import MustReportError
from app.mod06_proc.models import ProcMechMatchRule


# 仅初始化规则表；解析时读取已存规则，不使用此表作匹配捷径。
SEED_ALIASES = {
    "新疆普康项目": ["新疆普康项目"],
    "乌兰察布项目": ["乌兰察布储能项目"],
    "内蒙宜化项目": ["内蒙宜化项目"],
    "南平项目": ["福建南平项目"],
    "龙源纸业项目": ["龙源纸业项目"],
    "安徽国风项目": ["安徽国风项目"],
    "新疆慧能项目": ["新疆慧能项目"],
    "晋江污泥项目": ["晋江污泥项目"],
    "许昌安彩项目": ["许昌安彩项目"],
    "宜昌项目": ["湖北宜昌项目"],
    "沭阳热电厂": ["沭阳项目"],
    "泗阳#4": ["2025泗阳锅炉"],
    "灵宝二期": ["灵宝二期项目"],
    "兰考金不换": ["兰考金不换项目"],
    "大唐雷州": ["广东大唐雷州项目"],
    "焦作佰利项目": ["2024年小微佰利"],
}


def project_rows(s):
    """取有仓库键的在建普通、小微档案；不读取项目全名。"""
    from app.mod01_projects import service as projects

    return [{"warehouse": p.warehouse_name, "display": p.disp or p.warehouse_name}
            for p in projects.all_projects(s)
            if p.warehouse_name and p.status == "active" and p.project_type in ("normal", "small")]


def list_rules(s):
    """展示全部已存规则和当前项目候选；不在读取时初始化或补写。"""
    projects = project_rows(s)
    displays = {p["warehouse"]: p["display"] for p in projects}
    return {"projects": projects, "items": [
        {"warehouse": r.warehouse_name, "display": displays.get(r.warehouse_name, r.warehouse_name),
         "aliases": list(r.aliases or [])}
        for r in s.execute(select(ProcMechMatchRule).order_by(ProcMechMatchRule.warehouse_name)).scalars()]}


def resolve_report_project(name, rules):
    """机械规则表精确查找；与付款计划的归一/包含匹配语义不同，不能复用其模糊匹配。重复名字拒绝。"""
    name = str(name or "").strip()
    matched = {r["warehouse"] for r in rules
               if name and name in {r["warehouse"], r["display"], *r["aliases"]}}
    if len(matched) > 1:
        raise MustReportError(f"报表项目「{name}」对应多个项目，请到规则配置修改匹配名称后重新预览")
    return next(iter(matched), "")


def save_rule(s, *, warehouse, aliases):
    """保存一个项目的报表名称；拒绝会让两个项目混写的重复名称。"""
    data = list_rules(s)
    if warehouse not in {p["warehouse"] for p in data["projects"]}:
        raise MustReportError("请选择有档案且在建的项目")
    values = list(dict.fromkeys(str(a).strip() for a in aliases if str(a).strip()))
    proposed = [r for r in data["items"] if r["warehouse"] != warehouse]
    display = next(p["display"] for p in data["projects"] if p["warehouse"] == warehouse)
    proposed.append({"warehouse": warehouse, "display": display, "aliases": values})
    for alias in {warehouse, display, *values}:
        resolve_report_project(alias, proposed)
    row = s.get(ProcMechMatchRule, warehouse)
    if row is None:
        row = ProcMechMatchRule(warehouse_name=warehouse)
        s.add(row)
    row.aliases = values
    s.flush()
