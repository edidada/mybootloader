#!/usr/bin/env python3
"""mini bootblock 校验。

用法:
  python check.py static boot.bin   静态检查镜像结构
  python check.py smoke  boot.bin   QEMU 启动并从 VGA 缓冲区确认打印了 'M'

静态检查项:
  * 恰好 512 字节，偏移 510 处为 55 AA 引导签名
  * 含 mov al,'M' (B0 4D) 与 int 0x10 (CD 10)
  * 含 cli/hlt/jmp 停机死循环 (FA F4 EB FC)

烟测原理: 以 -display none -monitor stdio 启动 QEMU，用 monitor 的 xp
命令轮询读取 VGA 文本缓冲区（0xB8000），在字符位中查找 'M'。
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

CHAR = "M"
VGA_BASE = 0xB8000
VGA_BYTES = 80 * 25 * 2
BOOT_TIMEOUT_SECONDS = 20
MONITOR_TIMEOUT_SECONDS = 20
BYTE_PATTERN = re.compile(r"0x([0-9a-fA-F]{2})\b")


def find_qemu() -> str | None:
    env = os.environ.get("QEMU")
    if env:
        return env
    for candidate in ("qemu-system-x86_64", "qemu-system-i386"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def do_static(image: Path) -> int:
    data = image.read_bytes()
    errors: list[str] = []

    if len(data) != 512:
        errors.append(f"大小应为 512 字节，实际为 {len(data)} 字节")
    elif data[510:] != b"\x55\xaa":
        errors.append(f"引导签名应为 55 aa，实际为 {data[510:].hex(' ')!r}")

    if b"\xb0\x4d" not in data:
        errors.append("未找到 mov al,'M'（B0 4D）")
    if b"\xcd\x10" not in data:
        errors.append("未找到 int 0x10（CD 10）")
    if b"\xfa\xf4\xeb\xfc" not in data:
        errors.append("未找到 cli/hlt/jmp 停机死循环（FA F4 EB FC）")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(
        "PASS: 512 字节引导扇区，签名 0xAA55，"
        "打印字符 'M' / int 0x10 / 停机死循环均存在"
    )
    return 0


def dump_vga(qemu: str, image: Path) -> tuple[bytes, str]:
    """启动 QEMU 并轮询读取 VGA 缓冲区，返回（缓冲区字节，monitor 原始输出）。"""
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

    threading.Thread(target=reader, daemon=True).start()

    latest = b""
    try:
        time.sleep(2)
        deadline = time.monotonic() + BOOT_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            process.stdin.write(f"xp /{VGA_BYTES}b {VGA_BASE:#x}\n")
            process.stdin.flush()
            time.sleep(1)

            values = [int(m, 16) for m in BYTE_PATTERN.findall("".join(chunks))]
            if len(values) < VGA_BYTES:
                continue
            latest = bytes(values[-VGA_BYTES:])
            if CHAR in latest[0::2].decode("ascii", errors="replace"):
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

    return latest, "".join(chunks)


def do_smoke(image: Path) -> int:
    qemu = find_qemu()
    if not qemu:
        if os.environ.get("REQUIRE_QEMU"):
            print("FAIL: 未找到 qemu-system-x86_64（REQUIRE_QEMU 已设置）")
            return 1
        print("SKIP: 未找到 QEMU，跳过启动测试")
        return 0

    vga, raw = dump_vga(qemu, image)
    if not vga:
        print("FAIL: 未能从 QEMU monitor 读取 VGA 缓冲区")
        print("--- monitor 输出末尾 ---\n" + "\n".join(raw.strip().splitlines()[-20:]))
        return 1

    text = vga[0::2].decode("ascii", errors="replace")
    if CHAR in text:
        print(f"PASS: QEMU 启动成功，VGA 文本缓冲区中出现字符 {CHAR!r}")
        return 0

    print(f"FAIL: VGA 缓冲区中没有找到字符 {CHAR!r}")
    print("--- monitor 输出末尾 ---\n" + "\n".join(raw.strip().splitlines()[-20:]))
    print(f"VGA 文本内容: {text[:80]!r}")
    return 1


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] not in ("static", "smoke"):
        print("用法: check.py {static|smoke} boot.bin")
        return 2
    image = Path(argv[2])
    if not image.is_file():
        print(f"FAIL: 找不到 {image}，请先运行 `make build`")
        return 1
    return do_static(image) if argv[1] == "static" else do_smoke(image)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
