NASM ?= nasm
QEMU ?= qemu-system-x86_64

# Windows 上通常只有 python.exe；类 Unix 系统上使用 python3。
ifeq ($(OS),Windows_NT)
PYTHON ?= python
else
PYTHON ?= python3
endif

BIN := boot.bin
SRC := boot.asm

.PHONY: all build test smoke run clean

all: build test

$(BIN): $(SRC)
	$(NASM) -f bin $(SRC) -o $(BIN)
	@echo "built $(BIN)"

build: $(BIN)

test: $(BIN)
	$(PYTHON) check.py static $(BIN)

smoke: $(BIN)
	$(PYTHON) check.py smoke $(BIN)

run: $(BIN)
	$(QEMU) -drive format=raw,file=$(BIN)

clean:
	$(PYTHON) -c "import os; os.path.exists('$(BIN)') and os.remove('$(BIN)')"
