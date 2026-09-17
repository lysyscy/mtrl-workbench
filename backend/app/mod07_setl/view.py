"""`MOD-07` 收发结存月报页的 HTML 装配（**服务端渲染**）。

规范：
- 五段骨架一律走 `page.render_list_page`（口径说明 → 指标区 → 筛选栏 → 数据区 → 空态提示行）
- 列**不写字面量**：一律来自 `domain.SETL_COLUMNS`
- 合计行 / 空态行的跨列数由**表头列数派生**（不写死数字）
- 用户输入一律经 `esc()` 出口；产出物清单**实时算**（份数随仓数）

⚠️ 口径说明块**恒为 1 个**（设计规则 `R1`）；不写进度、不复述取值。
⚠️ 本页**不得**出现「列设置 / 列宽 / 提醒 / 督办」（`NG-01` `NG-02` `NG-04`）—— 由 `domain.boundary_violations` 钉住。
"""

from __future__ import annotations

from decimal import Decimal

from app.core.nav import NAV
from app.mod03_notice.page import BASE_CSS, esc, render_list_page
from app.mod07_setl import domain as D
from app.mod07_setl import extract as X

PAGE_ID = "m07"
TITLE = "收发结存月报"

TIPS = (
    "**本表只有两个用途**（§5.3.1）：① 总公司资产处每月要；② 会议大表里**提取焊材和气体**。",
    "**认项目只靠「仓库名」**：本表没有「项目全名」列 —— 找不到即「陌生仓库」，去项目档案处理（§2.7.4）。",
    "**交付形态**：分仓库表 ＋ 原表加数据透视表，**打包 zip**；金额按 2 位小数对平、**容差 0**（§5.3.2）。",
    "**抓取只允许单月**（§9.2），且会**登录 i8 并强踢在线用户** —— 抓前须二次确认，失败不自动重试登录（D9）。",
)

EXTRA_CSS = """
.dlg{border:1px solid var(--bd);border-radius:8px;padding:14px 16px;background:var(--sf);max-width:560px}
.dlg::backdrop{background:rgba(0,0,0,.28)}
.dlg h4{margin:0 0 8px;font-size:14px}
.hd{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.hd h1{font-size:18px;margin:0}
.hd nav{margin-left:auto;display:flex;gap:10px;flex-wrap:wrap}
.hd nav a{color:var(--pri);text-decoration:none;font-size:13px}
.warn{border:1px solid var(--wn-bd);background:var(--wn-l);color:var(--wn-d);padding:8px 12px;border-radius:6px;margin:8px 0}
"""


def money_text(value) -> str:
    """金额显示（千分位 · 2 位小数）；空值 ⇒ 空串（**不臆造 0**）。"""
    if value in (None, ""):
        return ""
    try:
        return f"{Decimal(str(value)):,.2f}"
    except Exception:  # noqa: BLE001 - 非金额列一律原样
        return str(value)


def _nav_html() -> str:
    return "".join(f'<a href="{esc(h)}">{esc(t)}</a>' for h, t in NAV)


def _cell_html(row: dict, col: dict) -> str:
    key = col["key"]
    if key == D.CHECK_KEY:
        return f'<span class="tag {D.check_level(row)}">{esc(D.check_text(row))}</span>'
    if col["type"] == "num":
        return esc(money_text(row.get(key))) if key in D.AMOUNT_KEYS else str(row.get(key) or 0)
    return esc(row.get(key))


def _rows_html(rows: list[dict]) -> str:
    body: list[str] = []
    for row in rows:
        tds = "".join(
            f'<td class="{_cell_cls(c)}">{_cell_html(row, c)}</td>' for c in D.SETL_COLUMNS
        )
        body.append(f"<tr>{tds}</tr>")
    return "".join(body)


def _cell_cls(col: dict) -> str:
    if col["key"] == D.CHECK_KEY:
        return "ctr"
    return "num" if col["type"] == "num" else ""


def _summary_row(row: dict) -> dict | None:
    """合计行：行数与四个金额列给值，校验格给**对合计值本身**的判定（域内核算，不在此重算）。"""
    if not row:
        return None
    out = {c["key"]: "" for c in D.SETL_COLUMNS}
    for key in D.SUM_KEYS:
        out[key] = money_text(row.get(key))
    out[D.WAREHOUSE_KEY] = D.TOTAL_LABEL
    # ⚠️ 合计行的格子由 `render_list_page` **统一转义**（`_cells` 不带类）⇒ 这里只给纯文字，
    #    不得塞 HTML（塞了会被转义成字面量）。
    out[D.CHECK_KEY] = str(row.get(D.CHECK_KEY))
    return out


