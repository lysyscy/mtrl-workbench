"""版式**模板驱动**渲染（`API-07` 真契约的实现）—— 纯函数，不连库、不发请求。

## 为什么必须"模板驱动"

i8 `getPrintDesign` 返回的是**模板 JSON**（`Data.printSchema` / `Data.printSetting`），
**不是 HTML** —— 2026-09-15 真机实测，样本见 `tests/fixtures/i8_print_design_sample.json`。
所以"取回 HTML 再往里注字段"这条路**根本不成立**（旧实现必然报"取不到版式"）。

## 依据

- **素材包 `i8一键打印/反解件/print_paynotice.py::render_html`** —— 同一套思路（**旁证**，
  ⚠️ 反编译产物有误：结尾 `</table>` 与 `return` 被错误缩进到 `for` 循环体内；本模块按**语义**重写）；
- **真机取样**：`tests/fixtures/i8_print_design_sample.json`（其他支出 · printId=3700000000000215）。

## 渲染策略（与素材包一致）

| 项 | 做法 |
|---|---|
| 表结构 | `table-layout:fixed` + `<colgroup>` 定列宽（列宽 = `globalSettings.widths` × `scale`） |
| 行高 | 逐行 `heights[row] ?? row_h`，再 × `scale` |
| 框线 | **CSS `border`**（四边独立、`cellBorders[side].hide` ⇒ none）—— 粗细统一，不会"有的 1 格有的 2 格" |
| 字号 | `className` 里的 `htFontSize_N`；对齐 `htLeft/htRight/htCenter`、垂直 `htMiddle`、粗体 `htFontWeight_700` |
| 明细行 | 该行含 `dataSetId ∈ DS_DETAIL` 的单元格 ⇒ **按明细条数重复渲染该行**（这就是"尾部行随行数派生"的机制） |
| 字段格 | `values["<dataSetId>.<fieldId>"]` |
| 签名图 | `cellData.otherShowType == "image"` ⇒ 取 `dataFilter` 里的**办理节点**名 → `signatures[node]`；取不到就**留空** |

⚠️ **已知边界**（未实现；**只有真带了内容才报错**，空壳放行 —— 真机样本里 `headerFooter` / `paging` 恒为空壳）：
`headerFooter` / `paging` / `frozen` / `cellData.bg` / `interaction` / 富文本。
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.errors import MustReportError

# ---------------------------------------------------------------- 常量

# 几何参数（素材包 `profiles_payment_bill.GEO` 旁证）——**设计 px → CSS px** 的缩放与默认尺寸
GEOMETRY: dict[str, float] = {
    "scale": 0.684,       # ⚠️ 模板里的设计尺寸按此比例缩到 CSS px
    "col_w": 110,
    "row_h": 30,
    "font_px": 14,
    "line_height": 1.5,
    "border_px": 1.0,
    "sig_h": 36,
}

# 主表数据集 id（素材包 `profiles_payment_bill.DS_HEADER`）—— 字段格 `values` 键的前缀
DS_HEADER = "3700000000000010"

# 明细数据集 id（素材包 `profiles_payment_bill.DS_DETAIL`）—— 含这些 id 的行 = **明细行**
DS_DETAIL: frozenset[str] = frozenset({"3700000000000212", "3700000000000019"})

# 图片格取「审批节点名」的**两种筛选写法** —— 真机两份模板**各出现一种**，缺任一种都会静默漏印签名：
#   ① `fieldId="办理节点"`（付款通知书那批 · 自定义字段写法）⇒ 节点名在 `value`
#   ② `fieldId="task_des"`（其他支出模板有 1 格用这个 · 直接筛流程字段）⇒ 节点名同样在 `value`
# ⚠️ 两种写法其实是**同一件事的两种表达**：② 直接筛流程字段 `task_des`，而 `task_des` 正是
#    `signatures.collect_signature_paths()` 用的节点名来源 ⇒ 语义完全对齐。
NODE_FILTER_FIELD = "办理节点"
NODE_FIELD_ID = "task_des"

_FONT_SIZE_RE = re.compile(r"htFontSize_(\d+)")

_SIDES = ("top", "bottom", "left", "right")

# 已知但**本模块不实现**的版式特性 —— ⚠️ **只有它们真带了内容**才报错；
#   空壳（`content: null` / `bodies: []`）**无需支持** —— 真实模板里这两项**恒为空壳**
#   （2026-09-15 真机样本实测：`headerFooter.header/footer.content` 均 null、`paging.bodies` 为 []）。
UNSUPPORTED_KEYS = ("headerFooter", "paging")


def _has_real_content(node) -> bool:
    """页眉/页脚的 `content` **是否真有内容**。

    ⚠️ i8 的形态是 `{"left": "", "middle": "", "right": ""}` —— 这是个**非空 dict 但全空串**，
       直接 `if node.get("content")` 会**误判为"有内容"**（空 dict 在 Python 里是 truthy）。
       ⇒ 必须逐槽判空。（2026-09-15：付款通知书模板正是这个形态，害得解析被误拦。）
    """
    if not isinstance(node, dict):
        return False
    content = node.get("content")
    if content is None:
        return False
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, dict):
        return any(str(v or "").strip() for v in content.values())
    return bool(content)


def unsupported_in_use(config: dict) -> list[str]:
    """未实现的打印设置里，**真的带了要渲染的内容**的那些（空壳不算）。"""
    used: list[str] = []
    hf = config.get("headerFooter") or {}
    for part in ("header", "footer"):
        if _has_real_content(hf.get(part) or {}):
            used.append(f"headerFooter.{part}")
    if (config.get("paging") or {}).get("bodies"):
        used.append("paging.bodies")
    return used


# ---------------------------------------------------------------- 数据结构


@dataclass
class PrintTemplate:
    """一份解析好的版式模板（`printSchema` + `printSetting` 的**结构化**表示）。"""

    print_id: str = ""
    print_name: str = ""
    sheet_name: str = ""
    cols: int = 8
    rows: int = 20
    widths: dict[int, float] = field(default_factory=dict)
    heights: dict[int, float] = field(default_factory=dict)
    cells: list[dict] = field(default_factory=list)
    margin: dict = field(default_factory=dict)
    page: dict = field(default_factory=dict)
    data_set_infos: list[dict] = field(default_factory=list)

    # --- 派生 ---
    def cells_by_row(self) -> dict[int, list[dict]]:
        out: dict[int, list[dict]] = {}
        for c in self.cells:
            out.setdefault(int(c.get("row") or 0), []).append(c)
        return out

    def is_detail_row(self, row: int, detail_ids: frozenset[str] = DS_DETAIL) -> bool:
        """该行是否**明细行**（含 `dataSetId ∈ DS_DETAIL` 的单元格）。"""
        for c in self.cells_by_row().get(row, []):
            if (c.get("cellData") or {}).get("dataSetId") in detail_ids:
                return True
        return False

    def col_width(self, index: int) -> float:
        return float(self.widths.get(index) or GEOMETRY["col_w"])

    def row_height(self, index: int) -> float:
        return float(self.heights.get(index) or GEOMETRY["row_h"])

    def field_cells(self) -> list[dict]:
        return [c for c in self.cells if c.get("cellType") == "field"]


# ---------------------------------------------------------------- 解析


def _loads(value: Any, what: str) -> Any:
    """i8 把结构化内容装成 **JSON 字符串**（`printSchema` / `printSetting` / `dataSetInfos`）。"""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise MustReportError(f"版式的「{what}」不是合法 JSON：{exc}") from exc
    return value


def _first_of(value: Any, what: str) -> dict:
    """取数组的第 0 个元素（i8 的这些字段都是**单元素数组**）。"""
    data = _loads(value, what)
    if isinstance(data, list):
        if not data:
            raise MustReportError(f"版式的「{what}」为空数组 —— 取不到版式")
        data = data[0]
    if not isinstance(data, dict):
        raise MustReportError(f"版式的「{what}」形态不认识：{type(data).__name__}")
    return data


def parse_design(data: dict) -> PrintTemplate:
    """i8 `getPrintDesign` 的 `Data` → `PrintTemplate`。

    ⚠️ **取不到模板就显式报错**（不得静默产出空白件）—— 对应 `ACC-PAY-PRINT-001/001-03` 的口径。
    """
    if not isinstance(data, dict):
        raise MustReportError("版式响应不是对象 —— 取不到版式")
    schema = _first_of(data.get("printSchema"), "printSchema")
    setting = _first_of(data.get("printSetting"), "printSetting")

    cells = schema.get("cells")
    if not isinstance(cells, list) or not cells:
        raise MustReportError("版式模板里没有单元格（cells 为空）—— 取不到可用版式")

    gs = schema.get("globalSettings") or {}
    config = setting.get("printConfig") or {}
    in_use = unsupported_in_use(config)
    if in_use:
        raise MustReportError(
            "版式用到了本渲染器尚未支持的打印设置（%s）—— 已停止，避免印出错误版式"
            % "、".join(in_use)
        )

    widths = {int(w["col"]): float(w.get("width") or 0) for w in (gs.get("widths") or [])
              if isinstance(w, dict) and "col" in w}
    heights = {int(h["row"]): float(h.get("height") or 0) for h in (gs.get("heights") or [])
               if isinstance(h, dict) and "row" in h}

    return PrintTemplate(
        print_id=str(data.get("printId") or ""),
        print_name=str(data.get("printName") or ""),
        sheet_name=str(schema.get("sheetName") or ""),
        cols=int(gs.get("cols") or 8),
        rows=int(gs.get("rows") or 20),
        widths=widths,
        heights=heights,
        cells=[dict(c) for c in cells],
        margin=dict(config.get("margin") or {}),
        page=dict(config.get("page") or {}),
        data_set_infos=list(_loads(data.get("dataSetInfos"), "dataSetInfos") or []),
    )


def extract_design_data(resp: Any) -> dict:
    """从 `getPrintDesign` 的**完整响应**里取出 `Data`（真机外层是 `{Status, Code, Msg, Data}`）。"""
    if isinstance(resp, dict) and isinstance(resp.get("Data"), dict):
        return resp["Data"]
    if isinstance(resp, dict) and ("printSchema" in resp or "printSetting" in resp):
        return resp                      # 已经是 Data（测试 / 未来形态变化）
    raise MustReportError("取版式响应里没有 Data —— 取不到版式")


# ---------------------------------------------------------------- 样式


def _font_px(cell: dict, default: float) -> float:
    found = _FONT_SIZE_RE.search(str(cell.get("className") or ""))
    return float(found.group(1)) if found else float(default)


def cell_css(cell: dict, *, geometry: dict | None = None) -> str:
    """单元格 CSS（字号 / 对齐 / 粗体 / 四边框线）。

    ⚠️ 框线**只用 CSS border**：四边独立、粗细统一（素材包 2026-09-14 实测结论）。
    ⚠️ `cellBorders[side]` **缺失或 `hide` ⇒ `border-<side>:none`**（缺省不画线）。
    """
    g = {**GEOMETRY, **(geometry or {})}
    scale = g["scale"]
    cn = str(cell.get("className") or "")
    out = f"font-size:{_font_px(cell, g['font_px']) * scale:.2f}px;"
    out += "text-align:" + ("left" if "htLeft" in cn else "right" if "htRight" in cn else "center") + ";"
    out += "vertical-align:" + ("middle" if "htMiddle" in cn else "top") + ";"
    if "htFontWeight_700" in cn:
        out += "font-weight:700;"
    borders = cell.get("cellBorders") or {}
    for side in _SIDES:
        spec = borders.get(side)
        if spec is None or spec.get("hide"):
            out += f"border-{side}:none;"
        else:
            color = spec.get("color") or "#000000"
            out += f"border-{side}:{float(g['border_px']):.2f}px solid {color};"
    return out


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=False)


def _attrs(cell: dict) -> str:
    out = ""
    if int(cell.get("colspan") or 1) > 1:
        out += f' colspan="{int(cell["colspan"])}"'
    if int(cell.get("rowspan") or 1) > 1:
        out += f' rowspan="{int(cell["rowspan"])}"'
    return out


def node_of(cell: dict) -> str:
    """图片格筛的**审批节点名** —— `dataFilter` 里的两种写法都认（见 `NODE_FILTER_FIELD` / `NODE_FIELD_ID`）。

    ⚠️ **为什么必须认两种**（2026-09-16 实测根因）：`i8_print_design_sample.json`（其他支出）的
       `row=15 col=3` 签名格用的是第 ② 种写法。旧实现只认第 ① 种 ⇒ 该格返回空 ⇒
       **它连"签名槽位"都算不上**（不进 `signature_slots()`）⇒ 既不在 `missing`、也不在
       `blank_by_design` ⇒ 印出来是一张**没有核算部部长签名的件**，而 `001-04/05/06` 三条判据
       **一条都不触发**（`001-06` 要"一个都没命中"才报，此处其余 4 个签名都命中了）—— 典型静默失效。
    ⚠️ **一个筛选条件都没有 ⇒ 返回空是正确**（真实打印件验证：无筛选的签名格 i8 本身也印空）；
       但**有筛选却解析不出节点**属"不认识的写法"，由 `signatures.unresolved_image_slots()` 兜住报警。
    """
    cd = cell.get("cellData") or {}
    for f in cd.get("dataFilter") or []:
        if not isinstance(f, dict):
            continue
        if str(f.get("fieldId") or "") in (NODE_FILTER_FIELD, NODE_FIELD_ID):
            name = str(f.get("value") or "")
            if name:
                return name
    return ""


def is_image_cell(cell: dict) -> bool:
    cd = cell.get("cellData") or {}
    return cell.get("cellType") == "field" and cd.get("otherShowType") == "image"


# ---------------------------------------------------------------- 渲染


def render_html(
    tpl: PrintTemplate,
    *,
    values: dict | None = None,
    detail_rows: list[dict] | None = None,
    signatures: dict | None = None,
    geometry: dict | None = None,
    detail_ids: frozenset[str] | None = None,
) -> tuple[str, list[tuple]]:
    """模板 + 数据 → HTML。返回 `(html, 签名落点列表)`。

    - `values` —— `{"<dataSetId>.<fieldId>": 值}`（如 `{"3700000000000010.项目名称": "…"}`）
    - `detail_rows` —— 明细行列表（**每条重复渲染一次明细行**）；为空则渲染一个空行
    - `signatures` —— `{审批节点名: 图片 data:URI}`；取不到就**留空**（不漏印、也不画错）
    - 签名落点列表 = `(row, col, 节点名, 是否取到图)` —— 供"零命中报警"用（`print/signatures.py`）
    """
    g = {**GEOMETRY, **(geometry or {})}
    scale = g["scale"]
    values = values or {}
    rows_data = list(detail_rows or [{}])
    signatures = signatures or {}

    colw = [round(tpl.col_width(i) * scale, 2) for i in range(tpl.cols)]
    total_w = round(sum(colw), 2)
    mg = tpl.margin
    mtop = float(mg.get("top") or 5)
    mleft = float(mg.get("left") or 10)
    mright = float(mg.get("right") or 10)
    mdown = mg.get("down")
    mbot = float(mdown if mdown is not None else 5)

    out: list[str] = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'><style>",
        "@page{size:A4 portrait;margin:%gmm %gmm %gmm %gmm;}" % (mtop, mright, mbot, mleft),
        'body{margin:0;font-family:"Microsoft YaHei","SimSun",sans-serif;color:#000;}',
        "table{border-collapse:collapse;table-layout:fixed;width:%gpx;margin:0 auto;}" % total_w,
        "td{padding:0 2px;line-height:%.2f;word-break:break-all;}" % g["line_height"],
        "img.sig{max-width:100%%;max-height:%.1fpx;display:block;margin:0 auto;}" % (g["sig_h"] * scale),
        "</style></head><body><table><colgroup>",
    ]
    out += ['<col style="width:%gpx">' % w for w in colw]
    out.append("</colgroup>")

    by_row = tpl.cells_by_row()
    signature_slots: list[tuple] = []

    for r in range(tpl.rows):
        row_cells = sorted(by_row.get(r, []), key=lambda x: int(x.get("col") or 0))
        if not row_cells:
            continue
        height = round(tpl.row_height(r) * scale, 2)
        # 明细行 ⇒ **按明细条数重复渲染该行**；普通行 ⇒ 渲染一次
        repeats = rows_data if tpl.is_detail_row(r, detail_ids or DS_DETAIL) else [None]
        for detail in repeats:
            out.append('<tr style="height:%gpx">' % height)
            for c in row_cells:
                cd = c.get("cellData") or {}
                if is_image_cell(c):
                    node = node_of(c)
                    uri = str(signatures.get(node) or "") if node else ""
                    signature_slots.append((r, c.get("col"), node, bool(uri)))
                    content = f'<img class="sig" src="{uri}">' if uri else ""
                elif c.get("cellType") == "field":
                    if detail is not None and cd.get("dataSetId") in (detail_ids or DS_DETAIL):
                        content = _esc(detail.get(str(cd.get("fieldId")), ""))
                    else:
                        key = "%s.%s" % (cd.get("dataSetId"), cd.get("fieldId"))
                        content = _esc(values.get(key, ""))
                else:
                    content = _esc(cd.get("value") or "")
                out.append(
                    "<td%s style=\"%s\">%s</td>" % (_attrs(c), cell_css(c, geometry=g), content)
                )
            out.append("</tr>")

    out.append("</table></body></html>")
    return "\n".join(out), signature_slots


__all__ = [
    "GEOMETRY", "DS_HEADER", "DS_DETAIL", "NODE_FILTER_FIELD", "NODE_FIELD_ID", "UNSUPPORTED_KEYS", "unsupported_in_use",
    "PrintTemplate", "parse_design", "extract_design_data",
    "cell_css", "node_of", "is_image_cell", "render_html",
]
