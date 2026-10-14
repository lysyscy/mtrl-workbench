"""`TAIL-117` 批次 0「细读」：**颜色只承担语义**的离线判据（守则 §4.5 · §4.2）。

**本批查出来的病**（逐个数过全壳 **38 处** `tip ok` / `tip wn`）：两种**语义错位**——
  ⭐ 2026-09-29（`A9`/`A10` 逐页）**补记**：本闸门原先**只覆盖 `tip ok` / `tip wn`**，`tip dg`（危险红）
  **从没被审过** —— `A10` 在 `m14` 查出一处「口径说明挂了危险红」（见下面墓碑）。⇒ 三类色**一起**管：
  ① **"还没发生的事"用了成功绿**（`tip ok`）：导出确认弹窗里写「**将**生成 1 个文件…」、
     抓取弹窗里写「目前有 N 条 / 抓取**会**全量刷新」—— 事都还没做，却用了"成功"的颜色；
  ② **纯说明 / 引导 / 空态用了警示黄**（`tip wn`）：退出登录那句"业务数据不受影响"、
     集采子表那句"本合同无贸易工具 ⇒ 不启用该子表"、"本项目下暂无集采合同 ⇒ 请先去集采台账"…

**本批定的判法**（已写入守则 §4.5）：
  · `tip ok`（成功绿）**只用于「这一步已经做完了」的结果回执**；
  · `tip wn`（警示黄）**只用于「用户必须注意的风险 / 禁止项」**；
  · 其余（预告 / 机制说明 / 空态指路 / 安抚）一律 **普通 `tip`**。

⚠️ **能证伪**：把任一句改回 `tip ok` / `tip wn` ⇒ 本件必红（墓碑是**带上下文的整串**，⛔ 不裸搜类名 ——
   裸搜会把"这句话本身就是在讲它已改"的注释也算上）。
⚠️ 本件**只钉这 14 处**（能用得上的、最不可辩驳的）；剩下那些**判定保留**的都给了理由（见审计清单 §十 批次 0），
   ⛔ 别把它当成"全壳颜色都必须这样"的通用闸门 —— "这个黄是不是真警告"仍须人眼（守则 §4.5 判据栏就这么写的）。
"""

from __future__ import annotations

from tests.acc_plugin import acc
from tests.shell_src import SHELL

#: 本批改掉的 14 处：`(墓碑整串, 为什么它原来是错的)`
TOMBSTONES: tuple[tuple[str, str], ...] = (
    # ── 用了成功绿、但事还没做 ──
    ('class="tip ok" style="margin:0"><b>提交后：', "批量付款弹窗：还没提交，只是在讲后果"),
    ('class="tip ok" style="margin:0"><b>${m}</b> 目前有', "抓取弹窗：当前条数概览（还没抓）"),
    ('class="tip ok" style="margin:0">抓取会<b>全量刷新该月', "抓取弹窗：讲抓取会做什么（还没抓）"),
    ('class="tip ok" style="margin:0">将生成 <b>1 个文件</b>', "过程资料导出确认：文件还没生成"),
    ('class="tip ok" style="margin-bottom:8px">将导出', "提取导出确认：还没导出"),
    ('class="tip ok" style="margin:0">将生成 <b>1 个工作簿</b>', "欠款台账导出确认：还没生成"),
    ('class="tip ok" style="margin:0"><b>交付形态：</b>', "收发结存：交付形态说明"),
    ('class="tip ok" style="margin:10px 0 0"><b>上次值带入：</b>', "活动大表：预填机制说明"),
    # ── 用了警示黄、但只是说明 / 引导 ──
    ('class="tip wn" style="margin:0">退出后回到', "退出登录弹窗：安抚性说明，不是警告"),
    ('class="tip wn" style="margin:0">本合同<b>无贸易公司</b>', "集采子表：口径说明，不是警告"),
    ('class="tip wn" style="margin:0"><b>本项目下暂无集采合同</b>', "空态 ＋ 指路，不是警告"),
    ('class="tip wn" style="margin-bottom:10px">按 <b>${esc(lvlName)}</b>', "供应商多命中：结果说明，不是警告"),
    # ── ⭐⭐ 2026-09-29（`A10` 逐页 · `m14`）：**危险红用在了"口径说明"上** ──
    #    原文「**分类只有三类**（机械 / 集采 / 辅材），**没有「其他」类**…」是**陈述事实**，不是危险 / 错误；
    #    ⚠️ 同页 1545 那条**禁止项**（"不得配置收款单位 = 资产处集中采购"）用的是 `tip wn`（黄）—— 那才对。
    ('class="tip dg" style="margin:0"><b>分类只有三类</b>',
     "规则配置页：口径说明挂了**危险红**（红只给危险 / 错；说明一律普通 `tip` —— 同页那条真禁止项用的是黄）"),
    # ── ⭐ 2026-09-29（`A9` 逐页 · `m08`）：**漏网的一处**（同款病，批次 0 当时没扫到）──
    ('class="tip ok" style="margin:0"><b>已验证：</b>', "库存单据：抓取后调整单仍保留 —— **机制说明**，不是"
     "「这一步已经做完」的回执（守则 §4.5 判法原文：预告 / 机制说明 / 空态指路 / 安抚 一律普通 `tip`；"
     "同批次 0 的「交付形态」「上次值带入」两处）"),
)


