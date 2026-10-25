#requires -Version 5.1
<#
.SYNOPSIS
    构建 ThinkBook 2024 UEFI Bootloader（Windows / PowerShell）。

.EXAMPLE
    .\scripts\build-uefi.ps1
    编译、生成 dist\EFI\BOOT\BOOTX64.EFI，并运行 PE 静态校验。
#>
param(
    [switch]$SkipTest
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

$cc = Get-Command x86_64-w64-mingw32-gcc -ErrorAction SilentlyContinue
if (-not $cc) {
    $gcc = Get-Command gcc -ErrorAction SilentlyContinue
    if ($gcc) {
        $machine = & $gcc.Source -dumpmachine 2>$null
        if ($machine -match 'mingw') {
            $cc = $gcc
        }
    }
}
if (-not $cc) {
    throw '未找到 MinGW-w64 x86_64 编译器。请安装 MSYS2 的 mingw-w64-x86_64-gcc，或把 x86_64-w64-mingw32-gcc 加入 PATH。'
}

Write-Host "使用编译器: $($cc.Source)"

$cflags = @(
    '-O2', '-ffreestanding', '-fno-builtin', '-fno-stack-protector',
    '-fshort-wchar', '-mno-red-zone', '-Wall', '-Wextra', '-Werror'
)
$ldflags = @('-nostdlib', '-Wl,--subsystem,10', '-Wl,-e,efi_main')

$source = Join-Path $Root 'uefi\bootx64.c'
$object = Join-Path $Root 'uefi\bootx64.o'
$target = Join-Path $Root 'uefi\BOOTX64.EFI'

& $cc.Source @cflags -c $source -o $object
if ($LASTEXITCODE -ne 0) {
    throw "编译失败（退出码 $LASTEXITCODE）。"
}

& $cc.Source @ldflags -o $target $object
if ($LASTEXITCODE -ne 0) {
    throw "链接失败（退出码 $LASTEXITCODE）。"
}

Write-Host "built $target ($((Get-Item $target).Length) bytes)"

$python = Get-Command python, python3 -ErrorAction SilentlyContinue |
    Where-Object { $_.Source -notlike '*WindowsApps*' } |
    Select-Object -First 1
if (-not $python) {
    throw '未找到可用的 Python，无法生成 dist 和运行校验。'
}

& $python.Source (Join-Path $Root 'scripts\make_dist.py')
if ($LASTEXITCODE -ne 0) {
    throw '生成 dist 失败。'
}

if (-not $SkipTest) {
    & $python.Source (Join-Path $Root 'tests\check_uefi.py') $target
    if ($LASTEXITCODE -ne 0) {
        throw 'PE 静态校验失败。'
    }
}

Write-Host ''
Write-Host '下一步:'
Write-Host '  1. 将 U 盘格式化为 FAT32'
Write-Host '  2. 复制 dist\EFI 到 U 盘根目录（或运行 .\scripts\copy-to-usb.ps1 -Drive E:）'
Write-Host '  3. BIOS 中关闭 Secure Boot，按 F12 选择 U 盘启动'
