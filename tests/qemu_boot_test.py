#!/usr/bin/env python3
"""在 QEMU 中真实启动 boot.bin，并从 VGA 文本缓冲区验证输出。

原理:
  引导程序通过 BIOS `int 0x10, ah=0x0E` 把字符写到 VGA 文本模式缓冲区
  （物理地址 0xB8000，每个字符占 2 字节：ASCII + 属性）。脚本以无界面
  模式启动 QEMU，等系统启动后用 monitor 的 `xp` 命令读取该内存，再在
  奇数字节中查找预期字符串。

依赖: qemu-system-x86_64（未安装时返回 0 并提示 SKIP，方便本地执行）。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

MESSAGE = "Hello from 512-byte Bootloader!"
VGA_BASE = 0xB8000
VGA_CELLS = 80 * 25
BOOT_TIMEOUT_SECONDS = 5
MONITOR_TIMEOUT_SECONDS = 20


def find_qemu() -> str | None:
    for candidate in ("qemu-system-x86_64", "qemu-system-i386"):
        if shutil.which(candidate):
            return candidate
    return None


def read_vga_bytes(qemu: str, image: Path) -> bytes:
    command = [
        qemu,
        "-drive", f"format=raw,file={image}",
        "-display", "none",
        "-monitor", "stdio",
        "-no-reboot",
    ]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )

    try:
        time.sleep(BOOT_TIMEOUT_SECONDS)
        output, _ = process.communicate(
            f"xp /{VGA_CELLS * 2}b {VGA_BASE:#x}\nquit\n",
            timeout=MONITOR_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        process.kill()
        output, _ = process.communicate()
        raise RuntimeError("QEMU monitor 响应超时") from None

    # monitor 每行形如:
    # 00000000000b8000: 0x42 0x07 0x6f 0x07 ...
    values = re.findall(r"0x([0-9a-fA-F]{2})\b", output)
    if len(values) < VGA_CELLS * 2:
        tail = "\n".join(output.strip().splitlines()[-20:])
        raise RuntimeError(
            f"未能从 QEMU monitor 读取完整 VGA 缓冲区，仅得到 {len(values)} 字节。"
            f"\n--- monitor 输出末尾 ---\n{tail}"
        )

    return bytes(int(value, 16) for value in values[: VGA_CELLS * 2])


def main(argv: list[str]) -> int:
    image = Path(argv[1]) if len(argv) > 1 else Path("boot.bin")
    if not image.is_file():
        print(f"FAIL: 找不到 {image}，请先构建引导扇区")
        return 1

    qemu = os.environ.get("QEMU") or find_qemu()
    if not qemu:
        print("SKIP: 未找到 qemu-system-x86_64，跳过启动测试")
        return 0

    vga = read_vga_bytes(qemu, image)
    text = vga[0::2].decode("ascii", errors="replace")
    if MESSAGE not in text:
        print(f"FAIL: VGA 缓冲区中没有找到预期字符串 {MESSAGE!r}")
        print(f"VGA 文本内容: {text!r}")
        return 1

    print(f"PASS: QEMU 启动成功，VGA 输出包含 {MESSAGE!r}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except RuntimeError as error:
        print(f"FAIL: {error}")
        raise SystemExit(1) from error
