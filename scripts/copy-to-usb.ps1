#requires -Version 5.1
<#
.SYNOPSIS
    把 dist\EFI 复制到已经格式化为 FAT32 的 U 盘（不会格式化！）。

.EXAMPLE
    .\scripts\copy-to-usb.ps1 -Drive E:
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$Drive,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

if ($Drive -notmatch '^([A-Za-z]):?\\?$') {
    throw "无法识别的盘符: $Drive（示例: E:）"
}
$letter = $Matches[1].ToUpper()
$volume = Get-Volume -DriveLetter $letter -ErrorAction SilentlyContinue
if (-not $volume) {
    throw "找不到 $letter`: 盘。"
}
if ($volume.FileSystem -ne 'FAT32') {
    throw "$letter`: 盘的文件系统是 $($volume.FileSystem)，UEFI 启动需要 FAT32。"
}

$source = Join-Path $Root 'dist\EFI'
if (-not (Test-Path -LiteralPath $source)) {
    throw '找不到 dist\EFI，请先运行 .\scripts\build-uefi.ps1'
}

$destination = "$letter`:\"
if (-not $Force) {
    Write-Host "即将把 EFI 文件夹复制到 $destination"
    Write-Host '不会格式化 U 盘，但同名文件会被覆盖。'
    $answer = Read-Host '继续? [y/N]'
    if ($answer -notmatch '^[yY]') {
        Write-Host '已取消。'
        return
    }
}

Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
Write-Host "PASS: 已复制到 $($destination)EFI\BOOT\BOOTX64.EFI"
Write-Host ''
Write-Host 'ThinkBook 启动步骤:'
Write-Host '  1. 重启，按 F2 进入 BIOS，Security -> Secure Boot -> Disabled'
Write-Host '  2. 保存退出，按 F12 选择 U 盘启动'
Write-Host '提示: 修改 Secure Boot 前请备份 BitLocker 恢复密钥。'
