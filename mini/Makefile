NASM ?= nasm
QEMU ?= qemu-system-x86_64

# Windows 上通常只有 python.exe；类 Unix 系统上使用 python3。
ifeq ($(OS),Windows_NT)
PYTHON ?= python
else
PYTHON ?= python3
endif

BOOT_BIN := boot.bin
BOOT_SRC := boot.asm
KERNEL_BIN := kernel.bin
KERNEL_SRC := kernel.asm
IMAGE := mini.img

# 第 2 步校验扇区是否读入内存；第 3 步改为校验内核被读入且跳转执行。
SMOKE_MODE ?= kernel

.PHONY: all build test smoke run clean

all: build test

$(BOOT_BIN): $(BOOT_SRC)
	$(NASM) -f bin $(BOOT_SRC) -o $(BOOT_BIN)
	@echo "built $(BOOT_BIN)"

$(KERNEL_BIN): $(KERNEL_SRC)
	$(NASM) -f bin $(KERNEL_SRC) -o $(KERNEL_BIN)
	@echo "built $(KERNEL_BIN)"

$(IMAGE): $(BOOT_BIN) $(KERNEL_BIN) make_image.py
	$(PYTHON) make_image.py $(BOOT_BIN) $(IMAGE) --payload $(KERNEL_BIN)

build: $(IMAGE)

test: $(BOOT_BIN)
	$(PYTHON) check.py static $(BOOT_BIN)

smoke: $(IMAGE)
	$(PYTHON) check.py smoke $(IMAGE) $(SMOKE_MODE)

run: $(IMAGE)
	$(QEMU) -drive format=raw,file=$(IMAGE),if=floppy

clean:
	$(PYTHON) -c "import os; [os.remove(p) for p in ('$(BOOT_BIN)', '$(KERNEL_BIN)', '$(IMAGE)') if os.path.exists(p)]"
