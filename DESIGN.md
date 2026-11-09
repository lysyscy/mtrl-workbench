---
name: 材料工作台
description: 专业、安静、有秩序的材料科专业案台
colors:
  primary: "var(--pri)"
  primary-hover: "var(--pri-d)"
  primary-soft: "var(--pri-l)"
  on-primary: "var(--on)"
  canvas: "var(--bg)"
  surface: "var(--sf)"
  surface-muted: "var(--sf2)"
  border: "var(--bd)"
  border-strong: "var(--bd3)"
  text: "var(--tx)"
  text-secondary: "var(--tx2)"
  success: "var(--ok-d)"
  warning: "var(--wn-d)"
  warning-soft: "var(--wn-l)"
  danger: "var(--dg-d)"
  info: "var(--bl-d)"
  sidebar: "var(--sb)"
  sidebar-text: "var(--sb-tx)"
  sidebar-selected: "var(--sb-on)"
  sidebar-selected-text: "var(--sb-on-hl)"
typography:
  title:
    fontFamily: "var(--fs)"
    fontSize: "calc(18px * var(--fscale, 1))"
    fontWeight: 600
  body:
    fontFamily: "var(--fs)"
    fontSize: "calc(var(--font-ui-size, 13.5) * 1px * var(--fscale, 1))"
    fontWeight: 400
    fontFeature: "tnum"
  label:
    fontFamily: "var(--fs)"
    fontSize: "calc(12px * var(--fscale, 1))"
    fontWeight: 500
  control:
    fontFamily: "var(--fs)"
    fontSize: "calc(12px * var(--fscale, 1))"
    fontWeight: 400
rounded:
  input: "var(--radius-input, 6px)"
  card: "var(--radius-card, 8px)"
  inner: "var(--radius-inner, 6px)"
  tag: "4px"
spacing:
  group-small: "8px"
  group: "16px"
  section: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.control}"
    rounded: "{rounded.input}"
    height: "calc(32px * var(--fscale, 1))"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.control}"
    rounded: "{rounded.input}"
    height: "calc(32px * var(--fscale, 1))"
  button-danger:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.danger}"
    typography: "{typography.control}"
    rounded: "{rounded.input}"
    height: "calc(28px * var(--fscale, 1))"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.control}"
    rounded: "{rounded.input}"
    height: "calc(32px * var(--fscale, 1))"
  navigation:
    backgroundColor: "{colors.sidebar}"
    textColor: "{colors.sidebar-text}"
    typography: "{typography.body}"
    rounded: "{rounded.input}"
  status-pending:
    backgroundColor: "{colors.warning-soft}"
    textColor: "{colors.warning}"
    typography: "{typography.control}"
    rounded: "{rounded.tag}"
    padding: ".1em .5em"
  container:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    typography: "{typography.body}"
    rounded: "{rounded.card}"
  grid-summary:
    backgroundColor: "{colors.surface-muted}"
    textColor: "{colors.text}"
    typography: "{typography.body}"
---

# Design System: 材料工作台

## Overview

**Creative North Star: "材料科专业案台"**

专业、安静、有秩序；支持密集核对，按任务区分密度，关键内容与操作清楚可达。“材料科专业案台”描述熟手处理、核对和修订业务数据的工作环境，不改产品名称。

控件紧凑、清楚、可发现：按钮保按钮外观，可编辑值有明确输入外观，悬停、聚焦、禁用和错误可辨；正常保存反馈安静，需处理的问题贴近对象保留。信息层次帮助使用者识别对象、金额、归属和下一步。

**Key Characteristics:**

- 熟手直接操作，业务对象和关键数值清楚可达。
- 表格密度随任务安排，编辑与保存期间保持稳定。
- 主题角色共用，状态含义不随主题改变。
- 普通表面平稳，浮层通过层叠、边界和必要阴影表达前后关系。

本文件最初于2026-10-29从当时规范、React共享源码及当时8000实例的首页/通知书页提取。2026-11-07按当前规范及源码同步动效；本次未重新进行界面验收。它是设计上下文入口；交互和页面例外由[前端设计规范](docs/guides/frontend-design.md)持有，业务规则回[需求](docs/requirements.md)，产品定位见[PRODUCT.md](PRODUCT.md)。变量引用用于消费既有主人，未建立另一套运行时色值表；非文本对比度与新页面字段组织按用户2026-11-07确认的规范维护。

## Colors

默认主题是“中性灰白＋清晰蓝色交互”。账号可选择中性浅色（存储名“默认”）、松绿、暖色纸面、深侧栏、深色、高对比、玫瑰柔粉和丁香浅紫；实际主题由各账号偏好决定。

### Primary

主强调色承担主要操作、编辑焦点和当前选择；较深角色用于悬停与强调文字，柔和底色用于选中背景。配对的主色上文字角色随主题提供。按钮、表格和业务页面消费同一组角色。

### Neutral

页面底、主表面和内层分组底建立安静的层次；普通边界与控件边界各有角色。正文与辅助文字区分阅读层级，辅助文字仍是有效信息。侧栏背景、文字、悬停和选中消费侧栏专属角色，兼容深侧栏及深色主题。

