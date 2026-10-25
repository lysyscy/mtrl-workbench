# TAIL-443: 保活页面更新边界与库存重复计算收敛

**What to build:** 保活页面更新边界与库存重复计算收敛

**Blocked by:** TAIL-442

**Status:** done

- [x] 用已访问页面前后对照定位并减少不相关保活页随路由/共享状态重渲染，保护账号树、草稿、滚动、选择、历史guard与离页暂停。
- [x] 仅针对已核重复计算稳定边界/派生值，复用已有React与Query；不全局改staleTime、不关闭新鲜度/校验、不引入Worker或分页新契约。
- [x] 实际轨迹或有效渲染计数与同条件交互证明减少重复工作，数据/金额与完整结果等价，迟到401/换号/失败保稿及跨页返回回归通过。

## Comments

2026-10-25 · Created.

2026-10-25 · 用户已授权按research结论开票并串行推进P0→保活→动效。固定累计起点2758b889c032a083ac1b5f336f0c507889094c5d；唯一整合者为本会话，开工clean，React/master公共高水位均441。范围、方法与证据边界回[研究](../../frontend-vue-rewrite/research.md)及[共同规格](../../frontend-vue-rewrite/spec.md#442444流畅度实施)。不更换字体、不扩为分页/Worker/全站换库；金额与写入契约不变。

2026-10-25 · done: Agent按本次授权技术完成。保活注册组件memo、历史context值稳定，只向台账传其变化状态；不引入Activity、不改身份或staleTime。库存候选值只在打开筛选时按依赖计算、预备活跃过滤，空过滤保原数组引用并复用同范围原sumRows汇总，金额校验与精度不变。诊断专用构建仅做调用计数：14页预热后3对往返，Home/I8/Settlement/Mechanical/Rules各6→0，Process/Big/Fees各10→1；Projects等路由/context订阅仍会更新，Flow9→12未消灭，不冒称全部冻结。计数后恢复正常构建，同条件10次清筛选事件中位240→160ms（442为192）；输入148→88ms（442为84，微小差异保留）。类型/生产构建与9项真实独占合成PG回归全过，覆盖跨页草稿/选择、账号丢失重建、月份/弹窗、库存过滤/金额/调整/拒绝/未知/导出和全文几何；schema均清理。原始render-counts-{before,after}.json、interactions443.json及keepalive443-tests.log留本机本run。最终全站对照、动效与累计双轴归444；8000/423/424不动。