def _period_input(state: dict) -> str:
    """核算年月 —— 本页**只声明「月」**（原型同款：`modes:['月']`）。"""
    return (
        '<input name="period" style="min-width:150px" '
        f'value="{esc(state.get("period") or "")}" placeholder="YYYY-MM">'
    )


def _counts_pill(counts: dict) -> str:
    """三项计数（行 / 仓 / 文件）—— **一律实时算**（001-07）。"""
    return (
        '<span class="pill">%s 仓 · %s 行 · %s 文件</span>'
        % (counts.get("warehouses"), counts.get("rows"), counts.get("files"))
    )


def fetch_dialog_html(default_month: str, back: str = "/m07") -> str:
    """「按月抓取」弹窗 —— **默认月份 = 本页当前所选核算年月**（001-06），可改。"""
    from app.mod02_i8.fetch_task import CONFIRM_TOKEN, KICK_WARNING

    return (
        '<dialog class="dlg" id="fetchDlg">'
        f"<h4>按月抓取 · {esc(D.CHANNEL)}（`API-02`）</h4>"
        '<form method="post" action="/m07/fetch">'
        f'<input type="hidden" name="back" value="{esc(back)}">'
        '<div class="fi"><label>核算年月（**单月**：起止同月）</label>'
        f'<input id="fetchMonth" name="month" value="{esc(default_month)}" placeholder="YYYY-MM"></div>'
        f'<div class="warn">{esc(KICK_WARNING)}</div>'
        '<label class="sm"><input type="checkbox" name="confirm" '
        f'value="{esc(CONFIRM_TOKEN)}"> 我已知晓**会强踢在线用户**，确认抓取</label>'
        '<div style="margin-top:10px">'
        '<button class="btn" type="button" '
        'onclick="document.getElementById(\'fetchDlg\').close()">取消</button>'
        '<button class="btn pri" type="submit" data-act="fetchOne">开始抓取</button>'
        "</div></form></dialog>"
    )


def zip_dialog_html(manifest: list[dict], zip_name: str) -> str:
    """「导出分仓库 zip」弹窗 —— 列出**产出物清单**（份数随仓数实时算，001-08）。"""
    items = "".join(
        f'<tr><td class="ctr">{i}</td><td>{esc(m["name"])}</td>'
        f'<td>{"分仓库工作簿" if m["kind"] == "warehouse" else "总表（含透视表）"}</td></tr>'
        for i, m in enumerate(manifest, 1)
    )
    return (
        '<dialog class="dlg" id="zipDlg">'
        f"<h4>导出分仓库收发结存 zip · {esc(zip_name)}</h4>"
        f'<div class="mut" style="margin-bottom:8px">共 <b>{len(manifest)}</b> 个文件 ＝ '
        "分仓库工作簿（每仓一份）＋ 总表（内含**真·可操作数据透视表**，求和项：期初 / 收 / 发 / 结存金额）。</div>"
        '<div class="tw" style="max-height:300px"><table class="dt">'
        "<thead><tr><th>#</th><th>文件</th><th>类别</th></tr></thead>"
        f"<tbody>{items}</tbody></table></div>"
        '<div style="margin-top:10px"><button class="btn" type="button" '
        'onclick="document.getElementById(\'zipDlg\').close()">关闭</button></div>'
        "</dialog>"
    )


def _flash_html(flash: dict | None) -> str:
    """抓取回执（三态 `ok` / `warn` / `err`）—— 降级 / 空导出 / 陌生仓库**都要显式说明**（禁静默）。"""
    if not flash:
        return ""
    kind = str(flash.get("kind") or "")
    cls = {"ok": "notice ok", "err": "notice err"}.get(kind, "notice wn")
    return f'<div class="{cls}">{esc(flash.get("message"))}</div>'


# ============================================================ 焊材 / 气体提取（§5.3.3）

# ⚠️ 原型里本页与「收发结存」是**同一页的两张卡**；服务端渲染按「一页一个五段骨架、一张表」拆成
#    `/m07/extract`（与 `MOD-05` 拆 `/m05` `/m05/debt` … 同款）—— **属实现方裁量，不改口径**。
EXTRACT_PAGE_ID = "m07e"
EXTRACT_TITLE = "焊材 / 气体提取"

EXTRACT_TIPS = (
    "本表是**核对工具**（§5.3.3）：该数据的**唯一去向 = 活动大表**（开会用），本页只用来核对。",
    "**提取口径**：气体按**白名单精确匹配**；焊材按**关键词 ＋ 排除子串**（取值见 §5.3.3）。",
    "**「总金额」= 全部月份累计**（⛔ 不随筛选变）；**「金额」= 所选月份范围内**的金额（走统一年月控件）。",
    "**本表刻意不可排** —— 各「合计」行必须**紧贴**本类数据行；一排序就会被卷到表尾。",
)

