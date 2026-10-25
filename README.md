# mybootloader

一个用 NASM 汇编编写的 512 字节 BIOS Bootloader。它会在 QEMU 中启动，打印一行字符串，然后停机。项目同时提供构建脚本、静态校验、QEMU 启动冒烟测试和 GitHub Actions CI。

## 项目结构

```text
.
├── boot.asm                  # 512 字节引导扇区源码
├── Makefile                  # build / test / smoke / run / clean
├── build.ps1                 # Windows PowerShell 构建脚本
├── tests/
│   ├── check_boot.py         # 静态校验：大小、签名、字符串、停机循环
│   └── qemu_boot_test.py     # QEMU 真实启动并检查 VGA 输出
├── .github/workflows/ci.yml  # GitHub Actions 构建与启动测试
├── .gitignore
├── LICENSE                   # MIT
└── README.md
```

## 完整代码 (`boot.asm`)

```nasm
; boot.asm —— 512 字节 BIOS Bootloader
; 编译: nasm -f bin boot.asm -o boot.bin
; 运行: qemu-system-x86_64 -drive format=raw,file=boot.bin

[BITS 16]               ; 16 位实模式
[ORG 0x7C00]            ; BIOS 将引导扇区加载到 0x7C00

start:
    ; 设置段寄存器与栈
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7C00      ; 栈向下生长，从 0x7C00 开始

    ; 打印字符串
    mov si, msg         ; SI 指向字符串首地址
.print:
    lodsb               ; AL = [DS:SI], SI++
    test al, al         ; 检查是否遇到 0 结束符
    jz .halt
    mov ah, 0x0E        ; BIOS 电传输出功能
    mov bh, 0           ; 页号 0
    int 0x10            ; 调用 BIOS 视频中断
    jmp .print

.halt:
    cli                 ; 关中断
    hlt                 ; 停机
    jmp .halt           ; 防止意外唤醒

msg: db "Hello from 512-byte Bootloader!", 13, 10, 0

; 填充至 510 字节，并添加引导签名 0xAA55
times 510 - ($ - $$) db 0
dw 0xAA55
```

## 关键点说明

- **`ORG 0x7C00`**：告诉汇编器代码将被加载到 `0x7C00`，这样 `msg` 等标签的地址计算才是正确的。
- **段寄存器清零**：BIOS 跳转过来时，`DS`、`ES` 等未必为 0，必须手动设为 0，使 `[DS:SI]` 直接对应物理地址。
- **`int 0x10` 功能 `0x0E`**：BIOS 提供的电传打字输出，打印 `AL` 中的字符并自动推进光标。
- **`times 510-($-$$) db 0`**：将剩余空间填零，确保代码恰好占 510 字节。
- **`dw 0xAA55`**：最后两字节的引导签名，BIOS 只认这个标记才会启动。

## 编译与运行

### Linux / macOS

```bash
# 安装依赖（Ubuntu/Debian）
sudo apt install nasm qemu-system-x86

# 编译
make build

# 确认大小为 512 字节
ls -l boot.bin

# 在 QEMU 中运行
make run
# 等价于: qemu-system-x86_64 -drive format=raw,file=boot.bin
```

### Windows

```powershell
# 需要预先安装 NASM、Python 3；运行 QEMU 时还需要 QEMU
.\build.ps1          # 构建 + 静态校验
.\build.ps1 -Run     # 构建 + 校验 + 启动 QEMU
```

也可以在 Git Bash / MSYS2 环境中直接使用 `make build`。

QEMU 启动后，你应看到类似输出：

```text
SeaBIOS ...
Booting from Hard Disk...
Hello from 512-byte Bootloader!
```

按 `Ctrl+Alt+2` 切换到 QEMU 监视器，输入 `quit` 退出；或直接关闭窗口。

## 测试

```bash
make test    # 静态校验：512 字节、0xAA55 签名、字符串、cli/hlt 停机循环
make smoke   # 在 QEMU 中真实启动，读取 VGA 文本缓冲区验证输出
```

`make smoke` 依赖 `qemu-system-x86_64`（或 `qemu-system-i386`）；未安装时会输出 `SKIP` 并以成功状态退出，方便本地开发。

## 持续集成

推送到 `main` 或提交 Pull Request 时，GitHub Actions 会自动：

1. 安装 NASM 并执行 `make build`；
2. 运行 `make test` 静态校验，并上传 `boot.bin` 构建产物；
3. 安装 QEMU，运行 `make smoke` 验证引导扇区能真正启动并输出字符串。

## License

[MIT](LICENSE)
