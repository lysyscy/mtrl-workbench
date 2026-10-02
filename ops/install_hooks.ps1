<#
.SYNOPSIS
  把 `ops/hooks/` 里的 git 钩子装进 `.git/hooks/`（**幂等** · 可反复跑）。

.NOTES
  ⚠️ **为什么需要这个脚本**：`.git/hooks/` **不被 git 跟踪** ⇒ 钩子本体必须先进仓（`ops/hooks/`），
     再由本脚本显式安装一次。⛔ 别用 `git config core.hooksPath` —— 那会改你的 git 配置（本仓规矩：不动 git config）。

  装什么：`ops/hooks/pre-commit` ⇒ 提交前跑**便宜子集**（syntax_audit / doc_audit / audit_meta /
  audit_work / mut_cover --check，秒级）。⚠️ 全套（pytest / 真机 / 盖章 / 产包干跑）仍在收工入口
  `tools/oneoff/_run_rulers.py --all`。

  卸载：删掉 `.git/hooks/pre-commit` 即可。
  跳过一次：`git commit --no-verify`（⛔ 不推荐）。

  用法（在仓库根）：
    powershell -NoProfile -ExecutionPolicy Bypass -File ops\install_hooks.ps1
#>
$ErrorActionPreference = 'Stop'

$root = (& git rev-parse --show-toplevel).Trim()
if (-not $root) { throw '不在 git 仓库里（git rev-parse 没回路径）' }

$src = Join-Path $root 'ops\hooks\pre-commit'
if (-not (Test-Path $src)) { throw "找不到钩子本体：$src" }

$dstDir = Join-Path $root '.git\hooks'
if (-not (Test-Path $dstDir)) { throw "找不到 .git/hooks 目录：$dstDir（这不是个普通 git 仓库？）" }
$dst = Join-Path $dstDir 'pre-commit'

Copy-Item -LiteralPath $src -Destination $dst -Force
Write-Host "✅ 已装：$dst"
Write-Host "   （来源 = ops\hooks\pre-commit · 幂等 ⇒ 改了源文件重跑本脚本即可）"
Write-Host "   卸载 = 删掉那个文件 · 跳过一次 = git commit --no-verify（⛔ 不推荐）"

# ⚠️ **这里不做"试跑"** —— `git commit --dry-run` **不会**触发 `pre-commit`
#    （假自证比没有自证更坏：它会让人以为"钩子验过了"）。要验就跑真的那五把尺子：
Write-Host ''
Write-Host '想先看它红不红 ⇒ 在仓库根手动跑这五把（钩子跑的就是它们）：'
Write-Host '  backend\.venv\Scripts\python.exe -X utf8 tools\audit\syntax_audit.py'
Write-Host '  backend\.venv\Scripts\python.exe -X utf8 tools\audit\doc_audit.py'
Write-Host '  backend\.venv\Scripts\python.exe -X utf8 tools\audit\audit_meta.py'
Write-Host '  backend\.venv\Scripts\python.exe -X utf8 tools\audit\audit_work.py'
Write-Host '  backend\.venv\Scripts\python.exe -X utf8 tools\audit\mut_cover.py --check'
Write-Host '真正的验证 = 下一次 `git commit`（它由 git 用 sh 调起）。'
