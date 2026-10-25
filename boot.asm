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
