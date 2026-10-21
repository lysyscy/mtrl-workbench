"""`MOD-15` 的**登录页**（§1.5.1「退出后**回到登录页**」）。

⚠️ **为什么 `MOD-15` 明明"无服务端渲染页"，却有这么一页**：
   登录页是**壳之外**的一页（未登录时你还没进壳体）⇒ 它只能由服务端给。
   ⛔ 这不违反"从第一天起就是 JSON API ＋ 新壳"——**账号管理**仍然是壳体里的一页。

⚠️ **不用 JS**（纯表单 POST ＋ 303 跳转）：
   登录页是全系统**唯一**"进不去就用不了"的页面 ⇒ 它出问题 = 谁都进不去。
   ⭐ 少一层 JS，就少一处"脚本没加载出来、页面却看着正常"的失效形态。
"""

from __future__ import annotations

from html import escape

_PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>登录 · 材料报表自动化工作台</title>
<link rel="stylesheet" href="/static/theme.css">
<style>
  /* ⚠️⚠️ 颜色**一律走 `var(--…)`、⛔ 一个色值字面量都不许出现**（含 `#fff` 与 `rgba(...)`）——
     这是本仓的主题铁律，`tests/test_theme.py` 会**全工程扫**（连内联 `<style>` 也算）。
     ⭐ 变量名一律用**主题表里真有的**（`--bg` `--sf` `--bd` `--tx` `--mut` `--pri` `--dg` `--dg-l` `--on` `--shadow`），
        ⛔ 别自造 `--fg` / `--card` 这种"看着像"的名字：那样既不生效、又不报错（最坏的一种）。*/
  body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
        background:var(--bg);font:14px/1.6 var(--fs);color:var(--tx)}}
  .box{{width:340px;background:var(--sf);border:1px solid var(--bd);
        border-radius:var(--r);padding:24px 22px;box-shadow:var(--shadow-md)}}
  h1{{margin:0 0 4px;font-size:17px;font-weight:600}}
  .sub{{margin:0 0 16px;font-size:12px;color:var(--mut)}}
  label{{display:block;font-size:12px;color:var(--mut);margin:10px 0 4px}}
  input{{width:100%;box-sizing:border-box;padding:8px 10px;border:1px solid var(--bd);
         border-radius:var(--r);font:inherit;background:var(--sf);color:var(--tx)}}
  button{{width:100%;margin-top:18px;padding:9px;border:0;border-radius:var(--r);cursor:pointer;
          font:inherit;font-weight:600;background:var(--pri);color:var(--on)}}
  .err{{margin:14px 0 0;padding:8px 10px;border-radius:var(--r);font-size:12.5px;
        background:var(--dg-l);color:var(--dg)}}
  .foot{{margin:16px 0 0;font-size:11.5px;color:var(--mut);line-height:1.7}}
</style></head><body>
<form class="box" method="post" action="/m15/login">
  <h1>材料报表自动化工作台</h1>
  <p class="sub">请用科室账号登录</p>
  <input type="hidden" name="next" value="{next_url}">
  <label for="acc">登录账号</label>
  <input id="acc" name="account" autocomplete="username" autofocus required>
  <label for="pwd">密码</label>
  <input id="pwd" name="password" type="password" autocomplete="current-password">
  <button type="submit">登录</button>
  {err}
  <p class="foot">系统内账号由管理员在「用户管理」页创建。<br>
     忘记密码？找管理员在「用户管理」页查看或重置（明文保存，见 §1.5.1）。</p>
</form></body></html>
"""


def login_html(*, error: str = "", next_url: str = "/app") -> str:
    """登录页 HTML。

    ⚠️ `next_url` 与 `error` **一律转义**再拼 —— `next` 是**用户可控的查询参数**
       ⇒ 不转义就是一个反射型注入点（而且它在**登录页**，全系统最不该出问题的一页）。
       ⚠️ `next_url` 还会在路由层被**收窄**到站内路径（⛔ 防开放跳转，见 `api.api_login_page`）。
    """
    block = f'<div class="err">{escape(error)}</div>' if error else ""
    return _PAGE.format(err=block, next_url=escape(next_url or "/app"))


__all__ = ["login_html"]