@acc("ACC-UI-SHELL-001", "001-24")
def test_颜色语义错位不许回来():
    """⭐ 上面那 14 处（本节只列了不重复的墓碑串）**不许**再挂回成功绿 / 警示黄。

    ⚠️ 判法 = **整串墓碑**（带上下文）。⛔ 别改成"数 `tip ok` 的个数"那种写法 ——
       个数会随页面增减漂，而且它拦不住"本来该是普通提示、却换了个位置又挂上绿色"。
    """
    bad = [f"{tomb!r}（{why}）" for tomb, why in TOMBSTONES if tomb in SHELL]
    assert not bad, (
        "颜色语义又被用错了（守则 §4.5：绿＝已完成 / 黄＝风险）：\n      " + "\n      ".join(bad))
    # MOD06改为同窗选项目，其范围说明同样不能预告成功绿或警示黄。
    proc = SHELL[SHELL.index("const procExpDlg=()=>"):SHELL.index("const procExpSelection=()=>")]
    assert '<div class="tip">导出所选项目' in proc
    assert 'class="tip ok"' not in proc and 'class="tip wn"' not in proc
    # 台账ZIP预览仍存在，保持原观测面。
    for tail in ("逐月欠款台账_${ym}.zip",):
        i = SHELL.find(tail)
        assert i > 0, f"找不到 {tail!r} 那段导出预览（落点变了？）"
        seg = SHELL[max(0, i - 260):i + 40]
        assert 'class="tip ok"' not in seg, f"{tail!r} 那段导出预览又用了成功绿（事还没做）"


@acc("ACC-UI-SHELL-001", "001-25")
def test_壳不许替域挑颜色():
    """⭐ 通用导入面 ① 步那三句**域自报文案**（`note` / `keep_note` / `memory`）**一律普通 `tip`**
    （用户 2026-09-27 就"壳替域挑颜色"这一格裁定 `A`）。

    ⚠️ 为什么这是错的：三句文本**全由域给**，壳**不知道域写了什么**，却按**字段名**挑颜色
       （`keep_note` → 警示黄 · `memory` → 成功绿）⇒ 同一个域的三句话长出三种颜色（守则 §4.5）。
    ⚠️ **能证伪**：把任一处改回 `tip wn` / `tip ok` ⇒ 本件必红。
    """
    for tomb in ('<div class="tip wn">${esc(sch.keep_note)}</div>',
                 '<div class="tip ok">${esc(IMP.memory)}</div>'):
        assert tomb not in SHELL, \
            f"壳又在替域挑颜色了：{tomb!r} —— 域自报文案一律普通 `tip`（要分语气走 B 案：域自报 `note_kind`）"


@acc("ACC-UI-SHELL-001", "001-26")
def test_判法本身写进了守则():
    """⭐ 本批的**判法**（"绿只用于已完成 / 黄只用于风险"）必须留在守则 `§4.5` 里 ——
    ⛔ 只改代码不写清判法 ⇒ 下一个人会照着旧习惯再把绿色挂到"将要发生"的说明上。

    ⚠️ 判法 = 守则正文里必须出现这条口径的**整句特征串**（⛔ 不判它写在哪一栏）。
    """
    import pathlib

    rule = (pathlib.Path(__file__).resolve().parents[2]
            / "docs" / "guides" / "frontend-design.md").read_text(encoding="utf-8")
    assert "只用于" in rule and "已经做完" in rule, "守则 §4.5 里没写「绿只用于已经做完」这条判法"
    assert "禁止项" in rule, "守则 §4.5 里没写「黄只用于风险 / 禁止项」这条判法"
