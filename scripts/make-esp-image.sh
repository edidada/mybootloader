#!/usr/bin/env bash
# 生成可直接 dd 到 U 盘的 GPT + FAT32 ESP 镜像（Linux / WSL）。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for tool in sgdisk mkfs.vfat mmd mcopy; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "缺少 $tool，请安装: sudo apt install gdisk dosfstools mtools" >&2
        exit 1
    fi
done

make uefi

mkdir -p dist
IMAGE="dist/thinkbook-esp.img"

echo "创建 64 MiB GPT + ESP 镜像: $IMAGE"
rm -f "$IMAGE"
dd if=/dev/zero of="$IMAGE" bs=1M count=64 status=none

# 单分区、从 1 MiB 开始、类型 EF00 (EFI System)
sgdisk --clear \
    --new=1:2048:0 \
    --typecode=1:ef00 \
    --change-name=1:THINKBOOT \
    "$IMAGE" >/dev/null

# 在第 2048 扇区（1 MiB）处创建 FAT32
mkfs.vfat -F 32 --offset 2048 -n THINKBOOT "$IMAGE" >/dev/null

export MTOOLS_SKIP_CHECK=1
mmd -i "${IMAGE}@@1M" ::/EFI ::/EFI/BOOT
mcopy -i "${IMAGE}@@1M" uefi/BOOTX64.EFI ::/EFI/BOOT/BOOTX64.EFI

echo
echo "PASS: $IMAGE"
echo "写入 U 盘（危险操作，请确认设备名！）:"
echo "  sudo dd if=$IMAGE of=/dev/sdX bs=4M status=progress conv=fsync"
echo
echo "Windows 下可用 Rufus 以 DD 模式写入该镜像。"
