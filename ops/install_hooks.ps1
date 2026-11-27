<#
.SYNOPSIS
  为普通克隆及其工作树安装共享的 pre-commit 入口。
.NOTES
  在仓库内运行一次。规则由主检出的 ops/hooks/pre-commit 维护。
  工作树沿用自己的暂存区和审计脚本。安装器不修改 Git 配置。
#>
$ErrorActionPreference = 'Stop'

$common = & git rev-parse --path-format=absolute --git-common-dir
if ($LASTEXITCODE -ne 0 -or -not $common) { throw '无法定位仓库的公共 Git 目录' }
$rule = Join-Path (Split-Path -Parent $common) 'ops/hooks/pre-commit'
if (-not (Test-Path -LiteralPath $rule -PathType Leaf)) { throw "找不到主检出的钩子规则：$rule" }

$target = Join-Path $common 'hooks/pre-commit'
$entry = @'
#!/bin/sh
common=$(git rev-parse --path-format=absolute --git-common-dir) || exit 1
exec sh "$common/../ops/hooks/pre-commit" "$@"
'@
[IO.File]::WriteAllText($target, ($entry.Replace("`r`n", "`n") + "`n"), [Text.UTF8Encoding]::new($false))
Write-Host "提交钩子已安装到 $target"
