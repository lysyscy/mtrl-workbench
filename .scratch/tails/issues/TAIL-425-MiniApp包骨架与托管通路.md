# TAIL-425: MiniApp 包骨架与托管通路

**What to build:** 仓库里出现一个能被本机托管起来的 Mini App「付款原表核对台」：包落在 miniapps/payment-plan-audit-desk/，publish → inspect → open 三步走通，打开后是一个明暗主题齐备的空壳页；后面六张票都在这个包里做。

**Blocked by:** None

**Status:** needs-info

- [ ] `miniapp.init` 返回的 packagePath 落在 `miniapps/payment-plan-audit-desk/`，不另造目录；manifest 的 `agentAccess` 是字符串 `"session.run"`（不是数组）
- [ ] `publish` → `inspect` → `open` 三步走通；`inspect` 能读到包身份与 client、node 两个非空 payload 根
- [ ] 在 `miniapp.open` 托管的那个标签页里能打开页面；用普通 Browser 标签页打开会 401（属预期，报告里写明）
- [ ] 页面用 `--mcode-*` 变量；明暗双主题都可用，`prefers-color-scheme` 能映射到 `data-theme`，不强制明暗
- [ ] 语义化 HTML、连续标题层级、交互元素有可见文本或 aria-label、可键盘访问、状态消息带 `role="status"`；不用 emoji、不引远程字体/图片/CDN
- [ ] 加载、空、错误三种状态在页面上真实可见，出错时保留页面结构而不是整页崩
- [ ] 未新增任何后端端点、未改动 `backend/`、未改动 `skills/payment-plan-audit/`

规格：[付款原表核对台 Mini App 规格](../../miniapp-payment-plan-audit/spec.md) §6–§7、§10 步骤1；界面口径：[前端设计守则](../../../docs/guides/frontend-design.md) §0–§9；边界：[D34](../../miniapp-payment-plan-audit/spec.md)。

验证类型：宿主工具实调（init／publish／inspect／open）＋托管标签页里的真实页面检查。本票不涉及数据库与写库。

---

## Comments

**2026-10-28 · 用户暂缓。** 用户当前暂不准备实施Mini App，本票改为needs-info；规格和技术依赖原地保留，待用户以后重新安排。当前状态回[规格](../../miniapp-payment-plan-audit/spec.md)。

**2026-10-22 · 建票（agent）。** 来源：用户2026-10-22确认Mini App七票及依赖｜不做会怎样：没有可托管的包，后面六张票全部无处落地｜落点：[TAIL-425](TAIL-425-MiniApp包骨架与托管通路.md)｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①只做包骨架与托管通路②后续票都要一个能跑的包③独立成票才能单独验证④依赖和验收见本票

**2026-10-22 · 授权与执行入口。** 已按用户确认的七票与依赖建票；后续采用 implement-solo-spec 推进。本轮仅建票与立规格，**尚未授权开始实施**。ready-for-agent 只表示任务已说清，仍需实施启动授权；真实写入（TAIL-428）须用户单独授权。

**2026-10-22 · 建票核验（非实施）。** 已核7个票文件与规格 §10 实施分解逐项一致、依赖无环（425→426→427→{428,429,430}→431）、每张票的 What to build 为用户视角单句、验收项可证伪。TAIL-428按用户裁定不含真实写入（真写另待授权）。doc_audit 退出0，必须修0（疑似33、已豁免15，与本轮建票前同）；票仓与主计划 §15／§14.3 同步完成，活跃计数已按真源重算。尚未实施、未建包、未运行应用测试；真实写入回 TAIL-428、真机检查与交付报告回 TAIL-431。
