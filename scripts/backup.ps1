#Requires -Version 5.1
<#
.SYNOPSIS
    精卫（Jingwei WisdomFetch）生产数据备份脚本（阶段5 · 9.6 可观测性与备份）。

.DESCRIPTION
    备份以下数据源到 var/backup/<timestamp>/：
      - MongoDB：mongodump（需 mongodump 在 PATH）
      - MinIO ：mc mirror（需 mc 在 PATH）
      - Milvus：仅打印快照建议（向量库快照依赖底层存储，需运维侧手动/定时任务执行）

    凭据从仓库根 .env 读取（MONGO_URL / MINIO_*）。若工具缺失则跳过并告警，不中断其他项。

.EXAMPLE
    .\scripts\backup.ps1            # 全量备份
    .\scripts\backup.ps1 -WhatIf    # 仅打印将要执行的操作
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$EnvFile = (Join-Path $PSScriptRoot '..' '.env'),
    [string]$OutRoot = (Join-Path $PSScriptRoot '..' 'var' 'backup')
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$OutDir = Join-Path $OutRoot $Stamp
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# ---- 读取 .env（轻量解析，仅取需要的键） ----
function Get-EnvValue {
    param([string]$Key)
    if (-not (Test-Path $EnvFile)) { return $null }
    $line = (Get-Content $EnvFile | Where-Object { $_ -match "^$Key=" } | Select-Object -First 1)
    if ($line) { return ($line -split '=', 2)[1].Trim().Trim('"').Trim("'") }
    return $null
}

$mongoUrl   = Get-EnvValue 'MONGO_URL'
$minioEp    = Get-EnvValue 'MINIO_ENDPOINT'
$minioAk    = Get-EnvValue 'MINIO_ACCESS_KEY'
$minioSk    = Get-EnvValue 'MINIO_SECRET_KEY'
$minioBucket= Get-EnvValue 'MINIO_BUCKET'

Write-Host "[backup] 输出目录: $OutDir"

# ---- MongoDB ----
if (-not $mongoUrl) {
    Write-Warning "[backup] 未找到 MONGO_URL，跳过 Mongo 备份。"
} elseif (-not (Get-Command mongodump -ErrorAction SilentlyContinue)) {
    Write-Warning "[backup] 未检测到 mongodump，跳过 Mongo 备份（请安装 MongoDB Database Tools）。"
} else {
    $mongoOut = Join-Path $OutDir 'mongo'
    if ($PSCmdlet.ShouldProcess($mongoOut, 'mongodump')) {
        Write-Host "[backup] Mongo dump -> $mongoOut"
        & mongodump --uri $mongoUrl --out $mongoOut 2>&1 | ForEach-Object { Write-Host "  $_" }
    }
}

# ---- MinIO ----
if (-not $minioEp -or -not $minioBucket) {
    Write-Warning "[backup] 未找到 MINIO_ENDPOINT / MINIO_BUCKET，跳过 MinIO 备份。"
} elseif (-not (Get-Command mc -ErrorAction SilentlyContinue)) {
    Write-Warning "[backup] 未检测到 mc (MinIO Client)，跳过 MinIO 备份。"
} else {
    $alias = "jingwei-backup"
    $miniOut = Join-Path $OutDir 'minio' $minioBucket
    if ($PSCmdlet.ShouldProcess($miniOut, 'mc mirror')) {
        Write-Host "[backup] MinIO mirror -> $miniOut"
        & mc alias set $alias "http://$minioEp" $minioAk $minioSk 2>&1 | Out-Null
        & mc mirror "$alias/$minioBucket" $miniOut 2>&1 | ForEach-Object { Write-Host "  $_" }
    }
}

# ---- Milvus ----
Write-Host "[backup] Milvus：向量库快照需在运维侧执行（如对象存储/磁盘快照或 milvus backup 工具）。"
Write-Host "[backup] 建议：对 etcd + 对象存储（MinIO 中 milvus bucket）做一致性快照，或采用官方 milvus-backup。"

Write-Host "[backup] 完成。备份位于: $OutDir"
