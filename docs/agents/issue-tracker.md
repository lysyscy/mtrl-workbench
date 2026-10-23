# TAIL 票协议

票源是 `.scratch/tails/issues/TAIL-<编号>-<短名>.md`，一票一文件。普通改动不必建票；需要跨会话状态或已采用 effort 时复用原票。`What to build`、`Blocked by`、`Status`、验收项与必要 `Comments` 持有本票真实状态，规格持有共同范围与累计基点。

TAIL_LAST_ISSUED: 434

这是唯一发号高水位，编号已分配即不回退、不复用，允许跳号。指定整合者在任务真源工作树串行发号；分配前核相关工作树新增号。行缺失、重复、非法或小于在场票号时工具拒绝，不从历史正文猜号。

## 状态与依赖

沿用 `ready-for-agent`、`ready-for-human`、`needs-info`、`needs-triage`、`blocked`、`in-progress`、`needs-human`、`done`、`wontfix`。已有在途票按原状态与采用方式解释。`Blocked by` 只列真正前置；None 表示无前置。每个编号必须有可读原票，只有 done 满足依赖，wontfix 不自动解锁；外部触发另写验收/Comments，工具不能判断它已经满足。done 表示本票按其协议达终态，不能证明部署或当前输入均通过。

## 熟悉的三个入口

从仓根调用 `backend/.venv/Scripts/python.exe -X utf8`：

```text
tools/oneoff/_tail_open.py --what "目标" --pre "None" --acceptance "可验证的完成条件"
tools/oneoff/_tail_open.py --what "目标" --pre "TAIL-<前置号>" --acceptance "完成条件" --apply
tools/oneoff/_tail_close.py --id <号> --status done --reason "真实证据与未验边界" --apply
tools/oneoff/_list_tails.py
```

open/close 默认干跑。open 仅创建票并推进高水位；close 只更新原票状态与 Comments，done/wontfix 必须明确依据，不写历史索引、状态双表或关闭计数。验收项据实完成，工具不自动勾选。夹具可用 `--tracker`、`--tickets` 指向临时目录。

关闭后的最终证据先进入 Git。原件只有在已保存且不再被活动阻塞、验收或范围裁决实际消费时退出；最后一个消费者退出后顺手检查相关引用。历史提及编号本身不要求永久留票。恢复原件按 Git，不把缺失前置当作 done，不建第二份关闭名册。
