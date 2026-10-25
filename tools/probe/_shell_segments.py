"""真机自检**段的注册表** —— 「哪几段 / 按什么顺序 / 为什么是这个顺序」的**唯一出处**（`TAIL-215` 批 1）。

## 为什么有它

`tools/probe/_shell_smoke.py` 此前把 39 段**依次写在 `main()` 里** ⇒ 两条病：
① **顺序约束只写在注释里**（㉟/㊱ 必须排在 ㉞ 之前 · ㉞ 必须最后 · ①②③ 必须在任何切页之前 ·
   ⑥→⑥b / ⑦→⑦′ / ⑩→⑩b 三对子步骤必须相邻）⇒ 新段插错位置**不会报错**，
   只会让别的段**静默读到被刷过的页面状态**（＝"判据自己瞎了、却看着是绿的"，本仓最贵那族病）；
② **每加一段都要改主文件**（689 行 · `T5` 黄）。

⇒ 本件把「段 / 顺序 / 理由」收成一张表，主文件只留**引导 ＋ 遍历 ＋ 汇总**。

## 字段

| 字段 | 含义 |
|---|---|
| `id` | 屏幕上打的那个段号（① ⑥b ㊱ …）—— ⛔ 不许重复 |
| `what` | 一句话：这一段验什么 |
| `phase` | `pre` = 开页之前 · `boot` = **开屏那一屏**（⛔ 任何切页之前） · `body` = 主流程 |
| `entry` | `模块:函数`（**每段一件**）或**直接给可调用** —— ⛔ `TAIL-215` 批 2 起**没有**「段函数放在编排件里」这一支（别把段代码塞回 `_shell_smoke.py`） |
| `page` | 它自己切/用的页（`—` = 不碰屏幕） |
| `net` | 会不会**拦断网络 / 刷新页面**（会 ⇒ 它跑完的页面状态不干净） |
| `after` | ⭐ **必须排在这些段号之后**（注释里那句约束的结构化版本） |
| `last` | ⭐ **必须是最后一段**（会把页面状态弄脏 ⇒ 后面的段全废） |
| `why` | ⭐ **为什么是这个位置**（空 = 位置无讲究） |

## ⚠️ 三条纪律

1. **顺序 = 本表次序**（唯一真源）—— ⛔ 别在 `_shell_smoke.py` 里再写"第几段做什么"。
2. 改本表 ⇒ 同批改 `backend/tests/test_shell_segments.py` 的**金标清单**（那是"段数守恒 · 逐段点名"的守卫，
   故意**独立于本表**：少了哪一段要**有人看见**，⛔ 不是自动跟上）。
3. 加一段 ⇒ ① 写段函数 / 外移件 ② 在下面加一条 ③ 跑 `tools/mut/_mut_segments.py`（反向灵敏度）。

⚠️ 本件**只登记、不执行**（执行在 `_shell_smoke.py` 的 `main()`）⇒ import 本件**不会**拉起浏览器。
"""

from __future__ import annotations

import dataclasses

#: 机址（**唯一出处**）—— `_shell_smoke` 的 `page.goto` 与 ㉘ 的"比公开只读端点"都用它
BASE = "http://127.0.0.1:8000"


@dataclasses.dataclass(frozen=True)
class Seg:
    """一段真机自检（见文件头字段表）。"""

    id: str
    what: str
    phase: str                                  # pre / boot / body
    entry: object                               # "模块:函数" / 直接给可调用
    page: str = "—"
    net: bool = False
    after: tuple[str, ...] = ()
    last: bool = False
    why: str = ""


# ---------------------------------------------------------------- 段函数（本文件里的适配）
def _live(page, errors):
    """㉘ 的适配壳 —— 本件的真判据仍是 `_shell_live.check(errors, base)`（⚠️ 它是**唯一签名不同**的一段）。

    ⛔ 刻意**不去改 `_shell_live.check` 的签名**：那会牵动它自己的调用点，而这里只是"把它接进表"。
    """
    from _shell_live import check as _c

    _c(errors, BASE)


