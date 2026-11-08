; mini/boot.asm —— 第 3 步：跳转内核
;
; 第 2 步把第 2 扇区读进 0x7E00 之后就停机；这一步只多了一个变量：跳转。
; 用 far jump 把控制权交给 0x0000:0x7E00，也就是刚从磁盘读进来的
; kernel.bin。内核会在屏幕上打印 'K'，VGA 中出现 'K' 即表示
; "读盘 + 跳转"整条链路都通了。
;
; 镜像: mini.img（第 1 扇区 boot.bin，第 2 扇区 kernel.bin）
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

    ; DL 由 BIOS 传入，是本次启动的驱动器号；这段代码不动 DX，直接沿用。
    ; int 0x13 / AH=0x02：把第 2 扇区（内核）读入 ES:BX = 0000:7E00
    mov ah, 0x02        ; 功能号：读扇区
    mov al, 1           ; 读 1 个扇区
    mov ch, 0           ; 柱面 0
    mov cl, 2           ; 扇区 2（引导扇区是扇区 1）
    mov dh, 0           ; 磁头 0
    mov bx, LOAD_ADDR
    int 0x13            ; 调用 BIOS 磁盘服务；CF=1 表示失败
    jc .halt            ; 读盘失败就停机（VGA 里不会有 'K'，CI 会报 FAIL）

    ; 比第 2 步只多这一条：跳到刚从磁盘读进来的内核
    jmp 0x0000:LOAD_ADDR

.halt:
    cli                 ; 关中断
    hlt                 ; 停机，CPU 等待唤醒事件
    jmp .halt           ; 被意外唤醒后继续停在这里

; 填充至 510 字节，再写入引导扇区签名 0xAA55（小端为 55 AA）
times 510 - ($ - $$) db 0
dw 0xAA55
