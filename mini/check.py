#!/usr/bin/env python3
"""mini 引导块校验。

用法:
  python check.py static boot.bin            静态检查引导扇区
  python check.py smoke  mini.img sector    验证第 2 扇区被读入 0x7E00
  python check.py smoke  mini.img kernel    验证跳转内核后 VGA 打印 'K'

静态检查项:
  * 恰好 512 字节，偏移 510 处为 55 AA 引导签名
  * 含 int 0x13 (CD 13)：第 2 步起用 BIOS 磁盘服务读扇区
  * 含 cli/hlt/jmp 停机死循环 (FA F4 EB FC)

烟测原理: 以 -display none -monitor stdio 启动 QEMU，用 monitor 的 xp
命令轮询读取指定物理内存，判断预期内容是否出现。
  * sector: 读 0x7E00 的 512 字节，与镜像第 2 扇区比对
  * kernel: 读 0xB8000 的 VGA 文本缓冲区，查找内核打印的 'K'
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

SECTOR = 512
LOAD_ADDR = 0x7E00
VGA_BASE = 0xB8000
VGA_BYTES = 80 * 25 * 2
KERNEL_CHAR = "K"
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

    if len(data) != SECTOR:
        errors.append(f"大小应为 {SECTOR} 字节，实际为 {len(data)} 字节")
    elif data[510:] != b"\x55\xaa":
        errors.append(f"引导签名应为 55 aa，实际为 {data[510:].hex(' ')!r}")

    if b"\xcd\x13" not in data:
        errors.append("未找到 int 0x13（CD 13）")
    if b"\xfa\xf4\xeb\xfc" not in data:
        errors.append("未找到 cli/hlt/jmp 停机死循环（FA F4 EB FC）")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(
        "PASS: 512 字节引导扇区，签名 0xAA55，"
        "int 0x13 / 停机死循环均存在"
    )
    return 0


def dump_region(
    qemu: str, image: Path, addr: int, count: int, accept
) -> tuple[bool, bytes, str]:
    """启动 QEMU，轮询 xp 读取物理内存，返回（是否命中，最后一份内存，原始输出）。"""
    process = subprocess.Popen(
        [
            qemu,
            "-drive", f"format=raw,file={image},if=floppy",
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

    found = False
    latest = b""
    try:
        time.sleep(2)
        deadline = time.monotonic() + BOOT_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            process.stdin.write(f"xp /{count}b {addr:#x}\n")
            process.stdin.flush()
            time.sleep(1)

            values = [int(m, 16) for m in BYTE_PATTERN.findall("".join(chunks))]
            if len(values) < count:
                continue
            latest = bytes(values[-count:])
            if accept(latest):
                found = True
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

    return found, latest, "".join(chunks)


def do_smoke(image: Path, mode: str) -> int:
    qemu = find_qemu()
    if not qemu:
        if os.environ.get("REQUIRE_QEMU"):
            print("FAIL: 未找到 qemu-system-x86_64（REQUIRE_QEMU 已设置）")
            return 1
        print("SKIP: 未找到 QEMU，跳过启动测试")
        return 0

    raw_image = image.read_bytes()
    if len(raw_image) < 2 * SECTOR:
        print(f"FAIL: {image} 不足两个扇区")
        return 1

    if mode == "sector":
        expected = raw_image[SECTOR : 2 * SECTOR]
        addr, count = LOAD_ADDR, SECTOR

        def accept(region: bytes) -> bool:
            return region[:64] == expected[:64]

        ok_message = (
            f"PASS: QEMU 启动成功，int 0x13 已把第 2 扇区读入 "
            f"0x{LOAD_ADDR:X}（前 64 字节与镜像一致）"
        )
        fail_message = f"FAIL: 0x{LOAD_ADDR:X} 处没有读到第 2 扇区的内容"
    elif mode == "kernel":
        addr, count = VGA_BASE, VGA_BYTES

        def accept(region: bytes) -> bool:
            return KERNEL_CHAR in region[0::2].decode("ascii", errors="replace")

        ok_message = (
            f"PASS: QEMU 启动成功，VGA 输出包含 {KERNEL_CHAR!r}"
            "（引导扇区读盘并跳转到内核成功）"
        )
        fail_message = f"FAIL: VGA 缓冲区中没有找到内核字符 {KERNEL_CHAR!r}"
    else:
        print(f"FAIL: 未知烟测模式 {mode!r}（可选 sector / kernel）")
        return 2

    found, latest, raw = dump_region(qemu, image, addr, count, accept)
    if found:
        print(ok_message)
        return 0

    print(fail_message)
    print("--- monitor 输出末尾 ---\n" + "\n".join(raw.strip().splitlines()[-20:]))
    print(f"读取到的前 64 字节: {latest[:64].hex(' ')}")
    return 1


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] not in ("static", "smoke"):
        print("用法: check.py {static boot.bin|smoke mini.img sector|kernel}")
        return 2
    image = Path(argv[2])
    if not image.is_file():
        print(f"FAIL: 找不到 {image}，请先运行 `make build`")
        return 1
    if argv[1] == "static":
        return do_static(image)
    return do_smoke(image, argv[3] if len(argv) > 3 else "sector")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
