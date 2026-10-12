# TAIL-308: 登录不再按12小时自动过期

**What to build:** 保持长期登录，主动退出仍清除登录态；严格四段v2账号票、版本签名及其他校验保持。

**Blocked by:** None (can start immediately)

**Status:** claimed

- [x] 有效账号票跨12小时和长时间仍可验证。
- [x] 篡改、换密钥、旧三段票与错误结构仍拒绝。
- [x] 登录cookie持久保存，主动退出清cookie；真实浏览器保存期限如实说明。
- [x] 只用本clone代码、假密钥与隔离HTTP测试，不创建或访问真实数据库。

---

## Comments

**2026-10-12 · 开工。** 用户已确认取消12小时自动过期；本任务独占独立clone，基点f6e13b018501a8aba9d0ba4debd059759209f050。308在clone及源仓票文件中未占用。交接明确要求主计划和公共索引由集成统一更新，因此本轮只建票文件，不运行会同时改索引的_tail_open.py。实现与测试完成后留未提交供独立复核，不部署或重启服务。

**2026-10-12 · 实现。** 删除服务器的时间过期分支；新票第三段为签发时间戳，仍是严格四段v2账号票，时间字段仍需为整数且包含在签名内。已有合法v2账号票的原过期戳亦不再导致服务器拒绝；全部旧三段标签票仍拒绝。签名、密钥、身份类型、账号解码及写闸保持。登录响应Max-Age改为34560000秒（400天），HttpOnly / SameSite=Lax / Path=/ / 局域网HTTP属性保持；退出仍由端点清cookie。更新阈值表原12小时条目，既有验签判据同步为长期有效。

**2026-10-12 · 隔离核验。** 先用跨12小时及3650天两条断言复现原实现失败（rc=1），删除过期判断后通过。最终命令：`D:/dev/mtrl-workbench/backend/.venv/Scripts/python.exe -B -X utf8 .codebuddy/work/00-scratch/tail308-verify.py`，rc=0；26项通过，0失败/错误/跳过，pytest回执耗时1.622秒，验证入口含导入检查总耗时3.435秒。结果在`artifacts/tail308-green-results.json`、`artifacts/tail308-junit.xml`与`artifacts/tail308-import-paths.json`。191个app/tests模块全部加载自本clone；源仓Python仅提供解释器/第三方依赖，clone无.env。假密钥、假账号查询、内存HTTP及数据库禁止调用守卫覆盖登录/写闸/退出，无真实数据库参与。

**2026-10-12 · 反向灵敏度。** 命令：同一解释器运行`tools/mut/_mut_long_login.py`，rc=0；正常输入及复原输入通过，9/9隔离靶明确行为断言造红（恢复时间过期、恢复12小时cookie、漏清退出cookie、漏验签、放行未知版本、接受旧三段票、漏验整数时间字段、写闸仅看cookie存在、接受空身份）。仅改scratch副本，正式源码字节未变；回执`artifacts/tail308-mutation-results.json`。首次漏清cookie靶报KeyError，未计为通过；补上清cookie响应存在的明确断言后重新完整验证。

**2026-10-12 · 浏览器与权限。** 命令：同一解释器运行`.codebuddy/work/00-scratch/tail308-browser.py`，rc=0；独立Chromium 151.0.7922.34接受真实登录端点发出的400天cookie，退出端点发出的删除响应清空cookie；回执`artifacts/tail308-browser-results.json`。全部虚拟站点请求被截获，无监听服务或真实网络。Chrome公开上限依据：https://developer.chrome.com/blog/cookie-max-age-expires 。普通沙箱的Python事件循环卡在内部socketpair初始化；常规审批后同一HTTP测试正常完成。未改网络设置、权限或Git配置。

**2026-10-12 · 边界与交接。** 浏览器可提前清理cookie；本实现不在请求间自动刷新其保存期限。已经存入浏览器的旧cookie仍带原12小时Max-Age，需要重新登录一次才能取得新400天cookie；清理登录数据后需重登。退出沿用清客户端cookie的既有方式。未运行需要真实数据库的用户管理回归、全站pytest、生产真机或服务重启；未修改主计划/公共索引，未提交/推送/部署。验收已成立，票保持claimed供集成独立复核后统一销号。py_compile、git diff --check及7件bytes_guard均通过（必须修0）。

**2026-10-12 · 独立复核与本地提交授权。** 集成任务明确通知独立复核无阻断，授权只提交本票及已报告的其余6文件到codex/long-login；主计划/公共索引仍由集成维护，不推送或部署。已核实HEAD仍为原基点、没有先前的重复提交，暂存区严格核对为7件。

**2026-10-12 · 提交检查与边界。** 使用项目自带ops/install_hooks.ps1在本clone安装原版pre-commit，不改Git配置。clone无backend/.venv，因此实际钩子会提示跳过，不能声称钩子全绿。另用源仓已有解释器逐项显式运行钩子6项：syntax_audit --staged、audit_work、mut_cover --check、bytes_guard --staged通过（rc=0）；doc_audit与audit_meta未通过（rc=1）。检查所需本clone基线路径以不含凭据的临时.env提供并在finally删除；变异台账由原生成器生成到忽略的artifacts，未暂存。

doc_audit报告12条红：7条缺本机产物/venv配置/服务工具/历史截图的T3、2条缺忽略目录的T25、2条缺完整acc_results.json而无法复用四态的T4、1条本票按交接未入公共索引的T6；audit_meta仅此T6一条红。未伪造完整四态、复制源仓产物或修改禁止更动的公共索引；上述审计由集成环境完成。完整回执为artifacts/tail308-precommit-results.json及对应txt；现有26项业务隔离回归、9/9反向与浏览器验证仍有效，产品代码及测试未再变化。
