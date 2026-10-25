#requires -Version 5.1
<#
.SYNOPSIS
    构建并校验 512 字节 BIOS Bootloader（Windows / PowerShell 版本）。

.EXAMPLE
    .\build.ps1
    构建 + 静态校验。

.EXAMPLE
    .\build.ps1 -Run
    构建后直接在 QEMU 中启动（需要 qemu-system-x86_64 在 PATH 中）。
#>
param(
    [switch]$Run,
    [switch]$SkipTest
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

if (-not (Get-Command nasm -ErrorAction SilentlyContinue)) {
    throw '未找到 nasm，请先安装 NASM 并加入 PATH。'
}

nasm -f bin boot.asm -o boot.bin
if ($LASTEXITCODE -ne 0) {
    throw "nasm 汇编失败（退出码 $LASTEXITCODE）。"
}

$size = (Get-Item -LiteralPath boot.bin).Length
Write-Host "built boot.bin ($size bytes)"

if (-not $SkipTest) {
    $python = Get-Command python, python3 -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -notlike '*WindowsApps*' } |
        Select-Object -First 1
    if (-not $python) {
        throw '未找到可用的 Python，无法运行校验脚本。'
    }
    & $python.Source tests/check_boot.py boot.bin
    if ($LASTEXITCODE -ne 0) {
        throw '静态校验失败。'
    }
}

if ($Run) {
    if (-not (Get-Command qemu-system-x86_64 -ErrorAction SilentlyContinue)) {
        throw '未找到 qemu-system-x86_64，请先安装 QEMU 并加入 PATH。'
    }
    qemu-system-x86_64 -drive format=raw,file=boot.bin
}
