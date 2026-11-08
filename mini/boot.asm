; mini/boot.asm —— 第 2 步：读磁盘扇区
;
; 把第 1 步的"打印字符"换成"用 BIOS int 0x13 / AH=0x02 读第 2 个扇区"。
; 相比第 1 步只增加了一个变量：磁盘读取。
; 扇区被读到 0x7E00（引导扇区 0x7C00 + 512），随后停机。
; 验证方式也随之改变：用 QEMU monitor 读取 0x7E00 处的内存，确认第二扇区
; 的内容确实被读进来了，不再依赖屏幕输出。
;
; 镜像: mini.img（make_image.py 把 boot.bin 与第二扇区拼成软盘镜像）
; 编译: make build
; 运行: make run

[BITS 16]               ; BIOS 把引导扇区加载到 0x7C00，运行在 16 位实模式
[ORG 0x7C00]

LOAD_ADDR equ 0x7E00    ; 引导扇区之后紧邻的 512 字节

start:
    ; BIOS 只保证 CS=0，DS/ES/SS 的值不确定，先统一清零
    xor ax, ax
    mov ds, ax
    mov es, ax          ; ES:BX 是读扇区的目标缓冲区
    mov ss, ax
    mov sp, 0x7C00      ; 栈从引导扇区下方往下生长

    ; DL 由 BIOS 传入，是本次启动的驱动器号。这段代码不动 DX，直接沿用。
    ; int 0x13 / AH=0x02：按 CHS 把扇区读入 ES:BX；CF=1 表示失败
    mov ah, 0x02        ; 功能号：读扇区
    mov al, 1           ; 读 1 个扇区
    mov ch, 0           ; 柱面 0
    mov cl, 2           ; 扇区 2（引导扇区是扇区 1）
    mov dh, 0           ; 磁头 0
    mov bx, LOAD_ADDR   ; ES:BX = 0000:7E00
    int 0x13            ; 调用 BIOS 磁盘服务

.halt:
    cli                 ; 关中断
    hlt                 ; 停机，CPU 等待唤醒事件
    jmp .halt           ; 被意外唤醒后继续停在这里

; 填充至 510 字节，再写入引导扇区签名 0xAA55（小端为 55 AA）
times 510 - ($ - $$) db 0
dw 0xAA55
