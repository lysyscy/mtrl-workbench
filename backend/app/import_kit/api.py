"""`import_kit.api` —— **通用导入 API 面**（`TAIL-75` B1 · 设计 §七）。

一套面覆盖所有导入域：`schema → parse → preview → commit（→rollback）`。
域只给 `DomainSpec`（字段/必填/别名）＋ 两个钩子（落库/回滚）—— ⛔ 通用层不碰业务判定。

四条硬性（⛔ 实施时别破）：
1. **永不静默猜**：认不出的列 ⇒ `field=None` 留在界面上让人选；解析不了的单元格 ⇒ 进问题清单。
2. **未映射列原样保留**（`raw`），⛔ 不丢、不报错。
3. **确认前零写库**：`parse`/`preview` 只进 `core.preview_store`（唯一载具）。
4. 恒 **HTTP 200 ＋ `ok` 标志** ＋ **中文原因原样交界面**（与 `m05`/`m06` 既有口径一致）。

⭐ 本层"聪明"的地方全在复用：
- 挑工作表 = **哪张认得出表头**（用 `mapping.guess` 判，不是猜位置）；
- 认列 = `mapping.guess`（四级命中 ＋ 类型交叉验证）＋ **记忆预填**（`profile_store`）；
- 取值 = `import_kit.parse`（金额/日期的**唯一解析出口**，与 i8 抓取同一套）。
"""

from __future__ import annotations

import inspect
import re

from fastapi import APIRouter, File, Form, UploadFile

from app.core import preview_store
from app.core.db import session_scope
from app.core.errors import MustReportError
from app.core.identity import current_operator
from app.import_kit import mapping
from app.import_kit.parse import amount as parse_amount
from app.import_kit.parse import date_text, text
from app.import_kit.profile_store import ProfileStore
from app.import_kit.readers import HEADER_SCAN_ROWS, list_sheets, read_grid
from app.import_kit.spec import DomainSpec, Hooks

#: 预览给前几行（⛔ 不是导出：全量已随 token 暂存）
#  ⚠️ 2026-09-26（用户报障「第 4 步显示的行不完整」）：原值 **20** —— 而真文件（晋江那份过程资料）
#     数据在 Excel 的 r4~r32 ⇒ **20 条盖不住**，"有问题的第 19 行"那一屏里就是看不到。
#     ⇒ 抬到 **200**（不是"给全量"：上限仍在，只是**够看清一份台账**；真正的全量始终随 token 暂存、
#     ④ 落库写的是**全量**）。⭐ 壳侧必须写明"显示前 N 行 / 共 M 行"（⛔ 不许静默截断）。
PREVIEW_ROWS = 200
#: 每列取几个样本值（给画像与界面看）
SAMPLES = 3
#: 挑工作表时，至少要认出这么多列才算"这张是对的"
MIN_SHEET_HITS = 2

#: ⭐ **已挂上通用面的域**（`build_router` 被调用时登记 —— 应用 import 期即完成）。
#: 壳的「数据导入」页据此列清单（⛔ 壳里不许再抄一份域清单 —— 抄了就是"加一个域要改两处"）。
REGISTRY: dict[str, DomainSpec] = {}


def domains_router() -> APIRouter:
    """`GET /api/imp/domains` —— 给壳的**域清单**（只给 `domain/title/batch`；字段契约另走 `/schema`）。"""
    r = APIRouter(tags=["imp-domains"])

    @r.get("/api/imp/domains")
    def api_domains() -> dict:
        return {"ok": True, "domains": [{"domain": s.domain, "title": s.title,
                                         "batch": bool(s.batch)}
                                        for s in REGISTRY.values()]}

    return r


def _hit(header, spec: DomainSpec) -> str | None:
    """表头单元格 → 命中字段（用 `guess` 判，`<0.70` 一律不算命中）。"""
    got = mapping.guess([header], spec.fields)[0]
    return got.field


