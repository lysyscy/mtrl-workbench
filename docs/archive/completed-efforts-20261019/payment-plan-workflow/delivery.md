# 原表付款计划核对skill交付

用户最新范围：保留系统付款计划，先做skill；加入向通知书写拟付款方式的能力。生产迁移、服务加载和具体业务回写本轮未执行。

源：skills/payment-plan-audit；Skills Manager库ID877236e1-3546-485f-a2be-2114add22a3d，local来源指向本仓，已显式部署Codex。install-verification.json核对源/中央库/真实部署的5个文件SHA相同，installed-smoke由真实部署脚本离线复跑成功。没有改个人通用技能源。

真实原表：桌面2026.10.12第四工程公司10月汇总，SHA97753b7f7f1a61cb016d0f0f1bd02a244c5ee5301f3181efc9135e007799b051。仅材机工作表：9项目143明细、196非空行全分类，明细计划合计19099428.50。原件未保存/重算/修改。

result-final为最终现场只读取数报告：采集时间2026-10-15T16:49:35+08:00，系统全月份通知书和全部生效流水，不访问i8。69行核对通过，74待人工核对；金额规则完全匹配120不等于最终通过。原表E81/E82各少计259250，E154/E157受E153缺值影响无法独立确认。其他4工作表未核。69条拟方式候选仅预览，SHA1131fab7b29bfb9cb81d47398abe2b440c17df590051ec8f48b008ce4efc1bc7；绝非业务写入授权。

能力：只读快照用PostgreSQL显式只读REPEATABLE READ事务；复用现有六类金额及项目匹配规则；报告并排原报/系统项目、收款单位与金额；缺金额/现金/重号/归属不明/剔除撤单不入回写。回写先验证用户确认的预览SHA、源SHA、库身份，短事务锁通知书与流水，复查唯一性、归属、原拟方式、审批/生效已付；全部通过后只更新planned_pay_method。失败回滚整批，回执pending不可当作成功或自动重试依据。

后端配套：新迁移c350261015(parent c313261012)；通知书本地拟方式默认空、i8重抓保护、列表API/前端传递；实际付款默认依次本次手改、通知书拟方式、系统原计划、现汇。原付款、打印和付款计划均保留。加载新后端前必须先迁移目标库，当前现场字段不存在，未重启。

验证：skill离线测试14 passed/exit0；后端离线与浏览器选集53 passed/exit0，见planned-method-acc.json。独立实际表复跑及审查见skill-review.md；其最后一个E196空汇总噪声亦已修正并重跑。quick_validate exit0，git diff --check exit0。syntax/bytes/ui_parity/wiring/chain/asset/claim/prg共8检查exit0；chain原锚同步至新默认取值函数。

总检查未全绿：doc_audit --ui exit1，剩T18仓外归档根D:/dev/.归档-mtrl不存在；交付面_doccheck另报素材包1103/1104计数差。未改无关归档或素材。自动按影响入口--explain对新skills脚本与任务输出缺分类而exit1，没有绕过报通过；已依据真实依赖直接执行上述定向检查。开票工具因T18回滚，未产生TAIL-350；不伪造票状态。

保存：改动已落盘，保留开工已有dirty；未提交/推送（总检查仍有上述阻断）。未执行PostgreSQL真实迁移/业务回写/付款/打印/i8，未检Excel视觉排版。源目录维护后通过Skills Manager update/deploy更新，不能只改部署副本。
