#!/usr/bin/env python3
"""把 BOOTX64.EFI 整理成可直接复制到 U 盘的目录结构。"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "uefi" / "BOOTX64.EFI"
DIST = ROOT / "dist"


def main() -> int:
    if not SOURCE.is_file():
        print(f"FAIL: 找不到 {SOURCE}，请先运行 `make uefi`")
        return 1

    shutil.rmtree(DIST, ignore_errors=True)
    target = DIST / "EFI" / "BOOT"
    target.mkdir(parents=True)
    shutil.copy2(SOURCE, target / "BOOTX64.EFI")

    (DIST / "README.txt").write_text(
        "ThinkBook 2024 UEFI Bootloader\n"
        "==============================\n\n"
        "1. 将 U 盘格式化为 FAT32。\n"
        "2. 把本目录下的 EFI 文件夹复制到 U 盘根目录。\n"
        "3. 目标结构: U盘根目录/EFI/BOOT/BOOTX64.EFI\n"
        "4. 进入 BIOS 关闭 Secure Boot，按 F12 选择 U 盘启动。\n\n"
        "注意: 未签名的 EFI 程序在 Secure Boot 开启时会被拒绝。\n"
        "修改 Secure Boot 前请先备份 BitLocker 恢复密钥。\n",
        encoding="utf-8",
    )

    print(f"PASS: 已生成 {DIST / 'EFI' / 'BOOT' / 'BOOTX64.EFI'}")
    print("      将 dist 目录下的 EFI 文件夹复制到 FAT32 U 盘根目录即可。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
