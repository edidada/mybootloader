#!/usr/bin/env python3
"""拼接 QEMU 用的原始磁盘镜像 mini.img。

BIOS 只把第 1 个扇区（boot.bin）读到 0x7C00；后面的扇区必须由引导程序
用 int 0x13 自己读。镜像填充到 1.44 MiB（2880 扇区，标准软盘容量），
以保证 BIOS 报告的 CHS 几何里第 2 扇区（C=0,H=0,S=2）是有效扇区。

用法:
  python make_image.py boot.bin mini.img                      # 第二扇区填标记
  python make_image.py boot.bin mini.img --payload kernel.bin # 第二扇区放内核
"""

from __future__ import annotations

import argparse
from pathlib import Path

SECTOR = 512
IMAGE_SECTORS = 2880
MARKER = b"MINI: sector 2 loaded from disk via int 13h\r\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("boot")
    parser.add_argument("output")
    parser.add_argument("--payload")
    args = parser.parse_args()

    boot = Path(args.boot).read_bytes()
    if len(boot) != SECTOR:
        print(f"FAIL: {args.boot} 应为 {SECTOR} 字节，实际 {len(boot)} 字节")
        return 1

    if args.payload:
        payload = Path(args.payload).read_bytes()
        if len(payload) > SECTOR:
            print(f"FAIL: {args.payload} 超过一个扇区（{SECTOR} 字节）")
            return 1
    else:
        payload = MARKER

    image = boot + payload.ljust(SECTOR, b"\x00")
    image += b"\x00" * (IMAGE_SECTORS * SECTOR - len(image))
    Path(args.output).write_bytes(image)
    source = args.payload or "marker"
    print(f"built {args.output} ({len(image)} bytes, sector 2 from {source})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
