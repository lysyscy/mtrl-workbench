# TAIL-308: 登录不再按12小时自动过期

**What to build:** 保持长期登录，主动退出仍清除登录态；严格四段v2账号票、版本签名及其他校验保持。

**Blocked by:** None (can start immediately)

**Status:** done

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

**2026-10-12 · 主目录本地整合与单次最终组合核验。** 用户已授权本地整合，不推送部署。源clone干净、分支codex/long-login、7文件提交f4365f63e8cad7276d28248f7e131b550e11ca3b及父f6e13b0已核验。先精确提交B1十件为a5be5d7（真实pre-commit六项全绿），再无冲突cherry-pick -x为551174a8f96c7c3a91b31f12db650ea8ad2b8bf6；源产品代码及六个非票文件逐项一致。旧长期登录四草稿已完整ZIP/哈希归档并精准移出，Git状态无草稿；临时恢复脚本会拒绝覆盖最终实现。归档和核验回执仍在scratch，未删除。

最终命令：`backend/.venv/Scripts/python.exe -B -X utf8 .codebuddy/work/00-scratch/tmp-20261012-b1-308-combined.py`。原B1的110件完整包含，加登录/身份实际影响选集共130件；单次pytest **1032通过、0失败、0错误、0跳过**，pytest输出108.02s，含启动进程回执111.386s，rc=0。测试HEAD=551174a8f96c7c3a91b31f12db650ea8ad2b8bf6；正式app/tests与临时副本逐文件SHA256一致，运行前后两端未变，没有还原/替换登录源码。完整输出、JUnit、命令/选集/输入哈希及相对f6e13b0的diff在`artifacts/b1-tail308-combined/run2/pytest-output.txt`、`artifacts/b1-tail308-combined/run2/junit.xml`、`artifacts/b1-tail308-combined/run2/result.json`与同目录input-snapshot.json/input-diff.patch。

首轮1027通过/5失败（146.89s）的日志与JUnit保留在`artifacts/b1-tail308-combined/`，5项分别为假i8测试缺假服务地址和副本缺.gitignore；仅补隔离环境后完整重跑130件，未改产品代码或削弱断言，不用补验算术累计充作最终通过。假密钥/账号/i8配置，临时.env只有假开发库地址；实际DB限定127.0.0.1:5432/mtrl_workbench_test，B1回滚用例外层事务/SAVEPOINT整体回滚。所有本任务DB回归串行，通知书线为独立假数据；无生产库、真实凭据、真实i8或运行中服务操作。

最终输入反向：B1 8/8、会话唯一身份7/7、长期登录9/9均正常放行/明确断言造红/复原放行，正式源码字节未变。完整输出与耗时见`artifacts/b1-tail308-combined/integration-mutations.json`及两个txt；长期登录新跑回执为`artifacts/tail308-mutation-results.json`。浏览器`artifacts/tail308-browser-results.json`是保全的源clone既有回执（SHA256=7141d2d16c312c8d063d0cf9e3e4501efa777bb3fef8060acc4a4e65401dfc51），400天及退出清理已在源clone验证；整合对应代码完全一致，未冒称本轮重新跑浏览器。

主目录初审doc_audit红3（两份源回执不存在及308未入公共索引）、audit_meta红1（索引）、mut_cover失配；逐项重跑/保全回执、用_tail_open隔离副本干跑/应用/T6核验后转入索引，保留源票历史，登记新反向脚本并重生成131件覆盖台账；主目录doc_audit已必须修0。源clone的12红属于其环境历史，本轮没有豁免或伪造四态。销号与文档回写后适用终检全输出见`artifacts/b1-tail308-combined/final-checks.json`；本地治理提交后最终SHA、代码输入不变与完整最终diff绑定见同目录final-commit-binding.json。

本轮不部署、重启服务或推送；当前运行服务尚未应用这两项代码。只完成所选回归，不刷新完整权威四态；TAIL-284/287及D共享workbook机制未动。浏览器保存400天上限及主动清理仍可能要求重登，旧cookie原保存期限不变，需重新登录取得新cookie。历史原独立clone阶段的“不访问数据库/未提交”记录仅描述当时阶段，当前以本次组合记录与Git链为准。