_TAG_CLASS = {"焊材": "tag wn", "气体": "tag ok"}


def _extract_head_html() -> str:
    """表头：**全部不可排**（`nosort`）—— 「本表刻意不可排」在这里落地（001-03）。"""
    return "".join(
        f'<th class="nosort" data-nosort="1">{esc(c["label"])}</th>' for c in X.EXTRACT_COLUMNS
    )


def _extract_block_html(block: dict) -> str:
    """一个分组 = **本类数据行 ＋ 紧贴其后的合计行**（无行则给空态提示行，跨列数 = 表头列数）。

    ⚠️ 合计行**紧贴本类数据行**（不是表尾）⇒ 整表刻意不可排（001-03）。
    """
    kind = str(block["kind"])
    rows = block["rows"]
    if not rows:
        tip = f"当前筛选条件下没有{kind}数据 —— 换个「项目状态」或月份"
        return (f'<tr class="empty"><td colspan="{len(X.EXTRACT_COLUMNS)}" '
                f'class="ctr mut">{esc(tip)}</td></tr>')
    body: list[str] = []
    for row in rows:
        body.append(
            f'<tr><td><span class="{esc(_TAG_CLASS.get(kind, "tag"))}">{esc(kind)}</span></td>'
            f'<td>{esc(row["warehouse"])}</td>'
            f'<td class="num">{esc(money_text(row["total"]))}</td>'
            f'<td class="num">{esc(money_text(row["amount"]))}</td></tr>'
        )
    total = block["total_row"]
    body.append(
        f'<tr class="sum" data-pin="1"><td colspan="2">{esc(total["warehouse"])}</td>'
        f'<td class="num">{esc(money_text(total["total"]))}</td>'
        f'<td class="num">{esc(money_text(total["amount"]))}</td></tr>'
    )
    return "".join(body)


def _extract_data_html(data: dict) -> str:
    """数据区（整段由本处渲染：**一页两块**、每块自带上紧贴的合计行/空态行 ⇒ 骨架的单表合计满足不了）。"""
    body = "".join(_extract_block_html(b) for b in data["blocks"])
    return (
        '<div class="tw" data-seg="data">'
        '<table class="dt" data-sort-key="m07:kinds">'      # ⚠️ **没有 `data-sort`** = 刻意不可排
        f'<thead><tr>{_extract_head_html()}</tr></thead><tbody>{body}</tbody></table></div>'
    )


def _status_select(state: dict) -> str:
    cur = state.get("status") or X.STATUS_DEFAULT
    opts = "".join(
        f'<option value="{esc(v)}"{" selected" if v == cur else ""}>{esc(v)}</option>'
        for v in X.STATUS_OPTIONS
    )
    return f'<select name="status">{opts}</select>'


def _extract_period_input(state: dict) -> str:
    """金额 · 月份 —— 四种模式（月 / 跨月 / 年 / 全部），走统一年月控件（§9.2）。"""
    return (
        '<input name="ext_period" style="min-width:190px" '
        f'value="{esc(state.get("period") or "")}" '
        'placeholder="2026-08 / 2026-01~2026-06 / 2026 / 留空=全部">'
    )


def export_dialog_html(matrices: list[dict]) -> str:
    """导出弹窗：**行 = 所筛选项目 · 列 = 项目 → 各月（逐月连续）→ 求和**（001-06）。
    ⚠️ 本处只给**矩阵内容**（导出为文件的动作归 `ACC-X-EXP-001`）。"""
    blocks: list[str] = []
    for m in matrices:
        head = ["项目", *m["months"], "求和"]
        rows = [
            [r["warehouse"], *[money_text(v) for v in r["cells"]], money_text(r["total"])]
            for r in m["rows"]
        ]
        if m["rows"]:
            rows.append([f'{m["kind"]}合计', *[money_text(v) for v in m["sum_row"]]])
        n = len(head)
        body = "".join(
            "<tr>" + "".join(
                f'<td class="{"num" if i else ""}">{esc(c)}</td>' for i, c in enumerate(r)
            ) + "</tr>"
            for r in rows
        ) or (f'<tr class="empty"><td colspan="{n}" class="ctr mut">'
              f'当前筛选条件下没有{m["kind"]}数据</td></tr>')
        blocks.append(
            f'<div class="mut" style="margin:10px 0 4px"><b>{esc(m["kind"])}</b> · 项目 × 月份</div>'
            f'<div class="tw" style="max-height:260px"><table class="dt" '
            f'data-sort-key="modal:expExt-{esc(m["kind"])}"><thead><tr>'
            + "".join(f'<th class="nosort" data-nosort="1">{esc(h)}</th>' for h in head)
            + f"</tr></thead><tbody>{body}</tbody></table></div>"
        )
    return (
        '<dialog class="dlg" id="expDlg">'
        "<h4>导出 · 焊材 / 气体提取（按 项目 × 月份）</h4>"
        '<div class="mut">导出内容 = <b>当前筛选出的项目</b>；列从左到右 = '
        "<b>项目 → 各月（自最早有数据的月起逐月连续）→ 求和</b>。</div>"
        + "".join(blocks)
        + '<div style="margin-top:10px"><button class="btn" type="button" '
        'onclick="document.getElementById(\'expDlg\').close()">关闭</button></div></dialog>'
    )


