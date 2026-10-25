# mybootloader — ThinkBook 2024 UEFI Bootloader

[![CI](https://github.com/edidada/mybootloader/actions/workflows/ci.yml/badge.svg?branch=thinkbook)](https://github.com/edidada/mybootloader/actions/workflows/ci.yml)

这个分支提供 **ThinkBook 2024 笔记本可用的 UEFI x86-64 Bootloader**，并保留原来的 512 字节 BIOS 引导扇区作为参考实现。

> ThinkBook 2024 这一类新笔记本通常只支持 UEFI（UEFI Class 3，没有 CSM/Legacy BIOS），
> 因此 `boot.asm` 生成的 512 字节 MBR 引导扇区无法在真机上启动。真机需要使用 EFI 应用程序：
> 一个 PE32+ 格式的 `BOOTX64.EFI`，放在 FAT32 分区的 `\EFI\BOOT\` 目录下。

## 功能

- 启动时显示 UEFI 菜单，10 秒无操作默认启动 Windows
- 扫描所有 FAT 分区（包括内置 NVMe 的 Windows ESP），链式启动
  `\EFI\Microsoft\Boot\bootmgfw.efi`
- 启动 UEFI Shell（`\EFI\TOOLS\Shell.efi` 等路径）
- 重启、关机、重启进入固件设置（Firmware Setup）
- 同时把日志镜像到 COM1（115200 8N1），便于无屏幕调试
- 不依赖 EDK2 / gnu-efi / libc，只有一个约 14 KB 的 `.efi` 文件

## 项目结构

```text
.
├── uefi/
│   ├── bootx64.c             # UEFI Bootloader 源码
│   ├── uefi.h                # 极简 UEFI 类型与协议定义
│   └── Makefile              # MinGW-w64 交叉编译
├── tests/
│   ├── check_uefi.py         # PE32+ / EFI application 静态校验
│   ├── uefi_boot_test.py     # QEMU + OVMF 真实启动 + 链式加载测试
│   ├── uefi_payload.c        # 测试用链式加载目标
│   └── check_boot.py         # 传统 BIOS 引导扇区校验
├── scripts/
│   ├── build-uefi.ps1        # Windows 构建 + 校验 + 生成 dist
│   ├── copy-to-usb.ps1       # 安全复制到 FAT32 U 盘（不格式化）
│   ├── make_dist.py          # 生成 dist/EFI/BOOT/BOOTX64.EFI
│   └── make-esp-image.sh     # 生成可 dd 的 GPT+ESP 镜像
├── boot.asm                  # 传统 512 字节 BIOS Bootloader（参考）
├── Makefile
└── .github/workflows/ci.yml  # 构建、PE 校验、QEMU/OVMF 启动测试
```

## 构建

### Windows

需要 MinGW-w64（`x86_64-w64-mingw32-gcc`）和 Python 3：

```powershell
.\scripts\build-uefi.ps1
```

脚本会：

1. 编译 `uefi/bootx64.c`；
2. 链接为 PE32+ EFI application；
3. 生成 `dist\EFI\BOOT\BOOTX64.EFI`；
4. 运行静态校验。

如果编译器不在 PATH 中，请安装 MSYS2 的 `mingw-w64-x86_64-gcc`，或把
`x86_64-w64-mingw32-gcc.exe` 所在目录加入 PATH。

### Linux / WSL

```bash
sudo apt install gcc-mingw-w64-x86-64 make python3

make uefi-test      # 编译 + PE 静态校验
make uefi-dist      # 生成 dist/EFI/BOOT/BOOTX64.EFI
make uefi-image     # 生成 dist/thinkbook-esp.img（需要 gdisk/dosfstools/mtools）
```

也可以手动编译：

```bash
x86_64-w64-mingw32-gcc -O2 -ffreestanding -fno-builtin \
  -fno-stack-protector -fshort-wchar -mno-red-zone \
  -Wall -Wextra -Werror -c uefi/bootx64.c -o uefi/bootx64.o

x86_64-w64-mingw32-gcc -nostdlib \
  -Wl,--subsystem,10 -Wl,-e,efi_main \
  -o uefi/BOOTX64.EFI uefi/bootx64.o
```

链接参数 `--subsystem,10` 表示 **EFI application**，这是能被 UEFI 固件直接执行的关键。

## 制作启动 U 盘

### 方法 A：复制文件（推荐）

1. 把 U 盘格式化为 **FAT32**（MBR/GPT 均可）。
2. 把构建生成的 `dist\EFI` 整个文件夹复制到 U 盘根目录。
3. 确认路径为：

```text
U盘根目录\
└── EFI\
    └── BOOT\
        └── BOOTX64.EFI
```

Windows 上也可以在构建后运行（不会格式化 U 盘）：

```powershell
.\scripts\copy-to-usb.ps1 -Drive E:
```

### 方法 B：写入原始镜像

```bash
make uefi-image
# 会生成 dist/thinkbook-esp.img（64 MiB GPT + FAT32 ESP）

# Linux/WSL，确认设备名后再执行！
sudo dd if=dist/thinkbook-esp.img of=/dev/sdX bs=4M status=progress conv=fsync
```

Windows 下可以用 Rufus 选择该镜像，并以 **DD 模式** 写入。

## ThinkBook 2024 BIOS 设置

1. **先备份 BitLocker 恢复密钥**（如果开启了 BitLocker）：
   ```powershell
   manage-bde -status
   manage-bde -protectors -get C:
   ```
   修改 Secure Boot 可能触发恢复界面。
2. 开机时按 **F2** 进入 BIOS（部分机型需要 **Fn+F2**，或关机后按 Novo 小孔）。
3. 进入 **Security → Secure Boot**，设置为 **Disabled**。
   - 如果该选项是灰色的，先把 **Secure Boot Mode** 改为 **Custom**，或先设置 BIOS 管理员密码。
4. 保存并退出（F10）。
5. 插入 U 盘，开机按 **F12** 选择启动项：
   - `USB HDD`
   - `USB Storage`
   - `EFI USB Device`
   - 或带 U 盘品牌的条目
6. 看到 `ThinkBook 2024 UEFI Bootloader (x86-64)` 即成功。

说明：

- 本程序**没有签名**。Secure Boot 开启时固件会拒绝执行，必须关闭 Secure Boot。
- 部分 ThinkBook 需要在 BIOS 里启用 **USB Boot**，或关闭 **Fast Boot** 后 U 盘才会出现在 F12 菜单。
- ThinkBook 2024 的 Intel/AMD 版本都是 x86-64 UEFI，均可使用；ARM（骁龙）版本不适用。
- 如果必须保持 Secure Boot 开启，需要用自己的密钥签名并注册到固件的 db/KEK 中，本项目不包含该流程。

修改 Secure Boot 前，建议先暂停 BitLocker：

```powershell
manage-bde -protectors -disable C: -rebootcount 2
```

启动回 Windows 后 BitLocker 会自动恢复保护。

## 菜单说明

```text
[1] Boot Windows Boot Manager (default)
[2] Boot UEFI Shell
[3] Reboot
[4] Shut down
[5] Firmware setup
[0] Exit to firmware boot manager
```

- **1**：扫描所有带 FAT 文件系统的分区，找到第一个
  `\EFI\Microsoft\Boot\bootmgfw.efi` 后用 `LoadImage` + `StartImage` 启动。
  因此即使从 U 盘启动，也能引导内置硬盘上的 Windows。
- **2**：尝试 `\EFI\TOOLS\Shell.efi`、`\EFI\Shell\Shell.efi`、`\shellx64.efi`。
- **3/4**：调用 `RuntimeServices->ResetSystem` 重启或关机。
- **5**：设置 `OsIndications = BOOT_TO_FW_UI` 后重启进入固件设置。
- **0**：返回固件启动管理器。
- 10 秒无按键时默认执行 **1**。

所有输出同时写到 UEFI 控制台和 COM1（115200 8N1）。ThinkBook 没有物理串口，但可用
USB 转串口设备或 QEMU 调试。

## 测试

### 静态校验

```bash
make uefi-test
```

检查 MZ/PE 头、AMD64、PE32+、Subsystem=10（EFI application）、入口点、`.reloc` 节、
标识字符串和文件大小。

### OVMF 真实启动测试

```bash
# Ubuntu/WSL
sudo apt install qemu-system-x86 ovmf
make uefi-smoke
```

`uefi-smoke` 会：

1. 编译测试载荷 `tests/payload.efi`；
2. 建立临时 ESP，把主程序放到 `EFI/BOOT/BOOTX64.EFI`，
   载荷放到 `EFI/Microsoft/Boot/bootmgfw.efi`；
3. 用 QEMU + OVMF 启动；
4. 从串口等待 `ThinkBook 2024 UEFI Bootloader` 和 `CHAINLOAD_PAYLOAD_OK`，
   从而验证设备路径构造、`LoadImage`、`StartImage` 全流程。

CI 中会设置 `REQUIRE_QEMU=1`，缺少 QEMU/OVMF 时直接失败而不是跳过。

每次 push 后，可以在 GitHub Actions 的运行页面下载两个产物：

- `bootx64-efi`：单独的 `BOOTX64.EFI`
- `thinkbook-usb-image`：已经包含 `EFI/BOOT/BOOTX64.EFI` 的 64 MiB GPT+ESP 镜像

> OVMF 测试通过只能说明标准 UEFI 路径正确，不能替代真机测试。
> 真机首次测试前请准备好 Windows 安装 U 盘或恢复密钥。

### 传统 BIOS 版本

```bash
make build test smoke
```

生成 512 字节 `boot.bin`，用于 QEMU 或带 Legacy/CSM 的老机器。该版本无法在
ThinkBook 2024 这类纯 UEFI 机器上启动。

## 常见问题

| 现象 | 排查方向 |
|---|---|
| F12 菜单里没有 U 盘 | 确认 FAT32、`EFI/BOOT/BOOTX64.EFI` 路径正确；换 USB 2.0 端口；关闭 Fast Boot；确认 USB Boot 已启用 |
| `Secure Boot Violation` / 直接跳过 U 盘 | Secure Boot 未关闭或未保存；先备份 BitLocker 密钥再关闭；选项灰色时把 Secure Boot Mode 改为 Custom |
| 出现菜单但提示 Windows 找不到 | 内置硬盘 ESP 中没有 `\EFI\Microsoft\Boot\bootmgfw.efi`；确认 Windows 是 UEFI 安装；BitLocker 加密不影响文件存在性 |
| 启动后黑屏/立刻返回固件 | U 盘文件不完整；重新复制；确认是 x86-64 ThinkBook，不是 ARM 型号 |
| 键盘无响应 | 尝试另一个 USB 端口；部分扩展坞/USB Hub 在固件阶段不可用 |
| 进入 BitLocker 恢复界面 | 输入恢复密钥；进入 Windows 后运行 `manage-bde -protectors -enable C:` |
| 想恢复默认启动 | 拔掉 U 盘重启，或把 BIOS 启动顺序改回 `Windows Boot Manager` |

## 实现要点

- `uefi.h` 手写所需结构体，布局遵循 UEFI 规范；`EFI_FILE_PROTOCOL` 的第一个字段是
  `Revision`，之后才是函数表。
- 入口 `efi_main(EFI_HANDLE, EFI_SYSTEM_TABLE *)` 使用 Microsoft x64 调用约定，
  编译时不需要任何 UEFI SDK。
- `LoadImage` 使用 “卷的 DevicePath + FilePath 节点” 构造完整设备路径，
  这样 `LoadedImage->DevicePath` 是正确的，Windows Boot Manager 才能据此找到 BCD。
- 启动镜像前先构造设备路径并让固件读取文件，失败时只影响当前分区，继续扫描下一个。
- 所有代码在 `-ffreestanding -nostdlib` 下编译，自行提供 `memset`/`memcpy`。

## License

[MIT](LICENSE)
