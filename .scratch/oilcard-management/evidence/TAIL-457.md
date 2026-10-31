# TAIL-457 验证记录

2026-10-31，分支 `codex/oilcard-management-20261031`，实施起点 `9371ecd17ca23dadf832c4dbfd1886b0f0225903`。范围为专门换卡、同实体卡号纠错提示、明确单笔历史关联更正及既有全局安全撤销。没有开始458。

## 实现及自动检查

复用现有档案/关联历程、账务快照、BusinessModal、AG Grid/Ant Design及HistoryControls。换卡为所选账户选已有副卡或同事务建新副卡，保留旧卡及旧账；同卡其他账户不变。旧账更正可明确项目、账户、实体卡，沿原版本保护，转账只改选中侧并同步双边版本。卡号录错仍更正同一实体，不以改号模拟换卡。

首次隔离检查暴露真实缺陷：同事务建新卡并改挂现存账户时，撤销先删卡、后恢复账户引用，外键拒绝。最小修复位于core/history：保持历史头、整批完整值/xmin及规则校验，目标依赖有效后先解除必要既存子行引用，再按原外键顺序删除和恢复。外部引用、后续修改、缺失目标依赖仍拒绝；没有改写旧operation_history。

- 最终 `backend_verify.py --source-env .env --test tests/test_oilcard_associations.py --test tests/test_oilcard_archives.py --test tests/test_oilcard_transfers.py --test tests/test_operation_history.py --test tests/test_layering.py -- -q -o addopts=`：68 passed in13.47s。父控直接核日志和JSON，报告组 `115644-527811-37808`，returncode=0，schema `backend_verify_d1d6a6827823445d92a15c1301b10233`和pytest临时目录均清理；首次失败资源亦已清理。
- 自动检查覆盖同卡只换所选账户、旧账/退款快照、归档及重新启用、幂等/版本/失败回滚、正常撤销重做、外部引用及后续修改拒绝、转账单侧关联及实际工作簿读回。父控检查了共享history差异和关键用例，未重复运行输入未变的整套回归。
- 前端关联、连续编辑、转账及保存队列定向10项通过，Corepack类型检查、设计机械检测和diff检查通过。父控按正式入口构建 `work/build-01`，退出码0后启动真实隔离预览。

## 内置浏览器代表路径

registered_preview先核源码、构建和schema身份，经已有API准备两个项目/账户共用同一副卡、充值1000的合成夹具。使用Codex内置浏览器登录专用预览账号：

1. 选账户甲，打开“换卡”专门弹窗，建立完整前导零新卡并填独立备注。保存后甲关联新卡，乙仍关联旧卡，各自账户备注保留。
2. 全局撤销确认明确显示“用卡账户换卡，涉及3项变更”；确认后甲回旧卡，重做后回新卡。两次均等明确完成状态再读取，关联历史可见旧卡、新卡、换卡动作及操作人。截图 `reports/replacement-history.png`已实际验看。
3. 从旧充值选“更正历史关联”，弹窗仍显示原卡，未被换卡追改。明确选新卡保存，再开弹窗读回新卡；全局撤销显示涉及1项变更，确认后旧账恢复原卡。
4. 刷新后甲当前关系仍为新卡、乙仍为旧卡；再次打开旧账弹窗，原卡、1000金额、原项目/账户及备注保持。截图 `reports/history-attribution-readback.png`已实际验看。定位账户行时一次hasText未匹配输入value，改用可见输入标签完成选行；该定位失败不计功能通过。

上述GUI不冒称已操作所有金额/归属组合；档案纠错、退款、归档及后续变更冲突由前述实际后端事务用例覆盖。没有模拟页面或真实账务写入。

## 资源与后续

预览 `127.0.0.1:8065`，PID37268，`mtrl_workbench_test` schema `frontend_rewrite_397_c14318e3b82341ed8437f5aa5af20c39`，迁移 `oil457261031`，synthetic=false/disposable=true。正常stop后进程退出码0，终端确认schema清理，owner为stopped-disposable。截图和夹具在 `.artifacts/active/oilcard-implementation/20261031-457/reports`；8000及8801未动。

用户要求本票保存后新对话继续剩余票。总票452不变，最终累计Standards/Spec独立审查尚未完成，真实接续及部署未执行。