### Semantic

成功、警告、危险、信息使用各自深色文字和相应软底/边界。状态标签与类别标签分别取角色；完成、待处理、错误、撤销及业务类别都有完整文字。合计依靠位置、字重和底色突出，金额正负本身不触发红绿异常色。

**The 单一主题来源 Rule.** 色值由[主题主人](backend/app/mod03_notice/page.py)维护，[React主题消费](backend/app/mod03_notice/theme_react.py)同时服务整页和主题预览；新组件引用角色，不在业务CSS复制配色表。

**The 语义稳定 Rule.** 更换账号主题不改变成功、警告、危险、信息和类别的含义；重要状态同时通过文字、位置或形状表达。

普通有效文字及占位文字的现行要求为至少4.5:1，大字号为至少3:1；实际合规仍需按具体主题和状态核验。侧车文件中的八步色阶仅为面板预览合成，跟随角色变量，不是新增主题或可直接用于业务状态的令牌。

## Typography

**Body Font:** 本地官方MiSans，回退到Microsoft YaHei、PingFang SC、system-ui和sans-serif。标题、正文、表头及控件使用同一字体体系，保持中文、编号和数字的阅读连续性；字体来源与许可由[字体清单](backend/app/web/fonts/misans-web/manifest.json)持有。

### Hierarchy

- **Title:** 页标题及业务弹窗标题，使用前置令牌中的标题角色。
- **Body:** 正文与业务数据，普通字重；数字采用等宽数字特性，金额右对齐。
- **Label:** 表头、分组标签和导航分组，中等字重；不把有效表头缩成装饰性小字。
- **Control:** 紧凑按钮、日期和选择控件的文字；表格内原生数字编辑器可沿正文大小，不强制全站一刀切。
- **Totals:** 沿对应正文大小使用600字重，并与金额列对齐。

字号档位为1、1.12、1.25、1.4。文字、控件和网格几何按当前账号档位协调变化；前置令牌保存缩放公式，不能把某次浏览器实测大小当成固定基准。按基准计算，1.12档正文为15.12px，标题为20.16px，表头为13.44px。

**The 完整数值 Rule.** 不借字号、排版或省略改变金额精度、单位和业务口径；自动布局保护完整金额/合计及指定标识，用户主动手调列宽的例外按原规范执行。

## Layout

桌面以侧栏导航和业务工作区组成。侧栏与正文分别滚动；页头、范围筛选、批量操作和表区按任务组织。分组节奏沿前置间距令牌，实际控件内部另有更小间隔，不把三档节奏强加到所有内部尺寸。

常规控件基准高度为32px，网格内紧凑控件为28px；数据行基准为36px、表头为34px。多层表头、来源反馈、确认及过程矩阵有任务例外，实际行高可随内容增大。同组控件等高，窄窗口工具条自然换行；不用缩字换空间。

