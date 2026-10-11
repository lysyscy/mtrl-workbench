<#
  已 clone 仓库的首次空库安装；用法与依赖见 ops/deployment.md。
  只用于尚无应用角色及两库的目标；不用于已有系统升级或数据恢复。
  -DryRun 仅检查文件/配置并打印计划，不执行子进程或写入。
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = '',
    [string] $PgBin = 'C:\Program Files\PostgreSQL\16\bin',
    [switch] $DryRun
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($RepoRoot)) { $RepoRoot = Split-Path -Parent $PSScriptRoot }
function Say($m) { Write-Host $m }
function Step($m) { Write-Host ''; Write-Host ('── ' + $m) }
function Run($exe, [string[]] $argv, $cwd) {
    Say ('   > ' + $exe + ' ' + ($argv -join ' '))
    if ($DryRun) { return }
    $prevPy = $env:PYTHONIOENCODING
    $prevPg = $env:PGCLIENTENCODING
    Push-Location $cwd
    try {
        $env:PYTHONIOENCODING = 'utf-8'
        $env:PGCLIENTENCODING = 'UTF8'
        & $exe @argv | Out-Host
        $code = $LASTEXITCODE
        if ($code -ne 0) { throw ('执行失败：' + $exe + '，退出码 ' + $code + '；已停止后续步骤。') }
    } finally {
        Pop-Location
        if ($null -eq $prevPy) { Remove-Item Env:\PYTHONIOENCODING -ErrorAction SilentlyContinue } else { $env:PYTHONIOENCODING = $prevPy }
        if ($null -eq $prevPg) { Remove-Item Env:\PGCLIENTENCODING -ErrorAction SilentlyContinue } else { $env:PGCLIENTENCODING = $prevPg }
    }
}

Say '=== 首次空库安装 ==='
if (-not (Test-Path -LiteralPath $RepoRoot -PathType Container)) { throw '仓库目录不存在；请先 clone。' }
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
foreach ($rel in @('.git', 'ops\init_db.sql', 'ops\pip.ini', 'ops\nssm_install.ps1', 'ops\selfcheck.ps1', 'backend\requirements.txt', 'backend\alembic.ini', '.env')) {
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $rel))) { throw ('缺少 ' + $rel + '；请先补齐，未执行安装。') }
}
# 配置只读且不回显；两条 URL 必须指向本 SQL 的同机两库，避免建库和迁移落到不同目标。
$config = @{}
foreach ($line in Get-Content -LiteralPath (Join-Path $RepoRoot '.env') -Encoding UTF8) {
    if ($line -match '^\s*(DATABASE_URL|TEST_DATABASE_URL)\s*=\s*(.*?)\s*$') {
        $config[$matches[1]] = $matches[2].Trim().Trim('"').Trim("'")
    }
}
$sql = Get-Content -LiteralPath (Join-Path $RepoRoot 'ops\init_db.sql') -Raw -Encoding UTF8
$dbNames = @([regex]::Matches($sql, '(?im)^CREATE DATABASE\s+(\w+)') | ForEach-Object { $_.Groups[1].Value })
$roles = @([regex]::Matches($sql, '(?im)^CREATE ROLE\s+(\w+)') | ForEach-Object { $_.Groups[1].Value })
if ($dbNames.Count -ne 2 -or $roles.Count -ne 1) { throw '初始化 SQL 的角色/两库定义已变化，请先核对部署流程。' }
$urls = @()
$keys = @('DATABASE_URL', 'TEST_DATABASE_URL')
for ($i = 0; $i -lt $keys.Count; $i++) {
    $key = $keys[$i]
    $value = $config[$key]
    $uri = $null
    if (-not $value -or $value -match '[<>]' -or -not [Uri]::TryCreate($value, [UriKind]::Absolute, [ref]$uri)) { throw ($key + ' 缺失或仍为模板占位；请填写 .env。') }
    if ($uri.Scheme -notin @('postgresql', 'postgresql+psycopg') -or $uri.Host -notin @('127.0.0.1', 'localhost', '[::1]') -or $uri.Query -or $uri.Fragment -or
        $uri.AbsolutePath.Trim('/') -ne $dbNames[$i] -or $uri.UserInfo -notmatch '^([^:]+):(.+)$' -or $matches[1] -ne $roles[0]) {
        throw ($key + ' 须配置 init_db.sql 定义的同机角色和数据库（含口令、不带查询参数）；未执行安装。')
    }
    $urls += $uri
}
if ($urls[0].Host -ne $urls[1].Host -or $urls[0].Port -ne $urls[1].Port) { throw '两库必须使用同一 PostgreSQL 地址和端口。' }
$pgPort = if ($urls[0].Port -lt 0) { '5432' } else { [string]$urls[0].Port }
$psql = Join-Path $PgBin 'psql.exe'
$pgArgs = @('-X', '-h', $urls[0].Host, '-p', $pgPort, '-U', 'postgres', '-d', 'postgres', '-v', 'ON_ERROR_STOP=1')
Step '1) 确认应用角色和两库尚不存在'
# 首次安装误用于已有库会留下半套状态；首次路线取消时可一并移除此检查。
$dbList = ($dbNames | ForEach-Object { "'$_'" }) -join ','
$roleList = ($roles | ForEach-Object { "'$_'" }) -join ','
$emptyCheck = 'DO $$ BEGIN IF EXISTS (SELECT FROM pg_database WHERE datname IN (' + $dbList + ')) OR EXISTS (SELECT FROM pg_roles WHERE rolname IN (' + $roleList + ')) THEN RAISE EXCEPTION ''Application database or role already exists; first installation only''; END IF; END; $$;'
Run $psql ($pgArgs + @('-c', $emptyCheck)) $RepoRoot

