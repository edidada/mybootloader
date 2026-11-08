; mini/boot.asm —— 只做一件事的 bootblock
;
; 用 BIOS 视频中断 int 0x10 在屏幕上打印一个字符 'M'，然后死循环。
; 这是最小验证步骤：只检验汇编语法、镜像构建、QEMU 启动这条链路。
; 通过之后再逐步替换成"读磁盘扇区"、"跳转内核"，每次只增加一个变量。
;
; 编译: nasm -f bin boot.asm -o boot.bin
; 运行: qemu-system-x86_64 -drive format=raw,file=boot.bin

[BITS 16]               ; BIOS 把引导扇区加载到 0x7C00，运行在 16 位实模式
[ORG 0x7C00]

start:
    ; BIOS 只保证 CS=0，DS/ES/SS 的值不确定，先统一清零
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7C00      ; 栈从引导扇区下方往下生长

    ; 打印一个字符：int 0x10 / AH=0x0E（电传输出 Teletype Output）
    mov ah, 0x0E        ; 功能号：在当前光标位置写字符并推进光标
    mov al, 'M'         ; 要打印的那一个字符
    mov bh, 0           ; 显示页 0
    int 0x10            ; 调用 BIOS 视频服务

.halt:
    cli                 ; 关中断
    hlt                 ; 停机，CPU 等待唤醒事件
    jmp .halt           ; 被意外唤醒后继续停在这里，绝不向下执行

; 填充到 510 字节，再写入引导扇区签名 0xAA55（小端为 55 AA）
times 510 - ($ - $$) db 0
dw 0xAA55
