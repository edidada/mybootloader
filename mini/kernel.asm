; mini/kernel.asm —— 第 3 步的"内核"
;
; 引导扇区把磁盘第 2 扇区读入 0x7E00 后，会 far jump 到这里执行。
; 它只做一件可观察的事：用 int 0x10 打印 'K'，然后停机。
; VGA 里出现 'K'，就说明"读盘 + 跳转"整条链路都通了。
;
; 它不是引导扇区，不需要 0xAA55 签名；只是补齐到 512 字节，
; 方便 make_image.py 把它整个放进第 2 扇区。
;
; 编译: nasm -f bin kernel.asm -o kernel.bin

[BITS 16]
[ORG 0x7E00]            ; 被加载到引导扇区之后紧邻的 512 字节处

start:
    mov ah, 0x0E        ; int 0x10 / AH=0x0E：电传输出
    mov al, 'K'
    mov bh, 0           ; 显示页 0
    int 0x10

.halt:
    cli
    hlt
    jmp .halt

; 补齐到一整个扇区（内核不需要引导签名）
times 512 - ($ - $$) db 0
