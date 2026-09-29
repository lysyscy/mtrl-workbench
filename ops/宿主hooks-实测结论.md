# 宿主 hooks 能力 · 实测结论（含**负结果**）

> **性质**：宿主能力实测（`CodeBuddy` / 本机 IDE 会话）—— 答"能不能用 hooks 做**自动到点提醒**"
> **方法**：查官方 `plugin-dev/skills/hook-development/SKILL.md` ＋ 数市场在用的插件 ＋ **本机三挂载点各配一遍、重启并走完整一轮**看是否触发
> **脚本**：`~/.codebuddy/hooks/handoff_stop_hook.py`（**宿主层 · 不在本仓**；逻辑已自证，留作 CLI 路线备用）
> **日期 / 本机**：2026-09-25 · `W11-20250421859`（同一台）
> **何时必复做**：① 换 IDE / 换宿主 ② 宿主升版 ③ 真出现"**我漏了交接评估**"的事件（那是本负结果的重议条件）
> **关联**：`TAIL-95`（已收口）· `work/40-decisions/D27-交接提醒维持每轮自检.md`（用户裁定 `B`）

## 一、能力：**支持吗** ⇒ ✅ 支持（文档层面）

| 项 | 结论 | 依据 |
|---|---|---|
| 支持吗 | ✅ **支持** | CodeBuddy 官方市场自带 `plugin-dev/skills/hook-development/SKILL.md`，**逐字列出**事件：`PreToolUse` · `PostToolUse` · `Stop` · `SubagentStop` · `SessionStart` · `SessionEnd` · `UserPromptSubmit` · `PreCompact` · `Notification`；市场里多个插件**真在用**（`security-scan`→`Stop` · `security-guidance`→`PreToolUse` · `plugin-finder`→`UserPromptSubmit` · `weixin-minigame-helper`→`SessionStart`） |
| 配置位（**用户级**） | **`.codebuddy/settings.json`** —— **direct 格式**（顶层直接写 `"Stop": [ … ]`） | 同上 · 该 skill 的 `## Settings Format (Direct)` |
| 配置位（插件级） | `hooks/hooks.json` —— **wrapper 格式**（`{"hooks": { … }}`），路径用 `${CODEBUDDY_PLUGIN_ROOT}` | 同上 · `## Plugin hooks.json Format`；⚠️ 插件 hooks 与用户 hooks **并行合并**执行 |
| hook 类型 | `"type": "command"`（跑外部命令）· `"type": "prompt"`（交模型判）＋ `matcher` ＋ `timeout` | 同上 |
| 收到的字段 | 公共：`session_id` · `transcript_path` · `cwd` · `hook_event_name`；`Stop/SubagentStop` 另有 `stop_hook_active` · `reason`；`UserPromptSubmit` 有 `user_prompt`；`Pre/PostToolUse` 有 `tool_name`/`tool_input`/`tool_result` | 同上 ＋ `security-scan` 的 README／脚本 |
| ⚠️ **未确认** | **`turn_id` 不在文档字段里** ⇒ 计数要按 **`session_id` ＋ `Stop` 次数**降级（或先实测一次拿到真实 payload） | 文档未列出该字段 |

⇒ **对 `project-handoff` 的意义**：它需要的三个事件（`SessionStart` / `UserPromptSubmit` / `Stop`）**全都有**，
且 `Stop` 带 `stop_hook_active`（防循环）⇒ **技术上可以适配**。
⚠️ 但落地要**改用户级配置**（`.codebuddy/settings.json`）＋ 可能触发宿主原生信任确认 ⇒ **必须先经用户同意**，⛔ 不许擅自写。

## 二、落地状态（`TAIL-95` 第一步 · 2026-09-25）

