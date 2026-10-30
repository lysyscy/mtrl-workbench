# React 真实副本预览

用于构建、启动、更新、核验和退出预览。业务定义回需求分册，界面约束回[前端设计](frontend-design.md)，自动验证回[开发与验证](development-and-verification.md)。正式 `/app` 的切换另按[部署](deployment.md)授权；开放 `/preview` 不表示上线。

## 先确定当前实例和数据用途

除用户明确要求单独查看另一预览外，同一时间仅一个最新产品代码与真实数据库副本的预览，自动 HTTP 测试和换端口也适用。当前入口、进程、schema、修订、构建、读写及数据保留归唯一运行 owner，以主检出登记指针及实际进程为准。

统一入口为 `tools/dev/frontend_preview.py`，排他与进程身份实现为同目录 runtime 模块，完整应用装配为 server 模块。主检出 `var/state/react-writable-preview/current.json` 指向当前 run 的 `reports/real_owner.json`；锁覆盖同仓各工作树和端口，持锁服务PID直接运行uvicorn。异常退出由OS释放锁，残留记录仍核实际PID、创建时间和命令，不能只凭文件存在或旧stopped_at判断。

| 用途 | 操作边界 |
|---|---|
| 新建验证副本 | 显式 `--copy-source --disposable`；来源只读一致快照，目标先匹配来源版本，核复制计数/内容/序列，再只升级目标。退出只清其自建schema。 |
| 现有用户试用副本 | `--existing`只接受已登记可写副本；需要时显式目标升级，先保恢复点并核已有表数据不丢。停止保留schema、私有状态和用户修改，禁止重拷正式库覆盖。 |
| 冻结历史性能样本 | 保既定版本、数据指纹和离线原件；无额外常驻服务，不为最新产品迁移原样本。获准测量时再按唯一实例安排符合条件的只读副本。 |

新副本账号经去凭据/停用投影，再建专用本地验看账号，配置、操作历史与运行记录按复制工具的明确边界处理；不打印或复制来源凭据到工作树.env。验证副本保持所有既有i8/物理打印外呼入口阻断，本地读写和Excel导出完整开放。已有业务试用实例保其明确授权的绑定及私有会话，读取配置不代表认证成功或新外部动作授权。

## 离线构建

依赖及最低版本读 `apps/frontend/package.json`（Node范围）与锁文件（pnpm精确版本）；复用已准备环境。仓根运行，`<run>`为本次 `.artifacts/active/<effort>/<run>`，构建目录必须是该run/work下不存在的新目录：

```text
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --run <run> --prepare-build <run>/work/<new-build>
```

入口依次执行现有typecheck/build，保存日志与version清单，核HTML入口、src/public、依赖/构建配置输入及完整资源散列。可在旧实例运行时离线构建；待用清单不会改变旧owner的实际身份。最新产品还核后端/迁移与预览工具输入，纯文档提交不触发重建。运行时theme链接保留，不能把index中的运行期链接改成相对构建资源。

## 启动、更新与切换

先离线准备。构建统一经Corepack调用package.json声明的pnpm，先核实际版本，再typecheck/build，版本身份随version.json记录；缺Corepack或版本不符即停止，不回落PATH中的其他pnpm。核旧owner后正常退出，再开放新实例；统一入口在任何副本持久写入前取得排他锁及目标端口。未知来源修订、迁移分叉、数据库身份或search_path不符均拒绝，不stamp、不回退public、不改来源结构。参数中的配置只用于明确来源和专用测试目标。

共享检出上开始累计回归或加载前，先与相关输入主人核目标修订和产品指纹，约定需要稳定的源码及窗口；实施期间可并行，验证窗口内保持这些输入稳定。无法冻结时使用隔离检出，仍遵守唯一预览和已登记真实副本约束。沿现有任务/owner沟通，不增加登记表；独立清理与归档不占共享索引窗口。