def _takes_options(fn, base: int) -> bool:
    """钩子是否**多收**一个 `options` 参数 —— 按**签名**判；`base` = 不收 `options` 时的位置参数个数
    （`commit` = 4：`session/records/mapping/operator` · `preview` = 3：`session/records/mapping`）。

    ⛔ 不写成"先按多一个参试调，失败再退回"：那会把钩子**内部**真出的 `TypeError` 一起吃掉，
       症状是"导入报了个莫名其妙的旧错"。
    """
    try:
        params = [p for p in inspect.signature(fn).parameters.values()
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    except (TypeError, ValueError):
        return False
    return len(params) >= base + 1


def _headers_of(grid: list[list], top: int, bottom: int | None, spec: DomainSpec
                ) -> tuple[list[str], set[str]]:
    """逐列算表头名 ＋ 命中字段集。

    ⭐ **两级表头**（`B5-0` 接 `m06` 时补的缺口）：`bottom` 给了就把「父 ＋ 子」拼名，**两种顺序都试**
      （真文件里父/子位置**在项目间互换**：慧能 = `含税` › `外租设备（零租）`，晋江 = `外租机械（含税）` › `零租`）。
      ⚠️ 拼名用**原文**拼（⛔ 不用 `mapping.join_levels` —— 它顺手归一化，而展示/映射键必须是原文）。
      ⚠️ 一格命中不了就退回「父+子」的写法 ⇒ 界面上仍看得见"系统按什么认的"（⛔ 不静默丢列）。
    """
    width = max(len(grid[top]) if top < len(grid) else 0,
                (len(grid[bottom]) if bottom is not None and bottom < len(grid) else 0))
    names: list[str] = []
    fields: set[str] = set()
    for c in range(width):
        up = text(grid[top][c]) if top < len(grid) and c < len(grid[top]) else ""
        down = (text(grid[bottom][c])
                if bottom is not None and bottom < len(grid) and c < len(grid[bottom]) else "")
        cands = [up + down, down + up] if (up and down and up != down) else [up or down]
        name = cands[0]
        for cand in cands:
            hit = _hit(cand, spec)
            if hit:
                name, _ = cand, fields.add(hit)
                break
        names.append(name)
    return names, fields


def _header_row(grid: list[list], spec: DomainSpec) -> tuple[int, int | None, int] | None:
    """前 N 行里找表头 ⇒ `(父行下标, 子行下标|None, 认出几列)`；都不够 ⇒ `None`。

    ⚠️ **单行与两行都要试**（不是"看第几行像表头"）：用户台账里既有单行表头（付款计划实拍），
      也有两级表头（过程资料 `线上入库（不含税）` › `主辅材`）⇒ 取"认出字段最多"的那个。
    """
    best: tuple[int, int | None, int] | None = None
    for idx in range(min(len(grid), HEADER_SCAN_ROWS)):
        for bottom in (None, idx + 1):
            if bottom is not None and (bottom >= len(grid)
                                       or not any(text(c) for c in grid[bottom])):
                continue
            _, fields = _headers_of(grid, idx, bottom, spec)
            if len(fields) < MIN_SHEET_HITS:
                continue
            # ⭐ 择优顺序：**认出字段多** > **不加"子行"** > **行号更靠下**。
            #   ⚠️ 中间那条是实测逼出来的：老板的表常是「r1 大标题 ＋ r2 表头」——
            #      早先把 r1 当"父级"拼名（`大标题+项目`）照样能命中（包含词）⇒ 认成"两级表头在 r1/r2"，
            #      于是第一个数据行被当成表头吃掉。加了这条：**拼名没多认出任何字段 ⇒ 就不算父级**。
            #   ⚠️ 中间那项 **1 = 无子行优先**（⛔ 别写成"有子行"更优 —— 那会把标题行/数据行拉进表头，
            #      自测踩到：B1 的夹具表头在首行，被"父级拼名"顶掉 ⇒ 整表认列全乱）。
            key = (len(fields), 1 if bottom is None else 0, idx)
            if best is None or key > (best[2], 1 if best[1] is None else 0, best[0]):
                best = (idx, bottom, len(fields))
    return best


def _pick_sheet(data: bytes, spec: DomainSpec
                ) -> tuple[str, list[list], int, int | None, list[str]]:
    """挑工作表 ＋ 找表头 ⇒ `(sheet, grid, 父行, 子行|None, sheets)`。

    ⭐ 规则：**哪张认得出表头就用哪张**（命中字段数最多者胜）；都不认得出 ⇒ **显式报错**并列出工作表。
    """
    sheets = list_sheets(data)
    if spec.preferred_sheet and spec.preferred_sheet in sheets:
        sheets = [spec.preferred_sheet] + [s for s in sheets if s != spec.preferred_sheet]
    best: tuple[int, str, list[list], int, int | None] | None = None
    for name in sheets:
        try:
            # ⭐ **只铺表头那几行的合并区**：两级表头的分组头是合并格（`线上入库（不含税）` 只写在
            #    `C2`、`D2~F2` 是空的）⇒ 不铺就拿不到父级、拼不出「线上入库（不含税）主辅材」。
            #    ⚠️ 只铺前 `HEADER_SCAN_ROWS` 行 —— 数据区的竖合并一铺，就会把同一个金额复制到相邻行。
            grid, _ = read_grid(data, sheet=name, max_rows=spec.max_rows,
                                fill_merged_rows=HEADER_SCAN_ROWS)
        except MustReportError:
            continue                      # 空表/读不了的表 ⇒ 跳过（真文件里就有：`pvOg8w` / `3月底`）
        found = _header_row(grid, spec)
        if found and (best is None or found[2] > best[0]):
            best = (found[2], name, grid, found[0], found[1])
            if found[0] == 0 and found[1] is None:
                break                     # 单行表头且在首行 ⇒ 不用再往下试
    if best is None:
        raise MustReportError(
            f"这份文件里没有一张工作表能认成「{spec.title}」的表头"
            f"（要至少认出 {MIN_SHEET_HITS} 列）。现有工作表：{' / '.join(sheets)}")
    return best[1], best[2], best[3], best[4], sheets


def _cols(headers: list[str], grid: list[list], *, first_row: int
          ) -> dict[str, list[str]]:
    """每列样本值（跳过空表头与完全空白的列）。`first_row` = 首行数据在网格里的下标。"""
    samples: dict[str, list[str]] = {}
    for i, name in enumerate(headers):
        if not name:
            continue
        vals = []
        for row in grid[first_row:]:
            v = text(row[i]) if i < len(row) else ""
            if v:
                vals.append(v)
            if len(vals) >= SAMPLES:
                break
        samples[name] = vals
    return samples


def _coerce(value, ftype: str, *, row_no: int, label: str, problems: list[dict]):
    """按字段类型取值（⭐ 走 `import_kit.parse` 唯一出口）；**取的失败 ⇒ 进问题清单**（不静默）。

    ⭐ **空 ≠ 0**（2026-09-22 · `B5-0` 接 `m06` 时发现的真冲突）：`parse.amount("")` 会给 `0.00`，
      而域里的口径是"**没填**就不写这一列"。⇒ 通用面**先看有没有值**：空 ⇒ 回 `""`（域钩子据此跳过），
      ⛔ 不把"没填"静默变成"填了 0"（那是直账上多一笔 0，且**没人看得出来**）。
    """
    if ftype == "amount":
        if not text(value):
            return ""
        try:
            return str(parse_amount(value))
        except Exception as exc:  # noqa: BLE001
            problems.append({"row": row_no, "column": label, "raw": text(value),
                             "reason": f"不是数字（{type(exc).__name__}）⇒ 保留原值待人处理"})
            return None
    if ftype == "date":
        return date_text(value)
    if ftype == "ym":
        # ⭐ 声明成 `ym` 就给**年月**（不是完整日期）—— 否则域钩子拿到 `2024-06-01` 还得再削一刀，
        #    而这种"每域各削一次"的活正是要收编的东西。只对**ISO 日期**削，其余原样交域内归一。
        got = date_text(value)
        return got[:7] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", got) else got
    return text(value)


def _records(rows: list[list], headers: list[str], spec: DomainSpec,
             mapping_: dict[str, str], *, first_row: int) -> tuple[list[dict], list[dict]]:
    """数据行 × 表头 × 映射 → `(记录, 问题清单)`。

    ⚠️ `rows` **只含数据行**（表头已切掉），`first_row` = 首行数据在 Excel 里的行号（1 起，用于报问题）。
       ⛔ 别在这里又跳过一行 —— 自测踩过：第一行数据被当表头吃掉（预览/确认都少一整行）。
    """
    out: list[dict] = []
    problems: list[dict] = []
    for offset, row in enumerate(rows, start=first_row):
        if not any(text(c) for c in row):
            continue                                   # 全空行跳过
        rec: dict = {"_row": offset}
        raw: dict = {}
        for i, src in enumerate(headers):
            if not src:
                continue
            val = row[i] if i < len(row) else None
            to = mapping_.get(src, mapping.IGNORE)
            if to and to != mapping.IGNORE:
                f = spec.by_label(to)
                rec[to] = _coerce(val, f.type if f else "text",
                                  row_no=offset, label=to, problems=problems)
            else:
                raw[src] = text(val)
        # 必填为空 ⇒ 显式列出（⛔ 不写 0、不写空字符串糊过去）
        # ⚠️⚠️ 2026-09-26（用户报障后收口）：**只对"看起来是数据行"的行报**（这一行至少有一个别的字段有值）。
        #    否则**说明行**（真文件里就写在「时间」列：`6月总出库也多了53.54`）会被报成
        #    「必填为空 ⇒ 需处理」，而域那边同时说它「**说明行 ⇒ 不导入**」⇒ **同一行两个说法**，
        #    用户会去追一条根本不用管的问题（实测晋江那份：预览的"待处理 1 处"指的就是这一行）。
        #    ⛔ 别把这条判据搬走：它管的是"这一行**像不像数据**"，与域"哪些行不收"无关。
        filled = any(str(v or "").strip() for k, v in rec.items() if k not in ("_row", "raw"))
        if filled:
            for label in spec.required:
                if not str(rec.get(label) or "").strip():
                    problems.append({"row": offset, "column": label, "raw": "",
                                     "reason": "必填为空 ⇒ 需处理（补值或跳过本行，⛔ 不写 0）"})
        rec["raw"] = raw
        out.append(rec)
    return out, problems


def build_router(spec: DomainSpec, hooks: Hooks, store: ProfileStore | None = None) -> APIRouter:
    """给一个域造一组端点（`B2` 起各域接线时用；⛔ 通用层不 include_router 到 app）。"""
    r = APIRouter(tags=[f"imp-{spec.domain}"])
    store = store or ProfileStore()
    base = f"/api/imp/{spec.domain}"
    REGISTRY[spec.domain] = spec          # ⭐ 登记 ⇒ `/api/imp/domains` 能列出来（壳据此渲染）

    @r.get(base + "/schema")
    def api_schema() -> dict:
        return {"ok": True, **spec.as_schema()}

    # ⭐ `/options` **恒挂**（2026-09-26）—— 它与 `rollback` 的处置**刻意不同**：
    #    · `rollback` 是**能力**：没钩子 = 这个域没有回滚 ⇒ 不挂端点，壳也不画那个按钮（能力缺失看得见）；
    #    · `options` 是**问一句**"这个域有哪些上下文"（候选项目 / 截止月 / 归属年月…）⇒ **问句必须有个回答**。
    #  ⛔ 原先写成 `if hooks.options is not None:` ⇒ 没挂钩子的域**一问就是 HTTP 404**，而真机自检
    #     （`tools/probe/_shell_smoke.py` 的「console / page 错误」）**把 404 判红**；
    #     更糟的是："问不到"（404）与"真的没有上下文"（空包）在壳侧长得一样 ⇒ 壳只能靠吞异常猜。
    #  ⇒ 没给钩子 = 这个域**没有域上下文**（回 `ok` 空包），壳据此不渲染那一栏控件。
    @r.get(base + "/options")
    def api_options() -> dict:
        """**域上下文**（候选项目 / 截止月 / 批次…）—— 由域钩子给，通用层不认识它的内容。

        ⚠️ 恒 200 ＋ `ok` 标志（与通用面其余端点同律）：取不到也要让人**看见原因**，⛔ 不静默给空。
        """
        if hooks.options is None:
            return {"ok": True}                      # 这个域**没有**域上下文（⛔ 这不是错误）
        try:
            with session_scope() as s:
                return {"ok": True, **(hooks.options(s) or {})}
        except MustReportError as exc:
            return {"ok": False, "message": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "message": f"取本域选项失败：{type(exc).__name__}: {exc}"}

    @r.post(base + "/parse")
    async def api_parse(file: UploadFile = File(...), sheet: str = Form("")) -> dict:
        try:
            data = await file.read()
            if sheet:                                     # 用户指定了工作表
                grid, _ = read_grid(data, sheet=sheet, max_rows=spec.max_rows,
                                    fill_merged_rows=HEADER_SCAN_ROWS)
                found = _header_row(grid, spec)
                if found is None:
                    raise MustReportError(
                        f"工作表「{sheet}」里认不出「{spec.title}」的表头"
                        f"（要至少认出 {MIN_SHEET_HITS} 列）—— 换一张或核对表头")
                top, bottom, sheets = found[0], found[1], list_sheets(data)
                name = sheet
            else:
                name, grid, top, bottom, sheets = _pick_sheet(data, spec)
            headers, _ = _headers_of(grid, top, bottom, spec)
            last = bottom if bottom is not None else top     # 表头最后一行（子行优先）
            samples = _cols(headers, grid, first_row=last + 1)
            # ⭐ **域里明确不采的列 ⇒ 引擎建议一律作废**（⛔ 不让"包含词"在短标签上过度命中）：
            #    实测（`B5b` 接 m11）：台账的 `序号` 被 0.90 认成 `存档序号`（"序号" ⊂ "存档序号"）
            #    —— 而域里白纸黑字写着"序号 = 行号，系统自己编，不采"。**人写的口径 > 引擎的猜测**。
            suggestions = [
                (mapping.Suggestion(s.src, None, 0.0, spec.ignored_why(s.src), "blank")
                 if spec.ignored_why(s.src) else s)
                for s in mapping.guess(headers, spec.fields, samples=samples)
            ]
            # ⭐ 记忆预填（表头指纹为准；界面照旧显示"来自记忆 · 可改"）
            memory = store.prefill(spec.domain, headers)
            payload = {"domain": spec.domain, "sheet": name, "header_row": top + 1,
                       "headers": headers, "grid_rows": grid[last + 1:],
                       "first_row": last + 2}            # 首行数据的 Excel 行号（报问题用，1 起）
            token = preview_store.save(payload)
            return {
                "ok": True, "token": token, "sheets": sheets, "sheet": name,
                "header_row": top + 1, "source": spec.source_label,
                # ⚠️ 两级表头时 `header_rows` 给两行（界面上写"表头在第 2、3 行"，人才对得上）
                "header_rows": [top + 1] + ([bottom + 1] if bottom is not None else []),
                "cols": [{"src": s.src, "field": s.field, "conf": s.conf, "why": s.why,
                          "level": s.level, "profile": mapping.profile(samples.get(s.src, [])),
                          "samples": samples.get(s.src, []),
                          # ⭐ "认得出但按口径不采"的列也在这张表里，带**理由**（⛔ 不混进"未认出"）
                          "ignored": "" if s.field else spec.ignored_why(s.src)}
                         for s in suggestions],
                "ignored": [{"src": s.src, "why": spec.ignored_why(s.src)}
                            for s in suggestions if not s.field and spec.ignored_why(s.src)],
                "dupes": mapping.dupes(suggestions),
                "memory": ({"mapping": memory[0], "note": memory[1], "sim": memory[2]}
                           if memory else None),
            }
        except MustReportError as exc:
            return {"ok": False, "message": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "message": f"解析失败：{type(exc).__name__}: {exc}"}

    @r.post(base + "/preview")
    def api_preview(body: dict | None = None) -> dict:
        try:
            payload = preview_store.load(str((body or {}).get("token") or ""))
            mapping_ = dict((body or {}).get("mapping") or {})
            records, problems = _records(payload["grid_rows"], payload["headers"], spec, mapping_,
                                         first_row=int(payload.get("first_row") or 2))
            out = {"ok": True, "total": len(records), "problems": problems[:200],
                   "problem_count": len(problems),
                   "preview": [{k: v for k, v in rec.items() if k != "raw"}
                               for rec in records[:PREVIEW_ROWS]]}
            # ⭐ **域预览补丁**（可选 · 2026-09-23 `B5b` 第三步）：域补"只有它自己算得出"的那几块
            #    （如 `m05` 的**未匹配清单**／未识别的付款方式取值／`m11` 的**对号结果**）。
            #    ⚠️ 它是**只读**的（只 `session_scope` 读库），⛔ **不写库** ⇒ `preview_store`
            #       仍是预览的唯一载具（判据 001-06「确认前一个字节都不写库」不受影响）。
            #    ⭐⭐ 2026-09-26（`TAIL-106`）：**上下文一并递过去**——有的域"算得出什么"取决于
            #       界面给的那几格（`m11` 不知道"进哪个项目"就一条都对不了号）。
            #       ⚠️ 与 `commit` **同一条规矩**：钩子收 4 参（只 session/records/mapping）或
            #       5 参（多收一个 `options`）都合法，按**签名**判 —— ⛔ 别写成"先按 5 参试调、
            #       `TypeError` 再退回 4 参"（那会把钩子内部真出的 `TypeError` 一起吃下去）。
            if hooks.preview is not None:
                options = dict((body or {}).get("options") or {})
                with session_scope() as s:
                    extra = (hooks.preview(s, records, mapping_, options)
                             if _takes_options(hooks.preview, 3)
                             else hooks.preview(s, records, mapping_)) or {}
                problems.extend(extra.get("problems") or [])
                out["problems"] = problems[:200]
                out["problem_count"] = len(problems)
                if extra.get("writable") is not None:
                    out["writable"] = int(extra["writable"])
                if extra.get("kpis"):
                    out["kpis"] = dict(extra["kpis"])
                if extra.get("blocks"):
                    out["blocks"] = list(extra["blocks"])
            return out
        except MustReportError as exc:
            return {"ok": False, "message": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "message": f"预览失败：{type(exc).__name__}: {exc}"}

    @r.post(base + "/commit")
    def api_commit(body: dict | None = None) -> dict:
        from app.core.errors import MustReportError as MRE

        try:
            payload = preview_store.load(str((body or {}).get("token") or ""))
            mapping_ = dict((body or {}).get("mapping") or {})
            if bool((body or {}).get("remember")) and mapping_:
                store.save(spec.domain, payload["headers"], mapping_,
                           source_label=spec.source_label)
            records, problems = _records(payload["grid_rows"], payload["headers"], spec, mapping_,
                                         first_row=int(payload.get("first_row") or 2))
            options = dict((body or {}).get("options") or {})      # ⭐ 域自定义上下文（如 m06 的"哪个项目"）
            with session_scope() as s:
                report = (hooks.commit(s, records, mapping_, current_operator(), options)
                          if _takes_options(hooks.commit, 4)
                          else hooks.commit(s, records, mapping_, current_operator()))
            # ⚠️⚠️ 这句话的数字**必须是"真写进去几行"**（2026-09-26 · 用户报障后顺出来的第二个谎）：
            #   原先是 `len(records)`（**解析出多少行**）—— 而域会**跳过**合计/说明行、**不收**认不出核算月的行
            #   ⇒ 实测晋江那份：写了 **24** 行，回执却写「已导入 **32** 行」（用户会以为全进去了）。
            #   ⇒ 域回执里给了写入行数（`rows`）就用它；没给才退回解析行数（⛔ 不许瞎写一个数）。
            written = report.get("rows") if isinstance(report, dict) else None
            n = int(written) if isinstance(written, int) and not isinstance(written, bool) else len(records)
            return {"ok": True, "report": report, "problems": problems[:50],
                    "message": f"已导入 {n} 行"
                               + (f"（{len(problems)} 处需处理）" if problems else "")}
        except MRE as exc:
            return {"ok": False, "message": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "message": f"导入失败：{type(exc).__name__}: {exc}"}

    if hooks.rollback is not None:
        @r.post(base + "/rollback")
        def api_rollback(body: dict | None = None) -> dict:
            from app.core.errors import MustReportError as MRE

            try:
                batch = str((body or {}).get("batch") or "")
                with session_scope() as s:
                    report = hooks.rollback(s, batch, current_operator())
                return {"ok": True, "report": report, "message": f"批次 {batch} 已回滚"}
            except MRE as exc:
                return {"ok": False, "message": str(exc)}
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "message": f"回滚失败：{type(exc).__name__}: {exc}"}

    return r


__all__ = ["MIN_SHEET_HITS", "PREVIEW_ROWS", "SAMPLES", "build_router"]
