#!/usr/bin/env python
"""任务 2/3（2026-09-21 用户口径「统一像集采台账」）：
  ① `dlExport` 开头加**即时反馈**（治"点了以为没点住"）；
  ② 新增 `fetchResultModal` ＋ nt/wh/iv 三条抓取的**结果弹窗化**（原 = 一闪而过的提示条）；
  ③ `expPivot`（m08 含透视导出，取数 = HTTP 现导会登录 i8）⇒ **二次确认** ＋ `allow_kick=true`（照集采形态）。
全部在**切片外**（core.js / actions.js）⇒ `U1` 不受影响。
"""
from __future__ import annotations

import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
BAK = ROOT / ".workbuddy" / "scratch"
BAK.mkdir(parents=True, exist_ok=True)
CORE = ROOT / "backend" / "app" / "web" / "shell" / "core.js"
ACTS = ROOT / "backend" / "app" / "web" / "shell" / "actions.js"


def patch(p: pathlib.Path, old: str, new: str, tag: str) -> None:
    t = p.read_text(encoding="utf-8")
    if old not in t:
        print(f"⚠️  {p.name}: 找不到锚点 ⇒ {tag}")
        return
    shutil.copy2(p, BAK / (p.name + ".bak-ux"))
    p.write_text(t.replace(old, new, 1), encoding="utf-8", newline="")
    print(f"✅ {p.name}: {tag}")


# ── ① dlExport 即时反馈（core.js）
patch(CORE,
      "async function dlExport(url, { name = '导出文件', label = '导出', close = false } = {}) {\n  let r;",
      "async function dlExport(url, { name = '导出文件', label = '导出', close = false } = {}) {\n"
      "  /* ⭐ 2026-09-21 用户口径「点了让人以为没点住」：导出是**重动作**（后端要现场生成文件，\n"
      "     几秒很正常）⇒ **先给一句进行中反馈**，成功/失败的明确提示由调用方在完成后给。 */\n"
      "  toast(`<b>${label}</b>：正在从服务器准备文件 …（完成后会再提示）`, 4000);\n  let r;",
      "① dlExport 即时反馈")

# ── ② fetchResultModal ＋ 三条抓取结果弹窗化（core.js）
HELPER = (
    "\n/* ⭐⭐ 2026-09-21 用户口径「统一像集采台账」：**抓取是重动作**（登录 i8 · 可能顶号 · 全量刷新当月），\n"
    "   结果**必须弹窗回显**（条数 / 扶正 / 待人工 / 降级原因），⛔ 不是一闪而过的提示条 ——\n"
    "   用户要能看完再关。nt / wh / iv 三条抓取已全部改走本件（集采 m11 本来就是弹窗 = 参照形态）。 */\n"
    "function fetchResultModal(title, html) {\n"
    "  modal({ title, body: `<div class=\"bd\" style=\"line-height:1.95\">${html}</div>`,\n"
    "    footer: `<button class=\"btn pri\" data-act=\"closeModal\">知道了</button>` });\n"
    "}\n"
)
t = CORE.read_text(encoding="utf-8")
if "function fetchResultModal" not in t:
    anchor = "async function ntFetchBackend(m) {"
    t = t.replace(anchor, HELPER.strip("\n") + "\n\n" + anchor, 1)
    CORE.write_text(t, encoding="utf-8", newline="")
    print("✅ core.js: 新增 `fetchResultModal`")

# ntFetchBackend：成功 / 失败 / 被拒 三路都弹窗
patch(CORE,
  '  if (r.ok) {\n    await reloadNotices();\n    await reloadM02IfOn();     /* ⭐ 刚写的那条记录要**立刻**在记录卡上看到（见 `reloadM02IfOn`） */\n'
  '    return toast(`已抓取 <b>${esc(m)}</b>：i8 返回 <b>${r.fetched}</b> 条，落库 <b>${r.upserted}</b> 条`, 6000);\n  }',
  '  if (r.ok) {\n    await reloadNotices();\n    await reloadM02IfOn();     /* ⭐ 刚写的那条记录要**立刻**在记录卡上看到（见 `reloadM02IfOn`） */\n'
  '    return fetchResultModal(`抓取结果 · 付款通知书（API-01）`,\n      `已抓取 <b>${esc(m)}</b>：i8 返回 <b>${r.fetched}</b> 条，落库 <b>${r.upserted}</b> 条。`);\n  }',
  "② ntFetch 成功 ⇒ 弹窗")
patch(CORE,
  '  toast(`<b>抓取被拒</b>：${esc(r.message || \'未知原因\')}`, 9000);\n  try { await openOwnDialog(); } catch (e) { /* 打不开弹窗也不影响上面那句原因 */ }',
  '  fetchResultModal(`抓取被拒 · 付款通知书（API-01）`,\n    `<b style="color:var(--wn)">后端拒绝了这次抓取</b>：${esc(r.message || \'未知原因\')}`);\n'
  '  try { await openOwnDialog(); } catch (e) { /* 打不开弹窗也不影响上面那句原因 */ }',
  "② ntFetch 被拒 ⇒ 弹窗")
patch(CORE,
  '    return toast(`⚠️ 抓取失败：${esc(String((e && e.message) || e))}`, 8000);',
  '    return fetchResultModal(`抓取失败 · 付款通知书（API-01）`,\n      `<b style="color:var(--wn)">网络或服务异常</b>：${esc(String((e && e.message) || e))}`);',
  "② ntFetch 异常 ⇒ 弹窗")

# whFetchBackend：降级 / 异常 ⇒ 弹窗（成功段是拼 msg 的，末尾单独处理）
patch(CORE,
  '      return toast(`<b>抓取没能完成</b>，已<b>降级为手动导入</b>：${esc(r.message || \'\')}<br>`\n'
  '        + `<span class="mut sm">可到「导入」入口上传 i8 导出的 Excel（解析走同一条管线）</span>`, 9000);',
  '      return fetchResultModal(`抓取没能完成 · 收发结存（API-02）`,\n'
  '        `已<b>降级为手动导入</b>：${esc(r.message || \'\')}<br>`\n'
  '        + `<span class="mut sm">可到「导入」入口上传 i8 导出的 Excel（解析走同一条管线）</span>`);',
  "② whFetch 降级 ⇒ 弹窗")