```text
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --stop
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --source-env <正式检出的.env> --run <run> --copy-source --disposable --port 8065
```

已有用户试用副本使用原run和owner，不经过自建schema的finally清理：

```text
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --source-env <正式检出的.env> --run <原试用run> --existing --port 8065
```

确需升级该副本时增加 `--upgrade-existing --pg-bin <现场匹配PG/bin>`。升级只作用登记目标，schema恢复点使用现有pg_dump/pg_restore目录校验；原表数据摘要前后核对。恢复点留在原run/recovery，风险窗口关闭后按既有生命周期处置。正式服务不在预览停止/升级范围。

## 实际核验与退出

从当前工作树现有解释器调用 `tools.dev.frontend_preview_runtime.registered_preview()`，核固定进程身份、HTTP `/visual-version`的实际schema/revision、产品输入、完整构建及实际HTML。再由入口导航检查登录、权限、受影响读取/正常保存读回或实际下载；不从健康200推完整业务正确。独立Cookie、精确search_path、导出目录及配置/i8缓存/导入状态都由原run隔离。

停止仍用统一CLI `--stop`。它按当前owner的真实进程和HTTP身份请求正常退出，不依赖可能已替换的待用version清单；停止后核端口及拥有者状态。用户试用schema和私有状态保留，可丢弃验证schema由创建者清理。需要临时写验证时先停并保留试用实例，验证后恢复原试用入口；试用修改不作为测试重置材料。

服务退出时在唯一预览锁内清除与自身owner路径及进程身份一致的current登记和停止请求，保留停止回执、用户试用数据及私有状态。替换owner（包括复用同一路径的新进程）保持；异常退出遗留或无法核实的历史登记须先核进程与用途。

## 布局采集

`tools/dev/frontend_layout.py`只附着指定run且与当前登记一致的最新可丢弃真实副本，使用其本地验看账号和新浏览器context。先按本任务授权把临时账号设为目标字号；采集器核实际字号，保留账号设置。

```text
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_layout.py --preview-run <本任务run> --width 1920 --height 1080 --scale 1.12
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_layout.py --preview-run <本任务run> --route /contracts --route /inventory
```

页面从实际侧栏导航枚举，`--route`只选择其中的入口。采集等待页面、数据与当前展开网格就绪，记录视口、字号、列、行数、页面横向溢出、单元格及其内容容器的横竖溢出和实际可见横向条；关闭的details不参与。无可验网格、零可见数据行或明确空结果、页面错误或超时分别记录且返回非零，不能当作布局通过；整数测量1px取整差与0高隐藏横向条区分。失败截图沿frontend_capture带预览身份；JSON绑定采集器散列和实际预览身份，运行前后核相同实例/产品输入。产物按workspace_paths退出，默认结束给出实际归档报告路径。此检查覆盖所选主视图，额外明细、弹窗和交互按本次变化选测。

## 性能测量

`tools/dev/frontend_measure.py`只消费已存在的只读真实副本，保留owner、读写身份、schema、版本与构建保护。当前可写业务预览不能冒充冻结性能条件；采集器集成检查也不等于重跑性能基线。

```text
backend/.venv/Scripts/python.exe -X utf8 tools/dev/frontend_measure.py check --samples <samples.jsonl> --interactions <interactions.json>
backend/.venv/Scripts/python.exe -X utf8 tools/dev/frontend_measure.py run --preview-run <只读run> --baseline-summary <summary.json> --label <新label> --stage screen
```

先小样筛查；有明确完整对照用途才用 `--stage all`。原始输入、版本、数据、浏览器/视口/字号及冷/热条件必须对应，较差样本和未验边界保留。ready为标题/networkidle/fonts/双rAF代理，不是现场INP、热SPA LCP或Lighthouse TBT；自动输入和导航传输开销分别解释，`fonts.ready`后新触发加载不伪称字体全稳定。现有纯计算、输出保护与真实页采集器检查入口见开发指南。
