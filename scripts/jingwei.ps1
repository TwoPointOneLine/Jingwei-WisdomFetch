#Requires -Version 5.1
<#
.SYNOPSIS
    精卫（Jingwei WisdomFetch）仓库级统一入口。

.DESCRIPTION
    封装各子工程的常用命令，避免"该在哪个目录执行"的困惑。
    关键约束：uv / pytest / ruff 必须在 backend/ 下执行（仓库根非 uv workspace 根）。

.EXAMPLE
    .\scripts\jingwei.ps1 dev      # 启动后端五服务
    .\scripts\jingwei.ps1 test     # 后端测试
    .\scripts\jingwei.ps1 up       # 容器编排启动（含构建）
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('help', 'dev', 'web', 'test', 'lint', 'lock', 'build', 'up', 'down', 'ps', 'health', 'logs', 'backup')]
    [string]$Command = 'help',

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot

function Invoke-Backend {
    param([string[]]$Arguments)
    Push-Location (Join-Path $RepoRoot 'backend')
    try {
        & uv @Arguments
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    finally { Pop-Location }
}

function Invoke-Deploy {
    param([string[]]$Arguments)
    Push-Location (Join-Path $RepoRoot 'backend')
    try {
        & uv run python scripts/deploy.py @Arguments
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    finally { Pop-Location }
}

switch ($Command) {
    'help' {
        @"
精卫 · 仓库级统一入口

  dev      启动后端五服务（前台常驻，Ctrl+C 停止）
  web      启动前端开发服务器（Vite 代理 /api -> 网关 8080）
  test     运行后端测试（pytest）
  lint     运行后端 lint（ruff）
  lock     校验 backend/uv.lock 与 pyproject 一致性
  build    构建前端产物（pnpm build）
  up       容器编排启动（--build 会先构建前端 + 镜像）
  down     容器编排停止
  ps       查看容器状态
  health   健康检查（轮询等待就绪）
  logs     查看服务日志，如： logs gateway
  backup   数据备份（Mongo dump + MinIO 桶同步），见 scripts/backup.ps1

用法： .\scripts\jingwei.ps1 <命令> [附加参数]
"@
    }
    'dev'    { Push-Location (Join-Path $RepoRoot 'backend'); try { & .\run.bat @Rest } finally { Pop-Location } }
    'web'    { & pnpm --dir (Join-Path $RepoRoot 'frontend') dev }
    'test'   { Invoke-Backend @('run', 'pytest') }
    'lint'   { Invoke-Backend @('run', 'ruff', 'check', 'packages', 'services') }
    'lock'   { Invoke-Backend @('lock', '--check') }
    'build'  { & pnpm --dir (Join-Path $RepoRoot 'frontend') build }
    'up'     { Invoke-Deploy (@('up') + $Rest) }
    'down'   { Invoke-Deploy (@('down') + $Rest) }
    'ps'     { Invoke-Deploy @('ps') }
    'health' { Invoke-Deploy @('health') }
    'logs'   { Invoke-Deploy (@('logs') + $Rest) }
    'backup' { & (Join-Path $PSScriptRoot 'backup.ps1') @Rest }
}
