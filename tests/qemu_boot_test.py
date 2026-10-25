#!/usr/bin/env python3
"""在 QEMU 中真实启动 boot.bin，并从 VGA 文本缓冲区验证输出。

原理:
  引导程序通过 BIOS `int 0x10, ah=0x0E` 把字符写到 VGA 文本模式缓冲区
  （物理地址 0xB8000，每个字符占 2 字节：ASCII + 属性）。脚本以无界面
  模式启动 QEMU，等系统启动后用 monitor 的 `xp` 命令读取该内存，再在
  字符位（偶数字节或奇数字节）中查找预期字符串。

依赖: qemu-system-x86_64（未安装时返回 0 并提示 SKIP，方便本地执行）。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

MESSAGE = "Hello from 512-byte Bootloader!"
VGA_BASE = 0xB8000
VGA_BYTES = 80 * 25 * 2
BOOT_TIMEOUT_SECONDS = 20
MONITOR_TIMEOUT_SECONDS = 20
BYTE_PATTERN = re.compile(r"0x([0-9a-fA-F]{2})\b")


def find_qemu() -> str | None:
    for candidate in ("qemu-system-x86_64", "qemu-system-i386"):
        if shutil.which(candidate):
            return candidate
    return None


def dump_vga(qemu: str, image: Path) -> tuple[bytes, str]:
    """启动 QEMU，轮询读取 VGA 缓冲区，返回（字节内容，monitor 原始输出）。"""
    process = subprocess.Popen(
        [
            qemu,
            "-drive", f"format=raw,file={image}",
            "-display", "none",
            "-monitor", "stdio",
            "-no-reboot",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        bufsize=1,
    )
    assert process.stdin is not None and process.stdout is not None

    chunks: list[str] = []

    def reader() -> None:
        for line in process.stdout:
            chunks.append(line)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()

    latest = b""
    try:
        time.sleep(2)
        deadline = time.monotonic() + BOOT_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            process.stdin.write(f"xp /{VGA_BYTES}b {VGA_BASE:#x}\n")
            process.stdin.flush()
            time.sleep(1)

            # 每次读取都会追加一段 dump，取最后一份完整缓冲区。
            values = [
                int(match, 16) for match in BYTE_PATTERN.findall("".join(chunks))
            ]
            if len(values) < VGA_BYTES:
                continue

            latest = bytes(values[-VGA_BYTES:])
            even = latest[0::2].decode("ascii", errors="replace")
            odd = latest[1::2].decode("ascii", errors="replace")
            if MESSAGE in even or MESSAGE in odd:
                break
    finally:
        try:
            process.stdin.write("quit\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        try:
            process.wait(timeout=MONITOR_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    raw = "".join(chunks)
    if os.environ.get("QEMU_DEBUG"):
        print("--- monitor 输出（前 2000 字符）---")
        print(raw[:2000])
        print("--- 解析出的最后 64 字节 ---")
        print(" ".join(f"{value:02x}" for value in latest[:64]))

    return latest, raw


def main(argv: list[str]) -> int:
    image = Path(argv[1]) if len(argv) > 1 else Path("boot.bin")
    if not image.is_file():
        print(f"FAIL: 找不到 {image}，请先构建引导扇区")
        return 1

    qemu = os.environ.get("QEMU") or find_qemu()
    if not qemu:
        print("SKIP: 未找到 qemu-system-x86_64，跳过启动测试")
        return 0

    vga, raw = dump_vga(qemu, image)
    if not vga:
        tail = "\n".join(raw.strip().splitlines()[-20:])
        print("FAIL: 未能从 QEMU monitor 读取 VGA 缓冲区")
        print(f"--- monitor 输出末尾 ---\n{tail}")
        return 1

    for offset, label in ((0, "偶数字节"), (1, "奇数字节")):
        text = vga[offset::2].decode("ascii", errors="replace")
        if MESSAGE in text:
            print(f"PASS: QEMU 启动成功，VGA 输出包含 {MESSAGE!r}（{label}）")
            return 0

    text = vga[0::2].decode("ascii", errors="replace")
    print(f"FAIL: VGA 缓冲区中没有找到预期字符串 {MESSAGE!r}")
    print(f"VGA 文本内容: {text!r}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
