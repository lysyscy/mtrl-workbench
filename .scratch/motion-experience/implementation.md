# 自然连贯动效

用户于2026-11-06授权实施、审查、提交正常推送；生产部署单独授权。目标Q2，约束Q1/Q6/Q7，附件仅为质量参考。

基线：master 7c4049737012776e3766afdf983d698cf3696553。已有frontend-design、status及未跟踪设计资料由原任务持有，保留不混入提交。

动效主张：工作区切换表达相邻任务的空间接续；浮层从触发上下文进入并有完整退出；展开通过尺寸变化说明内容关系。操作即刻生效，不等待动画；表格刷新、保存和行数据不重复入场。导航是主要体验，弹窗和展开用不同节奏辅助。

候选：A使用现有AntD/rc-motion与原生CSS/WAAPI；B使用Motion的可中断弹簧/布局能力，保留AntD焦点与关闭协议；原生View Transitions单独评估快照、交互和中断成本。先在实际代表入口对比，再决定推广，不自制引擎。

运行组：`.artifacts/runs/motion-experience-20261106`，baseline为统一入口生产构建。新建唯一8065可丢弃真实副本，来源只读，外部i8/打印阻断。录屏和trace仅本机保留，不提交业务图像。

验收：同浏览器1920×1080、字号1.12，同真实数据与预热动作，页面/弹窗/展开至少各5轮，加入快速反向与输入、滚动、选择保留及减少动态效果。类型检查、相关现有回归、必要独立审查，结束后保存最终效果入口和最小证据，清理被替代尝试。

## 已执行与当前进度

- baseline / native / motion 各完成同脚本5轮真实副本生产录屏，位于本run/reports对应目录；原生候选关闭仍突卸载，Motion presence补齐退出。选用Motion14.10.0 MIT（本机许可与npm元数据核实），保AntD6.6.7/rc-motion1.3.3，details用原生CSS。业务源码在主检出改，无附加工作树。
- 已覆盖全站PageSurface、侧栏指示、油卡保活工作区/标签、appearance与各域条件弹窗。非条件modal继续由AntD open驱动；明文密码查看保即时关闭。使用稳定ReducedMotion Provider，不重建账号树。
- 第一轮161项unit通过，15项真实副本browser回归通过。两位独立审查者motion_standards、motion_spec（GPT-6.1 Sol/high，fresh context）找到退出期pointer/ESC/aria、历史guard与收票锁的重开竞态、外观双占位/晚归焦、方向与rc提前结束问题；均修正，源码窄复查已确认无新增实质发现。嵌套子窗离场期间的Esc层栈遵循AntD默认，不自建键盘路由。
- 无录屏正常/减少动效对照发现切页额外长任务；CPU profile已排除导航marker与details，捕获AntD transition:all在继承visibility上产生240/320ms过渡，伴随表格重复测量。工作区输入/选择根控件已限为color/background/border/shadow反馈，网格内控件即时更新；页面、标签和portal浮层的运动保留。
- 最终构建work/validation-04通过。20个不同的浏览器场景已通过：regression-02中18项通过，一项自动聚焦断言按已实测AntD默认首控件焦点修正后单独通过；最后CSS修正后复验7项（含新增受控弹窗中途减动效），全部通过，复用未改业务路径的已通过结果。原失败是断言文本框必须自动聚焦；保留了“退出框中心不拦点击、离场中减少动效正确收尾”断言，并验证新窗焦点和实际输入。
- Impeccable机械检测一次已执行，结果[]。原docs/status末尾空行造成git diff --check非零，属于进入前已存在差异，不擅自清理。
- 前端总JS gzip（所有懒加载块加总）baseline857793 bytes，完成版905633 bytes，增47840 bytes；不是首屏传输量。CPU Ryzen5 5600GT（6核12线程），约32GB内存，Chromium156.0.8078.4，1920×1080、deviceScaleFactor1、字号1.12；无CPU/网络限速。
- 最终无录屏5轮正常/减少动效交替采样，正常动效点击→下一rAF中位：通知书158.6ms（150–175）、项目111.2ms（106.7–122.2）、弹窗开19ms/关13.6ms、展开14.3ms/收起8.2ms。弹窗/展开无50ms以上long task。切页仍有渲染长任务，正常最大帧间隔233.3ms；这是本机代理指标，不是线上INP，也不声称全程60fps或相对原版的严格性能提升。
- 最终baseline/final各5轮录屏、trace及独立连续操作录像完成，均无pageerror。连续操作包括快速导航反向、动画中输入、3轮快速开关、弃稿/恢复、油卡标签反向、外观关闭后焦点、1280×720弹窗和运行中减少动效。查看了最终逐帧序列、稳定真实通知书画面及紧凑弹窗，进退过程完整，未见残影/遮挡/状态丢失。
- 原版与完成版trace中的项目、通知书接口响应逐字节相同（SHA256对照已存），数据为20项目/13在建、1261通知书。油卡副本0账户/0卡，只核实际空态工作区，未冒称有数据油卡台账覆盖。
- 核心选择来自Motion官方布局/Presence/减少动效示例、Ant Design动效与IBM Carbon实践，以及MDN原生details/View Transitions文档。原生CSS版本成本低但条件弹窗直接卸载；选Motion管理成熟插值/presence，AntD继续持有modal行为，原生details不额外造引擎。View Transitions未接路由，避免快照与中断队列影响高频输入。引用及依赖退出方式已归frontend-design。
- 最小证据已按哈希复制到`.artifacts/runs/motion-experience-evidence-20261106/reports`，入口index.html与comparison.mp4（左原版、右完成版）；其余原始webm/trace、样本、XML与连续检查保本机，不上传业务画面。已核PersonalSkillArtifactCleanup存在；证据组待收尾close30天，最终预览单独保留。

## 待完成

1. 明确暂存本任务文件；frontend-design原有dirty部分不能混入提交。真实钩子、正常push并核remote SHA/CI。源码保存不部署。
2. 清理本轮无用候选/脚本和重复视频；必要证据30天登记，最终预览保留具名用途；本任务.scratch按保存提交/原路径退出检查。run active中不得close或删除在用构建。现有未注册/他人资料保持。