| 项 | 值 |
|---|---|
| 挂在哪 | 用户级 **`~/.codebuddy/settings.json`** 的 `Stop`（direct 格式 · `matcher:"*"` · `timeout:15`）｜改前备份 = 同目录 `settings.json.bak-20260925` |
| 脚本 | **`~/.codebuddy/hooks/handoff_stop_hook.py`**（宿主层 · 不在本仓 ⇒ 本仓文档架构规则不受影响） |
| 干什么 | ① **只认本项目**（`cwd` 含 `mtrl-workbench`，其余项目静默退出）② `stop_hook_active=true` ⇒ 静默（防循环）③ 其余 ⇒ 往 `~/.codebuddy/state/handoff-stop-hook.log` **写一行心跳**（含**真实字段名**）④ ⛔ **绝不往 stdout 写**、⛔ 异常全吞、**一律 `exit 0`** |
| 自证（四用例 · 都 rc=0 ＋ stdout 空） | 本项目 ⇒ 心跳 ✓ ｜异项目 ⇒ 静默不写 ✓ ｜`stop_hook_active=true` ⇒ 静默 ✓ ｜**畸形输入** ⇒ 吞掉 ✓ |
| ⭐ 实测到的真实 payload 字段 | `cwd` · `hook_event_name` · `session_id` · `stop_hook_active` · `transcript_path` —— **没有 `turn_id`** ⇒ 计数只能按 **`session_id`** |
| ⛔ **未实现（别当已完成）** | 「**压缩到期却漏了评估**」的判定 —— 技能计数器需要一次压缩计数输入，而宿主 `PreCompact` 没有"自增"入口、payload 也无 `turn_id` ⇒ 当前 hook 只做**管道自证 ＋ 心跳**；要真做到点提醒，下一步得先解决"压缩次数怎么落账" |

## 三、⛔ 负结果（2026-09-25 收口 · `TAIL-95`）：**本宿主的 IDE 会话不跑 hooks**

实测条件：**三个挂载点同时配置** ＋ 用户**重启整个 VS Code 进程** ＋ 走完**一个完整回合**：

| 挂载点 | 依据 | 结果 |
|---|---|---|
| 用户级 `~/.codebuddy/settings.json` 的 `Stop`（direct 格式） | 官方 `hook-development` 的 Settings Format | ⛔ **0 次触发** |
| 用户级 `~/.codebuddy/hooks.json` 的 `Stop` | 技能附页口径「合并到用户 `hooks.json`」 | ⛔ **0 次触发** |
| **项目级** `.codebuddy/settings.json` 的 `Stop` | direct 格式 | ⛔ **0 次触发** |

· hook 脚本**逻辑本身已验证**（四用例：写心跳 ✓ · 异项目静默 ✓ · 防循环静默 ✓ · 畸形输入吞掉 ✓，都 `rc=0` 且 stdout 为空）；
· 宿主日志 `~/.codebuddy/logs/` 里只有 `cli-memwatch-*.log` —— **没有** hook 加载/报错记录；
· 「插件形式」**未试**：本机 `plugins/known_marketplaces.json` **只有两个内置 zip 市场**（`isBuiltIn:true`），
  没有本地目录市场的样例 ⇒ 猜 schema 违反纪律（⛔ 不猜）。

⇒ **判定**：官方文档列的事件名/配置位是 **CodeBuddy Code（CLI）** 的能力；**本 IDE 会话不加载 hooks**。

**收口动作**：宿主配置**已还原**（`settings.json` ← `.bak-20260925`）· 两个新增文件**已删** ·
脚本 `~/.codebuddy/hooks/handoff_stop_hook.py` **留作 CLI 路线备用**（未接线、零影响）。

⚠️ **口径**：IDE 会话里**没有程序兜底** ⇒ 交接评估**只能靠每轮自检**（`project-handoff` 技能允许并要求的口径）。

**用户裁定（2026-09-25）**：按 **`B`** —— 维持「每轮自检 ＋ 交接材料 ＋ 记忆」，⛔ **不装 CLI**、⛔ 不再动宿主配置（重议条件 = 真出现"我漏了评估"的事件）。决定件 = `work/40-decisions/D27-交接提醒维持每轮自检.md`。

---

> ⭐ **为什么这份从 `ops/README.md` 里搬出来**（2026-09-28 文档审计）：它原先内联在索引里（约 49 行），
> 而 `ops/README.md` **自己的维护纪律**写的是「新增实测结论 ⇒ ① 文件自身写清（性质/方法/脚本/日期/本机）② 在本表加一行」
> ⇒ **内容混进索引**（职责混杂）：将来要复核 hooks 结论时，不知道"该改哪儿"。