# ---------------------------------------------------------------- ⭐ 注册表（**顺序就在这儿**）
#: ⚠️ 相位必须**成块**（pre* → boot* → body*，⛔ 不许交错）；`last=True` 恰好一条且必须在表末。
SEGMENTS: tuple[Seg, ...] = (
    # ---- phase=pre：**开页之前**
    Seg("⓪", "播种会话票（以在用管理员身份）", "pre", "_shell_session:check", "—",
        why="后面所有写动作的**前提**（不带票 ⇒ 写动作会被后端正当地拒掉）—— ⛔ 别删、别挪后"),
    Seg("㉒", "开发库卫生：自检/调试脚本的残留不许留", "pre", "_shell_dbhygiene:check", "库",
        why="与页面无关 ⇒ 放在开页之前跑，省一次等待"),

    # ---- phase=boot：**开屏那一屏**（⛔ 任何切页之前）
    Seg("①", "侧栏项数", "boot", "_shell_nav:check", "开屏",
        why="读的是**开屏那一屏** ⇒ 必须在任何切页之前"),
    Seg("②", "顶栏标题", "boot", "_shell_ttl:check", "开屏",
        why="同上（开屏那一屏）"),
    Seg("③", "数据层 NO / PJs（证明真拉到后端）", "boot", "_shell_data:check", "开屏",
        why="同上（开屏那一屏）"),

    # ---- phase=body：主流程（**次序 = 本表次序**）
    Seg("④", "m03 结构件（对照 `ui_parity` 口径）", "body", "_shell_m03:check", "m03"),
    Seg("⑤", "m01 渲染真数据（⛔ 不是「页面空着但不报错」）", "body", "_shell_m01:check", "m01"),
    Seg("⑦", "m05 付款流水与欠款：KPI 已撤成墓碑 ＋ 表在线 ＋ 后端欠款可取", "body", "_shell_m05:check", "m05"),
    Seg("⑦′", "台账「项目」面板展开/收起 round-trip", "body", "_shell_panel:check", "m05",
        after=("⑦",), why="同上：接着 ⑦ 那一屏真点 ⇒ 相邻且保序"),
    Seg("⑧", "m08 库存单据：全量行数 == 后端 ＋ **真滚轮**滚得动", "body", "_shell_m08:check", "m08"),
    Seg("⑨", "m06 过程资料：`procPj` 必须有值（加载时求值的坑已修）", "body", "_shell_m06:check", "m06"),
    Seg("⑩", "m07 收发结存与活动大表", "body", "_shell_m07:check", "m07"),
    Seg("⑩b", "m07 提取表「结余」列 == 后端 `balances`", "body", "_shell_m07bal:check", "m07",
        after=("⑩",), why="同上：接着 ⑩ 那一屏读 ⇒ 相邻且保序"),
    Seg("⑪", "m09 特殊费用（含 ⑪b 写路径净零往返）", "body", "_shell_m09:check", "m09"),
    Seg("⑫", "m14 规则配置（含 ⑫b/⑫c：剔除名单卡）", "body", "_shell_m14:check", "m14"),
    Seg("⑬", "m07 导出：**真拉一次 zip**（默认月两态 ＋ 有数据的月）", "body", "_shell_exp:check",
        "—（从页面上下文 fetch）"),
    Seg("⑭", "链路 B：待人工指认（真造库样本 ＋ 真点弹窗 ＋ 复原）", "body", "_shell_pend:check", "m01"),
    Seg("⑮", "链路 A ③-b：多仓库 ⇒ 选一个建行", "body", "_shell_arch:check", "m01"),
    Seg("⑯", "m02 i8 接入层：两张卡读真执行记录", "body", "_shell_m02:check", "m02/m01"),
    Seg("⑰", "m01 类型列人工覆盖", "body", "_shell_m01type:check", "m01"),
    Seg("⑱", "链路 C：兜底前先查 i8 仓库名单", "body", "_shell_ownwh:check", "m03"),
    Seg("⑲", "看板接真数据", "body", "_shell_home:check", "home"),
    Seg("⑳", "设置页与搬迁参数（无死控件）", "body", "_shell_legacy:check", "set/m02/m03"),
    Seg("㉑", "通用浮层 `fixed` 定位 ＋ 点命中", "body", "_shell_pops:check", "多页"),
    Seg("㉓", "m11 派生金额 == 后端派生值", "body", "_shell_m11:check", "m11"),
    Seg("㉔", "报错人话化（把 m01 导出**真拦成 500**）", "body", "_shell_err:check", "m01", net=True,
        why="⚠️ 自己拦网络，但 `finally` 里**放开** ⇒ 不会把后面的段拦死（已核）"),
    Seg("㉕", "上屏文案无内部编号 / 开发话术（含 ㉖ 说明块长度 · ㉙）", "body", "_shell_text:check", "17 屏"),
    Seg("㉘", "现行报表出口与通用导入退役（只读检查）", "body", _live, "—",
        why="⚠️ 唯一**签名不同**的一段（`check(errors, base)`）⇒ 用本文件顶上的 `_live` 适配"),
    Seg("㉗", "页级四态：先拖慢 ⇒ 「正在读取…」；再拦断 ⇒ 「没能取到 ＋ 重试」", "body", "_shell_states:check",
        "m09/m08", net=True,
        why="⚠️ 自己拦网络（两处），都 `unroute` 放开 ⇒ 不会把后面的段拦死（已核）"),
    Seg("㉚", "台账卡头那排按钮（`on` 态 ＋ 收起复原 ＋ 不许同名/溢出）", "body", "_shell_m05head:check", "m05"),
    Seg("㉛", "通知书空态与正常路往返", "body", "_shell_empty:check", "m03"),
    Seg("㉜", "大表「首列区固定」（吸附几何严丝合缝）", "body", "_shell_bigpin:check", "m07"),
    Seg("㉝", "m11 合同主表「行身份区固定」", "body", "_shell_jcpin:check", "m11"),
    Seg("㊲", "m11 重绘代价：**几何读次数与行数无关**", "body", "_shell_m11cost:check", "m11",
        why="⚠️ 必须排在 ㉞ 之前（㉞ 会拦断＋刷新）"),
    Seg("㉟", "表级虚拟滚动：本页内刷新**不跳滚动**", "body", "_shell_vskeep:check", "m08",
        why="⚠️ 必须排在 ㉞ **之前**：㉞ 会拦断 ＋ 刷新页面状态"),
    Seg("㊱", "接管缺口机器眼（够阈值却没接管的表）", "body", "_shell_vskeep:check_risk", "15 屏",
        why="⚠️ 必须排在 ㉞ 之前（㉞ 会拦断刷新）"),
    Seg("㉞", "启动失败横幅**不许盖住内容**（自己拦断 ＋ 刷新造出那个状态）", "body", "_shell_bootbar:check",
        "全页", net=True, last=True,
        why="⛔ **必须是最后一段**：它会拦断 ＋ `page.reload()`，并**故意把横幅留在屏上**（那条横幅会吃掉"
            "卡头按钮的点击）⇒ 它跑完之后，任何「要点卡头按钮」的段都验不准"),
)


__all__ = ["BASE", "SEGMENTS", "Seg"]
