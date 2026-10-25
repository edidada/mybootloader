#!/usr/bin/env python3
"""静态校验 UEFI 引导程序（PE32+ / EFI application）。"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

MACHINE_AMD64 = 0x8664
PE32_PLUS_MAGIC = 0x20B
EFI_APPLICATION_SUBSYSTEM = 10
BANNER = b"ThinkBook 2024 UEFI Bootloader"


def main(argv: list[str]) -> int:
    image = Path(argv[1]) if len(argv) > 1 else Path("uefi/BOOTX64.EFI")

    if not image.is_file():
        print(f"FAIL: 找不到 {image}，请先运行 `make uefi`")
        return 1

    data = image.read_bytes()
    errors: list[str] = []

    if len(data) < 0x40 or data[:2] != b"MZ":
        print("FAIL: 不是有效的 PE 文件（缺少 MZ 头）")
        return 1

    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        print("FAIL: 找不到 PE 签名")
        return 1

    coff = pe_offset + 4
    machine, section_count, _, _, _, optional_size, _ = struct.unpack_from(
        "<HHIIIHH", data, coff
    )
    optional = coff + 20

    if machine != MACHINE_AMD64:
        errors.append(f"Machine 应为 0x{MACHINE_AMD64:04x}，实际为 0x{machine:04x}")

    magic = struct.unpack_from("<H", data, optional)[0]
    if magic != PE32_PLUS_MAGIC:
        errors.append(f"Optional Header 应为 PE32+ (0x{PE32_PLUS_MAGIC:x})")

    entry_point = struct.unpack_from("<I", data, optional + 16)[0]
    if entry_point == 0:
        errors.append("AddressOfEntryPoint 为 0")

    subsystem = struct.unpack_from("<H", data, optional + 68)[0]
    if subsystem != EFI_APPLICATION_SUBSYSTEM:
        errors.append(
            f"Subsystem 应为 EFI application ({EFI_APPLICATION_SUBSYSTEM})，"
            f"实际为 {subsystem}"
        )

    section_table = optional + optional_size
    sections: list[str] = []
    for index in range(section_count):
        header = section_table + index * 40
        if header + 40 > len(data):
            errors.append("节表超出文件范围")
            break
        name = data[header : header + 8].rstrip(b"\0").decode("ascii", "replace")
        sections.append(name)

    if ".reloc" not in sections:
        errors.append("缺少 .reloc 节，UEFI 固件可能无法重定位该映像")

    if BANNER not in data:
        errors.append(f"文件中找不到标识字符串 {BANNER!r}")

    if len(data) > 2 * 1024 * 1024:
        errors.append(f"映像过大（{len(data)} 字节），可能是误链接了运行库")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    print(
        f"PASS: UEFI x86-64 PE32+ application，{len(data)} 字节，"
        f"entry=0x{entry_point:x}，节: {', '.join(sections)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