Step '2) venv 与依赖'
$venv = Join-Path $RepoRoot 'backend\.venv'
$python = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { Run 'python' @('-m', 'venv', $venv) $RepoRoot }
$pipSrc = Join-Path $RepoRoot 'ops\pip.ini'
$pipDst = Join-Path $venv 'pip.ini'
if (-not (Test-Path -LiteralPath $pipDst)) {
    if ($DryRun) { Say '   [干跑] 复制 ops/pip.ini 到 venv' }
    else { Copy-Item -LiteralPath $pipSrc -Destination $pipDst }
} elseif ([Convert]::ToBase64String([IO.File]::ReadAllBytes($pipSrc)) -ne [Convert]::ToBase64String([IO.File]::ReadAllBytes($pipDst))) {
    Say '   注意：venv/pip.ini 与 ops/pip.ini 不同，保留现有文件；请核对镜像配置。'
}
$req = Join-Path $RepoRoot 'backend\requirements.txt'
Run $python @('-m', 'pip', 'install', '-r', $req) (Join-Path $RepoRoot 'backend')

Step '3) 一次性建角色、两库与迁移'
Run $psql ($pgArgs + @('-f', (Join-Path $RepoRoot 'ops\init_db.sql'))) $RepoRoot
Run $python @('-m', 'alembic', 'upgrade', 'head') (Join-Path $RepoRoot 'backend')

Step '4) 注册服务与安装自检'
$install = Join-Path $RepoRoot 'ops\nssm_install.ps1'
Run 'powershell' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $install, '-RepoRoot', $RepoRoot) $RepoRoot
if (-not $DryRun) { Start-Sleep -Seconds 5 }
$check = Join-Path $RepoRoot 'ops\selfcheck.ps1'
Run 'powershell' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $check, '-RepoRoot', $RepoRoot) $RepoRoot
if ($DryRun) { Say '=== 干跑结束：未执行命令或写入；数据库空库前提与实际安装尚未验证。 ===' }
else { Say '=== 安装命令与自检已完成；自检 Skip 项仍未验证，请核对明细。 ===' }
Say '真实备份恢复仍未证明；完成标准与诊断入口见 ops/deployment.md。'
