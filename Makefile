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

.PHONY: all build test smoke run clean

all: build

build: $(BOOT_BIN)

$(BOOT_BIN): $(BOOT_SRC)
	$(NASM) -f bin $(BOOT_SRC) -o $(BOOT_BIN)
	@echo "built $(BOOT_BIN)"

test: $(BOOT_BIN)
	$(PYTHON) tests/check_boot.py $(BOOT_BIN)

smoke: $(BOOT_BIN)
	$(PYTHON) tests/qemu_boot_test.py $(BOOT_BIN)

run: $(BOOT_BIN)
	$(QEMU) -drive format=raw,file=$(BOOT_BIN)

clean:
	$(PYTHON) -c "import os; [os.remove(p) for p in ('$(BOOT_BIN)',) if os.path.exists(p)]"
