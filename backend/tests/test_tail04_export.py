"""`TAIL-04` 成品文件写出（模板法）—— 收发结存切片的**离线接线断言**。

绑 `ACC-X-EXP-001/001-02`（导出文件名用**当前年月**、不得硬编码成某个固定月份）；
其余接线断言用 `@acc()` 显式声明不绑定（避免被"未绑定测试体检"误报）。

⚠️ 这里钉的三件事（都踩过）：
1. **成品名只有一处主人** —— 页面清单（`domain.zip_manifest`）与实际产出的文件名必须**同一个来源**；
   实测踩过：清单写 `…2026-08…`、真产物写 `…2026年8月…`（两处各写一份命名）。
2. **文件名随期间参数变**（⛔ 不许把某个月份写死）。
3. **三种失败都不产出文件、且把中文原因带回**（模板缺失/损坏 · 该月无数据 · 缓存级对账不过）
   —— ⛔ 绝不静默交付一个空文件或数字对不上的文件。

真机验证在 `tools/_verify_tail04.py`（连库跑 SQL 与成品逐分对账，**第三条独立路径**）与
`tools/_shell_smoke.py`（第 ⑬ 段，走 HTTP 真下载）。
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from app.core.errors import MustReportError
from app.mod07_setl import domain as D
from app.mod07_setl.models import SetlDetail
from app.report_export import resources as R
from app.report_export import service as EX
from app.report_export import setl_export as SE
from tests.acc_plugin import acc
from tests.m07_helpers import dataset

ROOT = Path(__file__).resolve().parents[2]
SHELL = (ROOT / "backend" / "app" / "web" / "index.html").read_text(encoding="utf-8")
API = (ROOT / "backend" / "app" / "mod07_setl" / "api.py").read_text(encoding="utf-8")


def _act(name: str) -> str:
    """取壳里 `ACT` 的某个动作体（`\\n <名>:` 起，**花括号配平** —— ⛔ 不用"下一个动作"当终点）。"""
    i = SHELL.find(f"\n {name}:")
    assert i >= 0, f"壳里找不到动作 `{name}:`"
    depth, k = 0, SHELL.find("{", i)
    assert k > 0, f"`{name}` 里找不到起始花括号"
    while k < len(SHELL):
        if SHELL[k] == "{":
            depth += 1
        elif SHELL[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    body = SHELL[i:k + 1]
    assert len(body) < 3000, f"`{name}` 取到 {len(body)} 字符 —— 配平可能跑偏"
    return body


# ============================================================== 001-02


@acc("ACC-X-EXP-001", "001-02")
def test_导出文件名随期间变且不硬编码月份():
    """`001-02` 导出文件名用**当前年月**，⛔ 不得硬编码成某个固定月份。"""
    # ① 随参数变（两个不同月份必须给出两个名字）
    a, b = D.zip_name("2026-08"), D.zip_name("2026-09")
    assert a != b, f"两个月份给出同一个文件名 ⇒ 疑似写死：{a}"
    assert "2026年8月" in a and "2026年9月" in b
    assert D.total_workbook_name("2025-12") == f"{D.ORG_NAME}2025年12月收发结存表.xlsx"

    # ② 非单月 / 空值 ⇒ **原样返回**（⛔ 不臆造一个月份，也不抛）
    assert D.period_label("") == "" and D.period_label("2026") == "2026"
    assert D.period_label("2026-8") == "2026-8", "不干净的单月不该被猜成 `2026年8月`"

    # ③ 端点把「页面所选年月」透传下去（否则永远导出同一个月的成品）
    assert '/api/m07/settlement/export' in API, "后端没挂导出端点"
    assert 'request.query_params.get("period")' in API, "导出端点没读 `period` ⇒ 导出的是固定月份"
    assert "/api/m07/settlement/export?period=" in SHELL, "壳侧没把当前核算年月传给导出端点"


# ============================================================== 接线（不绑判据点）


@acc()
def test_成品名只有一处主人且与实际产出逐字一致():
    """⭐ **清单（页面承诺）与实际产出必须同一个来源** —— 实测踩过两处各写一份命名。"""
    ym = "2026-08"
    rows = dataset((ym,))[SetlDetail]
    # ⚠️ 用**域内核的键名**（`D.WAREHOUSE_KEY`），⛔ 不写死「仓库」——写死就变成第二份键名约定
    manifest = D.zip_manifest([{D.WAREHOUSE_KEY: w} for w in ("甲仓", "乙仓")], ym)
    assert [m["name"] for m in manifest if m["kind"] == "warehouse"] == ["甲仓.xlsx", "乙仓.xlsx"]
    assert manifest[-1]["name"] == D.total_workbook_name(ym)

    import tempfile

    with tempfile.TemporaryDirectory(prefix="t04-name-") as td:
        p = Path(SE.build_zip(rows, Path(td) / "out", D.period_label(ym)))
        assert p.name == D.zip_name(ym), f"产出名 {p.name} != 清单承诺 {D.zip_name(ym)}"
        # 包内总表名也要与清单一致
        members = zipfile.ZipFile(p).namelist()
    assert D.total_workbook_name(ym) in members


@acc()
def test_模板闸门缺失或损坏时显式报错():
    """⭐ `ops/模板法导出-实测结论.md` §五 点名的实现侧硬性：模板缺失 ⇒ **必须显式报错**。"""
    with pytest.raises(MustReportError) as e1:
        R.require_template(R.TEMPLATE_DIR / "__不存在的模板__.xlsx")
    assert "模板缺失" in str(e1.value)

    # 损坏（内容与登记不符）⇒ 也要拒（云同步回退过两次，是真实风险）
    import hashlib
    import tempfile as _tf

    with _tf.TemporaryDirectory(prefix="t04-tpl-") as td:
        fake = Path(td) / "模板_收发结存表.xlsx"
        fake.write_bytes(b"not a real xlsx")
        with pytest.raises(MustReportError) as e2:
            R.require_template(fake)
        assert "登记不符" in str(e2.value)
    # 闸门登记的摘要必须与真实文件一致（否则正常导出会全线被拦）
    for name, want in R.EXPECTED_SHA256.items():
        got = hashlib.sha256((R.TEMPLATE_DIR / name).read_bytes()).hexdigest()
        assert got == want, f"`{name}` 与登记的 SHA256 不符 —— 实现在跑，但闸门会在下次拒做"


@acc()
def test_三种失败都不产出文件且带回中文原因():
    """⭐ 空数据 / 坏期间 ⇒ 显式拒；⛔ 绝不静默产出一个空文件（那会被当成"交付了"）。"""
    import tempfile

    # ① 空数据
    with tempfile.TemporaryDirectory(prefix="t04-empty-") as td:
        out = Path(td) / "out"
        with pytest.raises(MustReportError) as e1:
            SE.build_zip([], out, "2026年8月")
        assert "没有任何收发结存明细" in str(e1.value)
        assert not list(out.glob("*.zip")) if out.exists() else True, "拒做时不该留下 zip"

    # ② 期间格式非法（服务层显式报，⛔ 不猜一个默认月）
    from app.core.db import session_scope

    with session_scope() as s:
        with pytest.raises(MustReportError) as e2:
            EX.export_settlement(s, "九月")
        assert "格式不对" in str(e2.value)


@acc()
def test_壳侧导出按钮已接线且按content_type分流():
    """`zipSfjc` 必须**真下载**（不再只弹"尚未落地"），并按 `content-type` 分流失败原因。

    ⚠️ 断言必须**只钉 `zipSfjc` 这个动作自己的作用域** ——
       「导出尚未落地」那句在**别的页**上是对的（其余页仍走路径①模板填充，属 `TAIL-04` 未完部分），
       把它当全站特征来查 ⇒ 一改别处就误红（实测首跑踩到）。
    """
    act = _act("zipSfjc")
    assert "尚未落地" not in act, "`zipSfjc` 还是旧提示 ⇒ 按钮按下去拿不到文件"
    assert "/api/m07/settlement/export?period=" in act, "`zipSfjc` 没打导出端点"
    assert "x-export-filename" in act, "壳侧没读后端带出的文件名（那就是自己拼了一份命名）"
    assert "'application/json'" in act, "没按 `content-type` 分流失败原因"
    assert "createObjectURL" in act and ".download" in act, "没真的触发下载（拿不到文件）"
    # 后端两条分支都要在：成功给 zip、失败给 JSON＋中文原因
    assert "application/zip" in API, "成功分支不是 zip"
    assert '"ok": False' in API.replace("'", '"'), "失败分支没回 `ok:false`（壳就分不出流）"
