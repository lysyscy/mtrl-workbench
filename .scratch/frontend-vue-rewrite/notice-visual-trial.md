# 付款通知书单页视觉试验

用户2026-10-26给出10条提示词，并指定付款通知书页。用户随后明确：不改产品源码，只做独立静态demo；使用示例数据，不接业务接口或数据逻辑，8065保持原样。初次误写入产品工作树的试验改动已全部撤回，按在用8065产品输入摘要逐字节核验一致。449仅补基础事项，继续暂停。当前样板尚待用户选定，不推广为全站规范。

## Direction contract

THESIS: 让材料科在付款前快速核对对象、金额和状态。保持既有工作表构成，以清楚分组代替重复说明与装饰卡片。

OWN-WORLD: 用户指定Radix Colors，采用Slate中性面、Teal主操作，Blue/Violet类别和Green/Amber/Red状态。按1–2背景、3–5控件状态、6–8边界、9–10实心操作、11–12文字组织；原MiSans继续使用。

STORY: 先筛选单据，再勾选、核对审批/本次应付，进入既有付款确认。抓取、导出、新增和分类仅展示按钮外观，不执行实际操作。

FIRST VIEWPORT: 左侧轻导航，页头18px。选择金额摘要紧凑置顶，付款为唯一实心主操作；维护工具和筛选区以细边界分组，主表占主要空间。正文14px、辅助/表头12px，字重承担层级。

FORM: 保留成熟工作台结构，直接代码试验。用户已固定页面、规范和原业务边界；无开放构图或风格抽签，seed: none (user-pinned existing surface)。全部新边框0.5px，圆角按容器嵌套，阴影省去，默认无过渡。

FINISH: 实际观察静态样板的字号、边框、Radix角色、表格与控件对齐；保示例数据和原有8065截图分别标识。视觉验看后由用户决定保留、调整或撤回，才更新正式设计规范。本试验不替代449性能验收。

## 10条约束落实

界面自写分隔文案去中点；业务原始名称不被改写。精简重复计数/解释，保必要风险信息；用材料科熟悉的单据、勾选、付款、剔除措辞。色值只取官方Radix数据，状态含义不换。控件基线、金额对齐、嵌套圆角统一；线框0.5px，默认无动画；12/14/18三档字号；只展示操作入口外观，不接业务；减少药丸圆角、阴影和多层卡片。

## 官方来源

- https://www.radix-ui.com/colors/docs/palette-composition/understanding-the-scale
- https://www.radix-ui.com/colors/docs/overview/usage
- Palette source: https://raw.githubusercontent.com/radix-ui/colors/dbdb85470547c7d34b9001f48fddb08ded335979/src/light.ts
- 官方MIT许可随独立demo数据保留在site/radix-colors-MIT.txt；MiSans字体同时附COPYRIGHT.txt和MiSans-License.pdf。

## 当前验看入口与边界

独立静态样板：http://127.0.0.1:30959/ 。产物和服务owner：D:/dev/mtrl-workbench/.artifacts/active/notice-visual-trial/20261026/，用户验看期间保留，选定或否决后退出。本页12条数据均为虚构，按钮仅外观，未接数据或业务逻辑；产品源码无差异，8065继续efc6f51e。

已在1280×720实际验看，正文12/14/18px三档、无页面横向溢出，主表保留横向滚动，约64px行高。源码detector返回空结果；修正了Teal和状态色小字对比，实心Teal按钮配深色文字。HTTP首页200、API路径404、写方法405，CSP禁脚本及连接。未执行业务测试，不将样板验看视为449性能通过。截图与检测结果保留于reports。