def render_extract_page(data: dict) -> str:
    st = data["state"]
    counts = data["counts"]
    filters = [
        {"label": "项目状态（默认在建）", "html": _status_select(st)},
        {"label": "金额 · 月份", "html": _extract_period_input(st)},
        {"label": "", "html": '<button class="btn pri" type="submit">查询</button>'
                              ' <a class="btn" href="/m07/extract">重置</a>'},
        {"label": "动作", "html":
            '<button class="btn" type="button" '
            'onclick="document.getElementById(\'expDlg\').showModal()">导出（项目 × 月份）</button>'},
        {"label": "", "html": f'<span class="pill">焊材 {counts.get("焊材", 0)} 项 · '
                             f'气体 {counts.get("气体", 0)} 项</span>'},
    ]
    section = render_list_page(
        page_id=EXTRACT_PAGE_ID,
        title=f"{EXTRACT_TITLE}（核对工具 · 项目状态 {st['status']}）",
        tips=EXTRACT_TIPS,
        filters=filters,
        data_html=_extract_data_html(data),
        filter_action="/m07/extract",         # ⚠️ 不给 ⇒ 「查询」按钮是死的
    )
    return (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        f"<title>{esc(EXTRACT_TITLE)} · 材料报表自动化工作台</title>"
        f"<style>{BASE_CSS}{EXTRA_CSS}</style></head><body><div class=\"wrap\">"
        f'<div class="hd"><h1>收发结存与活动大表</h1><nav>{_nav_html()}</nav></div>'
        f"{section}{export_dialog_html(data['export'])}"
        "</div></body></html>"
    )


def render_setl_page(data: dict, flash: dict | None = None) -> str:
    state = data["state"]
    filters = [
        {"label": "核算年月", "html": _period_input(state)},
        {"label": "", "html": '<button class="btn pri" type="submit">查询</button>'
                              ' <a class="btn" href="/m07">重置</a>'},
        {"label": "动作", "html":
            '<button class="btn" type="button" '
            'onclick="document.getElementById(\'fetchDlg\').showModal()">抓取 i8</button> '
            '<button class="btn" type="button" '
            'onclick="document.getElementById(\'zipDlg\').showModal()">导出分仓库 zip</button>'},
        {"label": "", "html": _counts_pill(data["counts"])},
    ]
    columns = [{"key": c["key"], "label": c["label"], "sortable": c["sortable"]}
               for c in D.SETL_COLUMNS]
    section = render_list_page(
        page_id=PAGE_ID,
        title=f"{TITLE}（{data['counts']['warehouses']} 仓 · {data['counts']['rows']} 行）",
        tips=TIPS,
        filters=filters,
        columns=columns,
        rows_html=_rows_html(data["rows"]),
        summary=_summary_row(data["summary"]),
        empty_text=data["empty_text"],
        sort_key="m07:warehouses",
        filter_action="/m07",                 # ⚠️ 不给 ⇒ 「查询」按钮是死的（控件不在表单里）
    )
    extra = (
        _flash_html(flash)
        + fetch_dialog_html(data["fetch_default_month"])
        + zip_dialog_html(data["manifest"], data["zip_name"])
        + '<div class="mut sm" style="margin-top:6px">校验列 = 期初 ＋ 收 － 发 － 结存，'
          '按 <b>2 位小数归一后判等（容差 0）</b>；合计行的校验格是**对合计值本身**再判一次。</div>'
    )
    return (
        "<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        f"<title>{esc(TITLE)} · 材料报表自动化工作台</title>"
        f"<style>{BASE_CSS}{EXTRA_CSS}</style></head><body><div class=\"wrap\">"
        f'<div class="hd"><h1>收发结存与活动大表</h1><nav>{_nav_html()}</nav></div>'
        f"{section}{extra}"
        "</div></body></html>"
    )


__all__ = ["PAGE_ID", "TITLE", "TIPS", "EXTRA_CSS", "EXTRACT_PAGE_ID", "EXTRACT_TITLE",
           "EXTRACT_TIPS", "money_text", "fetch_dialog_html", "zip_dialog_html",
           "render_setl_page", "render_extract_page"]
