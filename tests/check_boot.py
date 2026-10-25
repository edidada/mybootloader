#!/usr/bin/env python3
"""对生成的引导扇区做静态校验。

检查项:
  * 文件恰好 512 字节（BIOS 引导扇区大小）
  * 偏移 510 处为引导签名 0x55 0xAA
  * 包含要打印的字符串（含 CRLF 与 NUL 结尾）
  * 包含 cli / hlt / jmp $ 的停机循环
"""

from __future__ import annotations

import sys
from pathlib import Path

EXPECTED_SIZE = 512
SIGNATURE_OFFSET = 510
EXPECTED_SIGNATURE = b"\x55\xaa"
EXPECTED_MESSAGE = b"Hello from 512-byte Bootloader!\r\n\x00"
HALT_LOOP = b"\xfa\xf4\xeb\xfc"  # cli; hlt; jmp short -4（跳回 cli）


def main(argv: list[str]) -> int:
    image = Path(argv[1]) if len(argv) > 1 else Path("boot.bin")

    if not image.is_file():
        print(f"FAIL: 找不到 {image}，请先运行 `make build`")
        return 1

    data = image.read_bytes()
    errors: list[str] = []

    if len(data) != EXPECTED_SIZE:
        errors.append(f"大小应为 {EXPECTED_SIZE} 字节，实际为 {len(data)} 字节")
    else:
        if data[SIGNATURE_OFFSET:] != EXPECTED_SIGNATURE:
            got = data[SIGNATURE_OFFSET:].hex(" ")
            errors.append(f"引导签名应为 55 aa，实际为 {got!r}")

    if EXPECTED_MESSAGE not in data:
        errors.append("未找到预期的提示字符串")

    if HALT_LOOP not in data:
        errors.append("未找到 cli/hlt/jmp 停机循环")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    print(
        "PASS: 512 字节引导扇区，签名 0xAA55 正确，"
        "提示字符串与停机循环均存在"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
