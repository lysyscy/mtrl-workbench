# 旧前端生命周期与读取参考

本件仅在 backend/app/web 仍运行时使用。React 对应接管及旧实现退休实际完成、独有消费者退出后，必要共用意图归现行主人并删除本件；票 done 本身不足以证明这些条件。

index.html 定义真实脚本顺序。页面渲染 V、交互委托 ACT/BIND、API 适配各守职责；change 直接委托 ACT，不恢复 CHG 名单。脚本加载期不访问尚未初始化的后载 const；新增资源须核真实静态路由。读取源码用 shell_source/shell_api，不能只看 index 单文件。

LOADED 表示拉过/缓存，PENDING 表示正在拉，FAILED 表示失败；不能拿未 LOADED 当 loading，否则跨页全标脏会卡页。pageState/pageGate/retryPage/markPending 共用；未 ready 不走虚拟化/绑定/浮层放置。写后通过 API 统一失效，进页只拉自己必要路径，保存与读回错误分开。派生量在 reload 时重算，候选与真实数据同源。

API 金额为字符串，适配层显式转数字再显示/求和，ID 统一 String；分类内部英文值只在显示出口转中文。集采列表五个派生金额直接用后端 inv_sum/trade_inv_sum/settle/pay_sum/debt，不能依缺少的子表数组再算。所有普通取数走 rawFetch，人话错误走 errHuman；导出下载保自有错误处理。

虚拟表的选择/合计基于完整行集合，不能靠当前 DOM。重画后恢复横纵滚动、选中、编辑与焦点；延迟响应核当前身份/范围。TBL/FBAR/PJB 不隐式塞换行；模板字面量会规范行尾，需要逐字节核验时按实际渲染结果判断。

项目/时间面板内探索只局部更新浮层，确认筛选才改业务表。PJB/pjToggle 使用真实锚按钮，替换与外部点击按 composedPath；pjwrap/pjpop 由 placePops 提升 fixed 逃出 card 的裁剪，两条渲染路径都调用，不全局放开 overflow。projPanel 唯一实现候选搜索与归档折叠，applyPjFilters 在两条渲染路径收尾。空态统一 EMPTYROW/EMPTYBOX，域给人话与下一步。

sticky 合计落在 tr.sumrow 而非其 td，并核所属 .tw 滚动容器；不能仅抄旧原型。get/set 配置、渲染/修改和资源生命周期改动需按实际调用核验，不用历史函数清单或页数量代替。人眼和真实 DOM 核显示，源码含字串不证明上屏；折叠 details 读 textContent 或展开后观察，innerText 可为空。
