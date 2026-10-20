"""`m01` **类型列 · 人工覆盖三类判定**的壳侧断言（`TAIL-42`）—— 离线静态。

**壳里只做两件事**：问用户选哪个 ＋ 把答案**原样**送给后端。
⛔ 判定与落库全在后端（`classify_name(manual_override=…)` 是判定唯一出口；改类型也只有一个出口）
   ⇒ 壳里再写一份三类判定 = 造出第二份口径（本仓铁律）。

⚠️ 这些是**静态检查**（壳里有没有那些接线点），**不证明运行时能跑**；
   运行时那一段由壳真机自检 `tools/probe/_shell_m01type.py` 覆盖（**点开弹窗、只看不点** —— 确认会改真数据）。
"""

from __future__ import annotations

from pathlib import Path


from tests.shell_src import SHELL, act_entry, api_entry, func_body  # noqa: F401  ← `P4`① 读取点收敛

# ⭐ 2026-10-03（`TAIL-219` 批 2b）：本件原先自带剪刀 `_fn`（"标记 A → 标记 B"）——
#    已**整把删掉**，取段改走壳的语义口径（函数 ⇒ `func_body` · 动作条 ⇒ `act_entry` · `API` 条目 ⇒ `api_entry`）。


def test_类型列的人工覆盖入口由钩子注入():
    """⭐ 切片里那一格是只读的（`${typeTag(p.type)}`）⇒ 入口只能在**渲染后注入**（`BIND.m01`）。

    - 认"这是不是一条真档案行"的判据 = 该行有带 `data-id` 的 `editStatus` 按钮（与别处**同一把尺子**）；
    - 认"哪一格是类型列"靠**单元格文字**（三个类型标签之一）⇒ ⛔ 不赌列序号（列序变了也不会错）。
    """
    assert "td.setAttribute('data-act', 'pjTypeOpen')" in SHELL
    assert '[data-act="editStatus"][data-id]' in SHELL, "要认真的档案行，⛔ 别给表头/别的表也注入"
    assert "TYPES.includes((c.textContent || '').trim())" in SHELL, "列位置要按文字认，⛔ 不按序号"
    assert "pjTypeOpen:t=>{" in SHELL and "data-id" in SHELL


def test_弹窗讲清范围与留痕且只有两个可选():
    """人工覆盖只讲操作范围与留痕；自动判定规则由域内核负责，不在弹窗复述。"""
    dlg = func_body("pjTypeDlg")
    assert "当前类型" in dlg and "PJ_TYPE_LABEL[p.type]" in dlg, "要显示当前真实类型"
    assert "修改类型会留痕" in dlg, "要告诉用户改动留痕（可查）"
    assert "这里只能改为普通项目或小微壳" in dlg, "要讲清可修改范围，具体小微不由人工指定"
    assert "opt('small'" not in SHELL and "opt('shell'" in SHELL and "opt('normal'" in SHELL, \
        "只给两个选项（普通项目 / 小微壳）"


def test_选普通项目才出现仓库名且空值当场拦下():
    """⚖️ 仓库名的规矩在**两端各拦一次**（壳里给人话、后端是判据）：
    选「普通项目」⇒ 才出现仓库名输入；不填 ⇒ 当场说清为什么（⛔ 别等后端 400）。"""
    dlg = func_body("pjTypeDlg")
    ok = act_entry("pjTypeOk")
    assert "pjTypeNew === 'normal' ?" in dlg and 'id="pjTypeWh"' in dlg, "只在该填的时候才出现输入框"
    assert "!wh" in ok and "必须填仓库名" in ok and "不猜" in ok, "空值要在壳里就讲清（后端那道判据仍在）"


def test_反向_壳里不另写三类判定且只有一个出口():
    """⛔ 反向两条：
    ① 壳里**不许**再写一份"含小微 ⇒ 壳"之类的判定（那是 `classify_name` 的活）；
    ② 改类型**只有一个出口** `API.pjType`（⛔ 别处不许直接打那个端点）。"""
    dlg = func_body("pjTypeDlg")
    assert "indexOf('小微')" not in dlg and "includes('小微')" not in dlg, \
        "弹窗里只需**解释**口径，⛔ 不许自己判一遍"
    assert SHELL.count("API.pjType(") == 1, "改类型端点只许有一处调用方（唯一出口）"
    api = api_entry("pjType")
    assert "'PUT'" in api and "/type" in api, "走 PUT .../type（与后端端点一致）"
