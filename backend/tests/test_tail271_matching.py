"""验证机械项目匹配不混淆同全名小微、不吞未匹配项目及编辑后的真实匹配效果。"""

import pytest
from app.core.errors import MustReportError
from app.mod06_proc.mech_matching import resolve_report_project
from tests.acc_plugin import acc


@acc()
def test_same_full_name_never_matches_and_edit_takes_effect():
    rules = [
        {"warehouse": "大唐雷州发电项目", "display": "大唐雷州", "aliases": ["广东大唐雷州项目"]},
        {"warehouse": "焦作百利项目", "display": "焦作佰利项目", "aliases": ["2024年小微佰利"]},
        {"warehouse": "沭阳热电厂", "display": "沭阳热电厂", "aliases": ["沭阳项目"]},
        {"warehouse": "泗阳百通4#锅炉项目仓库", "display": "泗阳#4", "aliases": ["2025泗阳锅炉"]},
    ]
    assert resolve_report_project("广东大唐雷州项目", rules) == "大唐雷州发电项目"
    assert resolve_report_project("2024年小微佰利", rules) == "焦作百利项目"
    assert resolve_report_project("2025泗阳锅炉", rules) == "泗阳百通4#锅炉项目仓库"
    assert resolve_report_project("沭阳项目", rules) == "沭阳热电厂"
    for name in ["第四工程公司 2024小微项目(XMCB2024030001)", "灵宝一期项目", "焦作武陟县", "广州水泥项目", "广东郁南水泥厂项目"]:
        assert resolve_report_project(name, rules) == ""
    rules[0]["aliases"] = ["新报表名称"]
    assert resolve_report_project("新报表名称", rules) == "大唐雷州发电项目"
    assert resolve_report_project("广东大唐雷州项目", rules) == ""
    assert resolve_report_project("大唐雷州", rules) == "大唐雷州发电项目"
    rules[1]["aliases"] = ["新报表名称"]
    with pytest.raises(MustReportError, match="多个项目"):
        resolve_report_project("新报表名称", rules)