既有字段、列序及完整内容要求见[前端设计规范](docs/guides/frontend-design.md#阅读与操作)。新页面可提出主表与详情的组织方案，具体字段安排须逐页确认；不据此改变现有表格。

业务数据表统一使用AG Grid Community，表单和常规交互控件复用Ant Design。自动列宽使用既有原生内容拟宽/flex，编辑和保存读回期间不重新排宽；账号手调偏好沿既有存储和恢复规则。通知书、集采台账及机械费的单行显示有明确适用范围，不推广成全站禁止换行；长文本截断提示与手调列宽的适用范围见[前端设计规范](docs/guides/frontend-design.md#密集表格单行)。

行数与列密度分别判断：内容自适应短表随末行结束，合计紧跟；占剩余高度的主工作表内部滚动，表头及合计留在本表可见位置。列少的容器按内容合理收敛，列多的工作区充分使用宽度。完整金额、选择和动作的可达性优先。

现有样式在520px、740px、800px和900px处理不同构件，801—2000px另收窄桌面侧栏；这些是实现中的构件阈值，不是新设的一组全站设备规格。900px及以下的外观面板改为覆盖式。常规桌面核验基线为1920×1080、显示缩放100%、应用1.12档，相关窄窗及放大态仍需检查。

## Elevation & Depth

表格和普通容器以背景、边界和间距分层，保持平稳；弹窗、菜单和浮层按主题通过层叠、边界及必要阴影说明前后关系。普通页面和按钮去掉多余阴影，不能用装饰性悬浮效果暗示可点击。

### Shadow Vocabulary

- **轻表面:** 现有低阴影角色（`--shadow`）；并非普通容器默认都使用。
- **定位浮层:** 菜单、选择面板及时间面板（`--shadow-pop`）。
- **业务弹窗:** 较高层的对话框（`--shadow-md`），背景遮罩沿`--mask`。
- **短回执:** 独立动作的短消息（`--shadow-toast`），避开合计和滚动条。

阴影值随主题提供，具体变量表达保存在侧车扩展中；高对比主题的这些阴影角色为`none`，以遮罩、边界及层叠区分。普通容器不抬升、浮层层级清楚是当前已确认原则。

**The 平稳表面 Rule.** 普通背景、边界和间距负责分组，浮层用层叠、边界及必要阴影区分前后关系，不给每张业务卡片增加独立悬浮层。

## Shapes

形状是轻微圆角的业务控件与平直的专业网格。输入、按钮、卡片、内层分组和标签沿前置圆角令牌；不能从圆角令牌名推导胶囊外观。普通边界以0.5px轻线为基线，编辑、焦点、错误和高对比状态保清楚边界。识别控件与状态所必需的自定义线索，按[前端设计规范](docs/guides/frontend-design.md#视觉基础)检查相邻颜色的非文本对比度，不以线宽代替判断；范围限当次受影响控件。提取时个别组件实测为1px，不能据提取文档宣称全站像素一致。

## Motion

页面切换已由仅标题短反馈改为保活工作区的短距离纵向接续，方向沿导航顺序；侧栏选中背景移动，工作区标签横向接续并移动下划线。共同弹簧由[workspace-motion.tsx](apps/frontend/src/workspace-motion.tsx)持有，保持原节点和业务上下文；旧内容退出时立即停止交互，操作不等待动画。

业务弹窗保Ant Design的遮罩、关闭和焦点机制，由BusinessModal提供轻缩放与纵向进入、更快退出，条件挂载通过DialogPresence接续；原生details使用尺寸展开，不支持时即时开合。普通颜色反馈约130ms、组件状态约240ms、浮层进入320ms/退出180ms、展开280ms；曲线归[ui-theme.css](apps/frontend/src/ui-theme.css)，组件令牌归[ui-provider.tsx](apps/frontend/src/ui-provider.tsx)。这些是当前实现的提取值，侧车扩展同步展示，不新增运行时令牌。

普通筛选、排序、刷新和保存不重播整表或逐行入场，网格内控件即时更新；库存局部反馈和项目拖拽沿既有处理。减少动态效果关闭空间运动并保退出收尾，运行中切换不重建账号树、弹窗或草稿。完整交互约束与选型依据见[动效与连续操作](docs/guides/frontend-design.md#动效与连续操作)。

## Components

### Buttons

按钮紧凑而明确。主要操作采用主题实底，次要操作保表面与边界，破坏性行内操作使用危险文字/边界及柔和危险悬停底。查看、更改关联等动作保完整按钮外观，金额/编码导航保链接语义。普通与行内高度按Layout分工；悬停、聚焦、禁用及处理中不互相冒充。

### Inputs / Fields

可编辑值有明确输入外观，字段名称与当前值可识别；悬停、聚焦、修改、禁用及错误可辨。原生输入焦点沿既有主色轮廓，金额右对齐并保中文输入、原始数字草稿及输入位置。只读业务值仍须可读；失败保输入及就近原因，未知结果沿业务规则等待核对。

### Navigation

侧栏按业务名称分组，长名称允许换行，整行承担悬停和选中反馈；选中背景、文字采用对应侧栏角色。当前路由保持可识别，导航不增加装饰性链接下划线。账号菜单持有外观与字号入口，沿既有偏好保存流程。

### Chips / Tags

状态和有限类别采用小圆角、柔和底色及完整文字。状态色表达结果与待处理程度，类别色表达稳定分类；标签不能仅用相同色块让人猜含义。可编辑枚举继续保选择控件外观和当前语义。

### Cards / Containers

白色或主题对应表面承载业务组，轻边界、间距和分组底表达层次。卡片尺寸随内容与任务，不为填空白添加无关信息；表区与弹窗按任务使用宽度和可用高度。

### Business Grid

正文支持原生文字选择复制，数字右对齐，合计字重与底色稳定。鼠标点只读文字不增加冗余整格焦点框，内嵌输入保编辑焦点。虚拟滚动不改变筛选、合计或导出范围；保存读回不覆盖下一格草稿、滚动或列宽。侧车中的合计片段仅展示视觉外观，真实业务表继续使用现有AG Grid能力。

## Do's and Don'ts

### Do:

- **Do** 引用共享主题角色，让控件、表格和账号主题预览一致消费。
- **Do** 按任务安排表格密度与高度，保关键内容、完整数值和主要操作可达。
- **Do** 保清楚的输入外观及按钮外观，反馈贴近需要处理的对象。
- **Do** 在编辑和保存读回期间保草稿、输入位置、滚动和实际列宽稳定。
- **Do** 区分未知、未加载、真实零、失败、部分结果和已经完成。

### Don't:

- **Don't** 复制业务配色表、让主色换义或只靠颜色表达重要状态。
- **Don't** 为密度缩小文字、自动隐藏必要字段或在自动布局裁断金额。
- **Don't** 把指定页面的单行策略推广到全站，或擅自恢复用户已放开的手调列宽限制。
- **Don't** 为正常逐格保存增加闪动、布局跳变或持续成功提示。
- **Don't** 恢复已退役的自定义业务快捷键、跨格导航或专用键盘焦点模式。
