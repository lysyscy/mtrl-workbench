"""`TAIL-210` 第 3 批（用词统一）· 一次把「上屏文字」里的技术词收干净。

口径（用户 2026-10-01 裁定「123 按推荐」＋「交付面说明书跟着改」）：
- `落库` ⇒ **`写入`**（⛔ 不用「入库」—— 「入库」在本系统已是业务词：「入库 5 类 / 出入库方向 / 入库合计」）
- `落不了库` ⇒ **`写不进去`**（含后端那块标题 `⚠️ 落不了库的行`）
- `后端` ⇒ 人话（「系统 / i8 / 这次抓取」按上下文）
- `接口` ⇒ **`抓取`**（i8 取数那个意思）；执行记录那列表头 ⇒ **`动作`**
- `phid` ⇒ **`信息化编号`**（中文名 m01 口径块里本来就有）
- `解析` ⇒ **一字不动**（用户裁定保留）
- ⛔ 误命中不动：`只落库存单据`（是「落」＋「库存单据」）
- ⛔ 不上屏的不动：`PJ_COLS` 的 `'phid'` 键 · `p.phid` 取值 · 被 JS 覆盖的静态 `<th>接口</th>`

写法（照 `_tail209_mark.py` 的纪律）：**逐条定点**（件 + 行号 + 原文 + 新文 + 该行命中次数），
任一条不达标 ⇒ **整批不写盘**；写盘前在内存里自检（否则逐字节回滚）。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_front4_words.py`          # 干跑（只报，不写）
      `… --apply`                                                    # 落盘
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
FACE = pathlib.Path("D:/工作/AI/PRD编写夹 - Workbuddy专用")

W = ROOT / "backend" / "app" / "web"
B = ROOT / "backend"
T = ROOT / "backend" / "tests"
PR = ROOT / "tools" / "probe"

#: (相对路径, 行号, 原文, 新文, 该行应命中次数)
RULES: list[tuple[str, int, str, str, int]] = [
    # ── ① 壳 · index.html ────────────────────────────────────────────────────
    ("backend/app/web/index.html", 588, "<b>不静默落库</b>）；命中多家", "<b>不会自己写进去</b>）；命中多家", 1),
    ("backend/app/web/index.html", 590, "（未落库）", "（未写入）", 1),
    ("backend/app/web/index.html", 590, "」落库 / 点「<b>取消</b>」丢弃（<b>草稿不入库</b>",
     "」写入 / 点「<b>取消</b>」丢弃（<b>草稿不写入</b>", 1),
    ("backend/app/web/index.html", 654, "改动<b>落库、不被导入覆盖</b>", "改动<b>会写入、不被导入覆盖</b>", 1),
    ("backend/app/web/index.html", 694, "立刻落库（不留痕）", "立刻写入（不留痕）", 1),
    ("backend/app/web/index.html", 910, "/ 信息化编号（phid）。", "/ 信息化编号。", 1),
    ("backend/app/web/index.html", 912, "抓 phid / 仓库", "抓 信息化编号 / 仓库", 1),
    ("backend/app/web/index.html", 958, "才能抓到 phid。", "才能抓到 信息化编号。", 1),
    ("backend/app/web/index.html", 959, "任何接口不可用", "i8 抓不到时", 1),
    ("backend/app/web/index.html", 959, "<b>同一套解析 / 落库</b>", "<b>同一套解析 / 写入</b>", 1),
    ("backend/app/web/index.html", 959, "，接口失败即切导入。", "，抓不到就改走导入。", 1),
    ("backend/app/web/index.html", 961, "各接口的触发与导出在", "各项抓取的触发与导出在", 1),
    ("backend/app/web/index.html", 964, "里每类接口<b>最近一次</b>", "里每类抓取<b>最近一次</b>", 1),
    ("backend/app/web/index.html", 1334, "、i8 侧是否有可调用的接口 ", "", 1),
    ("backend/app/web/index.html", 1512, "不落库、也不再进「未落库」清单", "不写入、也不再进「未写入」清单", 1),
    ("backend/app/web/index.html", 1526, "不再落库，也不再进「未落库」清单", "不再写入，也不再进「未写入」清单", 1),
    # ── ② 壳 · proj.js ──────────────────────────────────────────────────────
    ("backend/app/web/shell/proj.js", 82, "「保存」落库；「取消」丢弃（草稿不入库，",
     "「保存」写入；「取消」丢弃（草稿不写入，", 1),
    ("backend/app/web/shell/proj.js", 93, "尚未落库 —— 落库后按", "尚未写入 —— 写入后按", 1),
    ("backend/app/web/shell/proj.js", 99, "校验通过后落库（统计结算恒 0", "校验通过后写入（统计结算恒 0", 1),
    ("backend/app/web/shell/proj.js", 99, "（不入库）", "（不写入）", 1),
    ("backend/app/web/shell/proj.js", 246, "<th>phid<span", "<th>信息化编号<span", 1),
    ("backend/app/web/shell/proj.js", 275, "校验通过后落库（日期必填", "校验通过后写入（日期必填", 1),
    ("backend/app/web/shell/proj.js", 275, "（不入库）", "（不写入）", 1),
    # ── ③ 壳 · pages-a.js / pages-b.js ──────────────────────────────────────
    ("backend/app/web/shell/pages-a.js", 115, "「保存」落库；「取消」丢弃（草稿不入库）",
     "「保存」写入；「取消」丢弃（草稿不写入）", 1),
    ("backend/app/web/shell/pages-a.js", 116, "点「保存」落库、点「取消」保持原样", "点「保存」写入、点「取消」保持原样", 1),
    ("backend/app/web/shell/pages-a.js", 118, "—— 落库记项目 id", "—— 写入记项目 id", 1),
    ("backend/app/web/shell/pages-a.js", 129, "校验通过后落库（落库后与导入行同样参与审查）",
     "校验通过后写入（写入后与导入行同样参与审查）", 1),
    ("backend/app/web/shell/pages-a.js", 129, "（不入库）", "（不写入）", 1),
    ("backend/app/web/shell/pages-b.js", 266, "校验通过后落库（归属恒为「库存单据」）",
     "校验通过后写入（归属恒为「库存单据」）", 1),
    ("backend/app/web/shell/pages-b.js", 266, "（不入库）", "（不写入）", 1),
    # ── ④ 壳 · actions.js ───────────────────────────────────────────────────
    ("backend/app/web/shell/actions.js", 265, "与抓取<b>同一套解析 / 落库</b>", "与抓取<b>同一套解析 / 写入</b>", 1),
    ("backend/app/web/shell/actions.js", 592, "<b>项目（phid 筛）</b>", "<b>项目（按信息化编号筛）</b>", 1),
    ("backend/app/web/shell/actions.js", 699, "预览（不写库）→ 确认落库", "预览（不写库）→ 确认写入", 1),
    ("backend/app/web/shell/actions.js", 704, "点该行「保存」落库、点「取消」丢弃", "点该行「保存」写入、点「取消」丢弃", 1),
    ("backend/app/web/shell/actions.js", 704, "它落库后<b>与导入行同住一表", "它写入后<b>与导入行同住一表", 1),
    ("backend/app/web/shell/actions.js", 711, "点「保存」落库、点「取消」保持原样", "点「保存」写入、点「取消」保持原样", 1),
    ("backend/app/web/shell/actions.js", 750, "（草稿未落库）", "（草稿未写入）", 1),
    ("backend/app/web/shell/actions.js", 828, "点该行「保存」落库、点「取消」丢弃", "点该行「保存」写入、点「取消」丢弃", 1),
    ("backend/app/web/shell/actions.js", 838, "（草稿未落库）", "（草稿未写入）", 1),
    ("backend/app/web/shell/actions.js", 846, "点「保存」落库、点「取消」保持原样", "点「保存」写入、点「取消」保持原样", 1),
    ("backend/app/web/shell/actions.js", 971, "点「保存」落库、点「取消」丢弃（<b>草稿不入库</b>）",
     "点「保存」写入、点「取消」丢弃（<b>草稿不写入</b>）", 1),
    ("backend/app/web/shell/actions.js", 1433,
     "⏳ <b>删除尚未接通后端</b>：「${esc(p.disp||p.name)}」—— 删除前必须<b>列出影响范围</b>（§7.2），"
     "那是<b>跨模块统计</b>；<br>该能力未落地前不接删除 —— 避免\"列不出影响范围就删了\"",
     "⏳ <b>删除这一项还没打通</b>：「${esc(p.disp||p.name)}」—— 先把「影响范围」列全才开放（见弹窗里那几项）", 1),
    ("backend/app/web/shell/actions.js", 2047, "点该行「保存」落库、点「取消」丢弃", "点该行「保存」写入、点「取消」丢弃", 1),
    ("backend/app/web/shell/actions.js", 2138, "→ 落库（新抓的默认", "→ 写入（新抓的默认", 1),
    ("backend/app/web/shell/actions.js", 2138, "但<b>落库前会给你一眼看见</b>", "但<b>写入前会给你一眼看见</b>", 1),
    ("backend/app/web/shell/actions.js", 2235, "填完点「保存」落库、点「取消」丢弃", "填完点「保存」写入、点「取消」丢弃", 1),
    ("backend/app/web/shell/actions.js", 2264, "这行还没从后端载入，请关掉弹窗重开", "这行还没载入，请关掉弹窗重开", 1),
    ("backend/app/web/shell/actions.js", 2269, "这行还没从后端载入，请关掉弹窗重开", "这行还没载入，请关掉弹窗重开", 1),
    ("backend/app/web/shell/actions.js", 2274, "这行还没从后端载入，请关掉弹窗重开", "这行还没载入，请关掉弹窗重开", 1),
    # ── ⑤ 壳 · legacy.js ───────────────────────────────────────────────────
    ("backend/app/web/shell/legacy.js", 226, "后端没给「i8 服务地址」这一项", "系统里没有「i8 服务地址」这一项", 1),
    ("backend/app/web/shell/legacy.js", 297, "'④ 确认落库'", "'④ 确认写入'", 1),
    ("backend/app/web/shell/legacy.js", 444, "（按 phid 建档，重复的不会重复建", "（按 信息化编号 建档，重复的不会重复建", 1),
    ("backend/app/web/shell/legacy.js", 464, "（库里还没有项目档案 —— 落不了库）",
     "（库里还没有项目档案 —— 没法写入）", 1),
    ("backend/app/web/shell/legacy.js", 476, "落库前一个字节都不写库", "写入前一个字节都不写入", 1),
    ("backend/app/web/shell/legacy.js", 479, "（后端还没挂任何域）", "（还没挂任何导入域）", 1),
    ("backend/app/web/shell/legacy.js", 650, "④ 落库按<b>全量</b>处理", "④ 写入按<b>全量</b>处理", 1),
    ("backend/app/web/shell/legacy.js", 671, "「落不了库的行」", "「写不进去的行」", 1),
    ("backend/app/web/shell/legacy.js", 682, "④ 照常落库即可", "④ 照常写入即可", 1),
    ("backend/app/web/shell/legacy.js", 697, "不影响其余行落库", "不影响其余行写入", 1),
    ("backend/app/web/shell/legacy.js", 707, "'正在落库 —— 请勿重复点击'", "'正在写入 —— 请勿重复点击'", 1),
    ("backend/app/web/shell/legacy.js", 707, "没选就落不了库", "没选就没法写入", 1),
    ("backend/app/web/shell/legacy.js", 707, "'确认落库（这一步才真正写库）'", "'确认写入（这一步才真正写进系统）'", 1),
    ("backend/app/web/shell/legacy.js", 707, "'正在落库…' : '④ 确认落库'", "'正在写入…' : '④ 确认写入'", 1),
    ("backend/app/web/shell/legacy.js", 710, "没选就落不了库", "没选就没法写入", 1),
    ("backend/app/web/shell/legacy.js", 736, "<h4>落库结果", "<h4>写入结果", 1),
    ("backend/app/web/shell/legacy.js", 830, "没选就落不了库", "没选就没法写入", 1),
    ("backend/app/web/shell/legacy.js", 831, "（按 phid 建档，重复的不会重复建）", "（按 信息化编号 建档，重复的不会重复建）", 1),
    ("backend/app/web/shell/legacy.js", 846, "IMP.msg = '正在落库…'", "IMP.msg = '正在写入…'", 1),
    # ── ⑥ 壳 · core.js ─────────────────────────────────────────────────────
    ("backend/app/web/shell/core.js", 439, "条，落库 <b>${r.upserted}</b> 条", "条，写入 <b>${r.upserted}</b> 条", 1),
    ("backend/app/web/shell/core.js", 444, "后端拒绝了这次抓取", "这次抓取被拒绝了", 1),
    ("backend/app/web/shell/core.js", 503, "并落库（集采是<b>逐条落库</b>", "并写入（集采是<b>逐条写入</b>", 1),
    ("backend/app/web/shell/core.js", 504, "那次会自动命中并落库。", "那次会自动命中并写入。", 1),
    ("backend/app/web/shell/core.js", 527, "⚠️ <b>只查不落库</b>。", "⚠️ <b>只查不写入</b>。", 1),
    ("backend/app/web/shell/core.js", 693, "（D9，避免反复顶号）—— 请确认 i8 账号后再试；接口失败可走「手动导入」降级（解析同一条管线）",
     "—— 请确认 i8 账号后再试；i8 抓不到时可走「手动导入」", 1),
    ("backend/app/web/shell/core.js", 811, "|| '后端未说明原因'", "|| '系统没有给出原因，请重试'", 1),
    ("backend/app/web/shell/core.js", 853, "（D9，避免反复顶号）—— 请确认 i8 账号后再试；接口失败可走「手动导入」降级（解析同一条管线）",
     "—— 请确认 i8 账号后再试；i8 抓不到时可走「手动导入」", 1),
    ("backend/app/web/shell/core.js", 1310, "th.textContent = '动作 / 接口'", "th.textContent = '动作'", 1),
    ("backend/app/web/shell/core.js", 1549, "待接通 —— 该接口属<b>集采域</b>（M5 未开工）", "待接通 —— 集采那边的抓取还没做", 1),
    ("backend/app/web/shell/core.js", 1665, "'仓库名单本身<b>不落库</b>", "'仓库名单本身<b>不写入</b>", 1),
    ("backend/app/web/shell/core.js", 1666, "会按 phid <b>建档，重复的不会重复建</b>",
     "会按 信息化编号 <b>建档，重复的不会重复建</b>", 1),
    ("backend/app/web/shell/core.js", 1828, "（已落库 · 默认「纳入台账」）", "（已写入 · 默认「纳入台账」）", 1),
    ("backend/app/web/shell/core.js", 1830, "<b>未落库</b>（<b>归属未走完</b>", "<b>未写入</b>（<b>归属未走完</b>", 1),
    ("backend/app/web/shell/core.js", 2084, "浏览器不许它读后端接口", "浏览器不许它读系统数据", 1),
    # ── ⑦ 壳 · api.js / print-export.js ────────────────────────────────────
    ("backend/app/web/shell/api.js", 29, "这个动作在服务端没有找到（最常见的原因：后端刚改过、但没有重启）",
     "系统暂时连不上，请刷新页面重试", 1),
    ("backend/app/web/shell/api.js", 30, "请让管理员在服务器上重启后端服务（本仓无热重载），然后刷新页面重试。",
     "若一直不行，请联系维护人。", 1),
    ("backend/app/web/shell/print-export.js", 13, "这些行缺少后端 id ⇒ 请先刷新页面再试", "这些行还没载全 ⇒ 请先刷新页面再试", 1),
    ("backend/app/web/shell/print-export.js", 64, "<b>下载没能开始</b>：后端没给下载地址", "<b>下载没能开始</b>：系统没有给出下载地址", 1),
    # ── ⑧ 后端 · 导入域自报 / 报错（会直接上屏）────────────────────────────
    ("backend/app/mod04_plan/imp_spec.py", 90,
     "没有一行可落库的数据 —— 该月未被改动（不写库）", "没有一行能写入的数据 —— 该月未被改动（没有写入）", 1),
    ("backend/app/mod05_flow/imp_spec.py", 53, "、**不落库**）", "、**不写入**）", 1),
    ("backend/app/mod05_flow/imp_spec.py", 198,
     "没有一行可落库的数据 —— 流水未被改动（不写库）。", "没有一行能写入的数据 —— 流水未被改动（没有写入）。", 1),
    ("backend/app/mod05_flow/imp_spec.py", 199, "未匹配 / 异常的行都不落库", "未匹配 / 异常的行都不写入", 1),
    ("backend/app/mod06_proc/imp_spec.py", 63, "落库前要选**项目**", "写入前要选**项目**", 1),
    ("backend/app/mod06_proc/imp_spec.py", 80, "⚠️ 落不了库的行（", "⚠️ 写不进去的行（", 1),
    ("backend/app/mod06_proc/imp_spec.py", 81, "其余行照常落库。", "其余行照常写入。", 1),
    ("backend/app/mod06_proc/imp_spec.py", 88, "「落不了库的行」", "「写不进去的行」", 1),
    ("backend/app/mod06_proc/imp_spec.py", 158, "没选就无从落库", "没选就无从写入", 1),
    ("backend/app/mod06_proc/imp_spec.py", 162,
     "没有一行可落库的数据 —— {why}。历史段未被改动（不写库）",
     "没有一行能写入的数据 —— {why}。历史段未被改动（没有写入）", 1),
    ("backend/app/mod11_jc/imp_spec.py", 56, "落库要选**项目**（仓库名）", "写入要选**项目**（仓库名）", 1),
    ("backend/app/mod11_jc/imp_spec.py", 60, "不落库（系统自己算）", "不写入（系统自己算）", 1),
    ("backend/app/mod11_jc/imp_spec.py", 146,
     "没有一行可落库的数据 —— 台账未被改动（不写库）", "没有一行能写入的数据 —— 台账未被改动（没有写入）", 1),
    ("backend/app/mod11_jc/imp_spec.py", 252, "提醒（不影响本次落库）", "提醒（不影响本次写入）", 1),
    ("backend/app/mod03_notice/router.py", 158, "这次会自动命中并落库。", "这次会自动命中并写入。", 1),
    ("backend/app/mod03_notice/router.py", 183, "这次会自动命中并落库。", "这次会自动命中并写入。", 1),
    ("backend/app/mod03_notice/notice_actions.py", 87, "分类改动**落库、不留痕**", "分类改动**会写入、不留痕**", 1),
    # ── ⑨ 后端 · phid 上线的那两处（顺手清掉同一串里的工程代号）──────────
    ("backend/app/mod01_projects/archive.py", 161, "（无 phid）", "（没有信息化编号）", 1),
    ("backend/app/mod01_projects/repository.py", 73,
     "没有可用 phid（i8 项目编号）⇒ 无法按项目导出。", "没有可用的信息化编号 ⇒ 无法按项目导出。", 1),
    ("backend/app/mod01_projects/repository.py", 74, "列表」（API-06）建档。", "列表」建档。", 1),
    ("backend/app/mod01_projects/domain.py", 154,
     "未建档 ⇒ 需走链路 A（抓 phid → 抓仓库 → 建档）", "未建档 ⇒ 需先补齐项目档案（抓 i8 的信息化编号与仓库）", 1),
    # ── ⑩ 判据 / 探针（同批跟着改）────────────────────────────────────────
    ("backend/tests/test_imp_shell.py", 96,
     "const IMP_STEPS = ['① 选域与文件', '② 列映射', '③ 预览校验', '④ 确认落库'];",
     "const IMP_STEPS = ['① 选域与文件', '② 列映射', '③ 预览校验', '④ 确认写入'];", 1),
    ("backend/tests/test_imp_shell.py", 113,
     "for step in (\"① 选域与文件\", \"② 列映射\", \"③ 预览校验\", \"④ 确认落库\"):",
     "for step in (\"① 选域与文件\", \"② 列映射\", \"③ 预览校验\", \"④ 确认写入\"):", 1),
    ("backend/tests/test_imp_m06_api.py", 338,
     't.startswith("⚠️ 落不了库的行")', 't.startswith("⚠️ 写不进去的行")', 1),
    ("backend/tests/test_imp_m06_api.py", 375,
     'b["title"].startswith("⚠️ 落不了库的行")', 'b["title"].startswith("⚠️ 写不进去的行")', 1),
    ("backend/tests/test_imp_m06_api.py", 385,
     'b["title"].startswith("⚠️ 落不了库的行")', 'b["title"].startswith("⚠️ 写不进去的行")', 1),
    ("tools/probe/_shell_legacy.py", 460, "「④ 确认落库」置灰", "「④ 确认写入」置灰", 1),
    ("tools/probe/_shell_legacy.py", 571, "「④ 确认落库」**变可用**", "「④ 确认写入」**变可用**", 1),
    # ── ⑪ 交付面《说明书》（用户点名的"跟着改"）────────────────────────────
    ("材料科业务全流程说明书.md", 713, "落库后**立刻按归属转成档案行", "写入后**立刻按归属转成档案行", 1),
    ("材料科业务全流程说明书.md", 939, "（**不落库**，无字段可覆盖）", "（**不写入**，无字段可覆盖）", 1),
    ("材料科业务全流程说明书.md", 952, "**刷新页面即恢复默认**、**不落库**", "**刷新页面即恢复默认**、**不写入**", 1),
    ("材料科业务全流程说明书.md", 1103, "这几处改动**落库、不被导入覆盖", "这几处改动**会写入、不被导入覆盖", 1),
    ("材料科业务全流程说明书.md", 1119, "（下拉，落库记**项目 id**）", "（下拉，写入记**项目 id**）", 1),
    ("材料科业务全流程说明书.md", 1315, "**落库前必须预览**", "**写入前必须预览**", 1),
    ("材料科业务全流程说明书.md", 2091, "（抓取时直接剔除、不落库，见 §6.5.4）", "（抓取时直接剔除、不写入，见 §6.5.4）", 1),
    ("材料科业务全流程说明书.md", 2101, "**既不落库、也不再进「未落库」清单**",
     "**既不写入、也不再进「未写入」清单**", 1),
    ("材料科业务全流程说明书.md", 2109, "**已经落库的合同**", "**已经写入的合同**", 1),
    ("材料科业务全流程说明书.md", 2113, "**该不落库还是不落库**", "**该不写入还是不写入**", 1),
    ("材料科业务全流程说明书.md", 2198, "**不静默落库**（该字段**不留痕**", "**不会自己写进去**（该字段**不留痕**", 1),
    ("材料科业务全流程说明书.md", 2283, "⛔ 不落库（现场算）", "⛔ 不写入（现场算）", 1),
    ("材料科业务全流程说明书.md", 2465, "（不落库、不参与统计）", "（不写入、不参与统计）", 1),
    ("材料科业务全流程说明书.md", 2466, "**自动预填也不得静默落库**", "**自动预填也不得自己写进去**", 1),
    ("材料科业务全流程说明书.md", 2522, "（自动预填**不静默落库**，须确认）", "（自动预填**不会自己写进去**，须确认）", 1),
    ("材料科业务全流程说明书.md", 2540, "本就不落库、刷新即恢复默认", "本就不写入、刷新即恢复默认", 1),
    ("材料科业务全流程说明书.md", 2542, "要么**改动不落库**（会话级付款金额）", "要么**改动不写入**（会话级付款金额）", 1),
    ("材料科业务全流程说明书.md", 2787, "**可在列表内手改 —— 落库、不被导入覆盖", "**可在列表内手改 —— 会写入、不被导入覆盖", 1),
    ("材料科业务全流程说明书.md", 2820, "Excel 台账 → **落库前预览** → 落库记批次",
     "Excel 台账 → **写入前预览** → 写入记批次", 1),
    # ── ⑫ 交付面 · 逐字引用界面文案的几处（⛔ 不同批改 ⇒ 那几句变假话）──────
    ("PRD/验收/验收基线.json", 2766, "预览校验 / 确认落库）", "预览校验 / 确认写入）", 1),
    ("PRD/验收/验收基线.json", 4322, "也不再进「未落库」清单", "也不再进「未写入」清单", 1),
    ("PRD/验收/验收基线.json", 4327, "也不进「未落库」清单", "也不进「未写入」清单", 1),
    ("PRD/验收/验收基线.json", 4747, "③ 预览校验 / ④ 确认落库", "③ 预览校验 / ④ 确认写入", 1),
    ("PRD/02-功能规格/MOD-14.md", 36, "也不进「未落库」清单", "也不进「未写入」清单", 1),
]


#: 第二批（`--p2`）：**与「落库」同族、但原候选词表里没有它**的词 —— `写库` / `未落库` 残留
#: ＋ 后端会直接上屏、而壳那轮没覆盖到的几处（`接口` 的收尾）。⚠️ 第一批已落盘 ⇒ 其规则**不可重跑**。
RULES2: list[tuple[str, int, str, str, int]] = [
    # ── 壳 · `写库` ⇒ `写入`（与「落库 ⇒ 写入」同一族）──────────────────────
    ("backend/app/web/shell/actions.js", 699, "预览（不写库）→ 确认写入", "预览（不写入）→ 确认写入", 1),
    ("backend/app/web/shell/actions.js", 1678, "一律拒绝、不写库。", "一律拒绝、不写入。", 1),
    ("backend/app/web/shell/legacy.js", 59, "（一个字节都不写库）", "（一个字节都不写入）", 1),
    ("backend/app/web/shell/legacy.js", 59, "解析并预览（不写库）", "解析并预览（不写入）", 1),
    ("backend/app/web/shell/legacy.js", 583, "这一步一个字节都不写库）", "这一步一个字节都不写入）", 1),
    ("backend/app/web/shell/legacy.js", 583, "③ 预览校验（不写库）", "③ 预览校验（不写入）", 1),
    ("backend/app/web/shell/legacy.js", 686, "一个字节都不写库</b>", "一个字节都不写入</b>", 1),
    ("backend/app/web/shell/legacy.js", 691, "本步写库量", "本步写入量", 1),
    ("backend/app/web/shell/legacy.js", 691, "确认前零写库", "确认前零写入", 1),
    ("backend/app/web/shell/legacy.js", 779, "预览阶段不写库", "预览阶段不写入", 1),
    ("backend/app/web/shell/legacy.js", 812, "预览阶段不写库", "预览阶段不写入", 1),
    # ── 后端 · `写库` / `未落库` ⇒ `写入` ────────────────────────────────────
    ("backend/app/mod06_proc/importer.py", 613, "历史段未被改动（不写库）", "历史段未被改动（没有写入）", 1),
    ("backend/app/mod06_proc/repository.py", 179, "历史段导入为空 —— 不写库（", "历史段导入为空 —— 不写入（", 1),
    ("backend/app/mod11_jc/excel_parse.py", 227, "（不落库）", "（不写入）", 1),
    ("backend/app/mod11_jc/excel_parse.py", 228, "（不落库）", "（不写入）", 1),
    ("backend/app/mod11_jc/excel_parse.py", 229, "（不落库）", "（不写入）", 1),
    ("backend/app/mod11_jc/fetch_service.py", 318, "归属未走完、未落库", "归属未走完、未写入", 1),
    ("backend/app/mod14_config/jc_ignore_api.py", 62,
     "**不再落库**，也不再进「未落库」清单。", "**不再写入**，也不再进「未写入」清单。", 1),
    # ── 后端 · `接口` 的收尾（会直接上屏的那几句）──────────────────────────
    ("backend/app/mod02_i8/fetch_task.py", 124, "i8 接口不可用（", "i8 抓不到数（", 1),
    ("backend/app/mod02_i8/fetch_task.py", 139, "i8 接口不可用（", "i8 抓不到数（", 1),
    ("backend/app/mod02_i8/contract_source.py", 197,
     "i8 采购合同接口未配置（见 `I8_CONTRACT_LIST_URL`，或到「设置」页填写 i8 服务地址）",
     "i8 采购合同取数还没配置 —— 请到「设置」页填写 i8 服务地址", 1),
    ("backend/app/core/app_settings.py", 48, "**四个接口路径由它推导**", "**四项取数的地址由它推导**", 1),
    # ── 交付面 · 同族的 `写库` ─────────────────────────────────────────────
    ("材料科业务全流程说明书.md", 716, "**写库仍按 id**", "**写入仍按 id**", 1),
    ("材料科业务全流程说明书.md", 964, "（不警告、不写库）", "（不警告、不写入）", 1),
    ("材料科业务全流程说明书.md", 1026, "（不自动改数、不写库）", "（不自动改数、不写入）", 1),
    ("材料科业务全流程说明书.md", 1315, "**人工确认后才写库**", "**人工确认后才写入**", 1),
    ("材料科业务全流程说明书.md", 2376, "原来两处都能改（本页写库、", "原来两处都能改（本页写进数据库、", 1),
    ("PRD/验收/验收基线.json", 2609, "**预览阶段不得写库**", "**预览阶段不得写入**", 1),
    ("PRD/验收/验收基线.json", 2707, "确认前零写库；记忆按表头指纹复用。", "确认前零写入；记忆按表头指纹复用。", 1),
    ("PRD/验收/验收基线.json", 2742, "**确认前一个字节都不写库**", "**确认前一个字节都不写入**", 1),
    ("PRD/验收/用例索引.md", 68, "确认前零写库", "确认前零写入", 1),
]


def _read(path: pathlib.Path) -> str:
    with open(path, encoding="utf-8", newline="") as f:      # ⚠️ newline="" ⇒ 逐字节保留行尾
        return f.read()


def _write(path: pathlib.Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _mk_orig() -> int:
    """补一份**改动前**的交付面快照（第 2 批的备份覆盖了第 1 批的 —— ⚠️ 我的失误，这里补回来）。

    做法：拿**当前**内容**反向**套两条规则（new ⇒ old）⇒ 得原始文本；
    再把结果**正向**套一遍、与当前内容逐字节比对 —— ⛔ 不等就拒写（不许留一个"看起来像"的备份）。
    """
    orig = ROOT / ".codebuddy" / "backups" / "交付面-20261001-用词统一-原始"
    n = 0
    for rel in sorted({r for r, *_ in (RULES + RULES2)}):
        if rel.startswith(("backend/", "tools/")):
            continue
        p = resolve(rel)
        cur = _read(p)
        back = cur
        for r, ln, old, new, cnt in reversed(RULES + RULES2):       # ⚠️ 反向
            if r != rel:
                continue
            lines = back.split("\n")
            assert lines[ln - 1].count(new) == cnt, f"反向失败 {rel}:{ln}（找不到 {new!r}）"
            lines[ln - 1] = lines[ln - 1].replace(new, old, cnt)
            back = "\n".join(lines)
        fwd = back                                                  # 正向复算 ⇒ 必须回到当前内容
        for r, ln, old, new, cnt in RULES + RULES2:
            if r != rel:
                continue
            lines = fwd.split("\n")
            assert lines[ln - 1].count(old) == cnt, f"复算失败 {rel}:{ln}"
            lines[ln - 1] = lines[ln - 1].replace(old, new, cnt)
            fwd = "\n".join(lines)
        assert fwd == cur, f"⚠️ 反向重建对不上当前内容（拒写）：{rel}"
        dst = orig / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst, "w", encoding="utf-8", newline="") as f:
            f.write(back)
        n += 1
        print(f"   原始快照 {rel} ⇒ {dst.relative_to(ROOT).as_posix()}")
    print(f"（{n} 件 · 逐件做过「反向 ⇒ 正向」逐字节复核）")
    return 0


def resolve(rel: str) -> pathlib.Path:
    return FACE / rel if not rel.startswith(("backend/", "tools/")) else ROOT / rel


def main() -> int:
    if "--mk-orig" in sys.argv:
        return _mk_orig()
    apply = "--apply" in sys.argv
    rules = RULES2 if "--p2" in sys.argv else RULES
    cache: dict[str, list[str]] = {}
    plan: list[tuple[str, int, str, str, int]] = []
    bad: list[str] = []
    for rel, ln, old, new, cnt in rules:
        p = resolve(rel)
        if not p.exists():
            bad.append(f"{rel} —— 文件不存在")
            continue
        if rel not in cache:
            cache[rel] = _read(p).split("\n")
        lines = cache[rel]
        if ln - 1 >= len(lines):
            bad.append(f"{rel}:{ln} —— 行号超出（该件只有 {len(lines)} 行）")
            continue
        got = lines[ln - 1].count(old)
        if got != cnt:
            bad.append(f"{rel}:{ln} —— 期望命中 {cnt} 次，实测 {got} 次  原文={old!r}")
            continue
        plan.append((rel, ln, old, new, cnt))
    print(f"规则 {len(rules)} 条 ⇒ 通过 {len(plan)} · 不达标 {len(bad)}")
    for x in bad:
        print("   ✗", x)
    for rel, ln, old, new, _ in plan:
        p = resolve(rel)
        head = _read(p).split("\n")[ln - 1].strip()[:110]
        print(f"   ✓ {rel}:{ln}  {old[:46]!r} ⇒ {new[:46]!r}")
        print(f"       该行现状：{head}")
    if bad or not apply:
        if not apply:
            print("\n（干跑 —— ⛔ 没写盘。确认无误后加 `--apply`）")
        return 1 if bad else 0

    # 逐件替换（同一件内的多条规则按行号顺序应用）
    touched = sorted({r for r, *_ in plan})
    # ⭐ 交付面先备份到**仓侧**（它是 WPS 云同步树：可能回退/生成副本；⛔ 别在交付面里建新文件）
    bk = ROOT / ".codebuddy" / "backups" / "交付面-20261001-用词统一"
    for rel in touched:
        if rel.startswith(("backend/", "tools/")):
            continue
        dst = bk / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(resolve(rel).read_bytes())
        print(f"   已备份 交付面/{rel} ⇒ {dst.relative_to(ROOT).as_posix()}")
    for rel in touched:
        p = resolve(rel)
        text = _read(p)
        nl = "\r\n" if "\r\n" in text else "\n"
        lines = text.split("\n")
        for r, ln, old, new, cnt in plan:
            if r != rel:
                continue
            assert lines[ln - 1].count(old) == cnt, f"写盘前复核失败 {rel}:{ln}"
            lines[ln - 1] = lines[ln - 1].replace(old, new, cnt)
        out = "\n".join(lines)
        assert ("\r\n" in out) == ("\r\n" in text) or nl == "\n", f"行尾被改动了：{rel}"
        _write(p, out)
        print(f"   已写 {rel}（{sum(1 for r, *_ in plan if r == rel)} 处）")
    print(f"\n✅ 落盘完成：{len(touched)} 件 · {len(plan)} 处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
