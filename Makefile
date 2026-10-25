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

UEFI_EFI := uefi/BOOTX64.EFI
UEFI_PAYLOAD := tests/payload.efi

.PHONY: all build test smoke run clean clean-legacy clean-uefi \
        uefi uefi-payload uefi-test uefi-smoke uefi-dist uefi-image

# ThinkBook 2024 使用 UEFI，因此默认构建 UEFI 版本。
all: uefi

# ---------------------------------------------------------------------------
# 传统 BIOS 引导扇区（老机器 / QEMU 参考实现）
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# UEFI 引导程序（ThinkBook 2024）
# ---------------------------------------------------------------------------
uefi:
	$(MAKE) -C uefi

uefi-payload:
	$(MAKE) -C uefi payload

uefi-test: uefi
	$(PYTHON) tests/check_uefi.py $(UEFI_EFI)

uefi-smoke: uefi uefi-payload
	$(PYTHON) tests/uefi_boot_test.py $(UEFI_EFI) $(UEFI_PAYLOAD)

uefi-dist: uefi
	$(PYTHON) scripts/make_dist.py

uefi-image: uefi
	bash scripts/make-esp-image.sh

# ---------------------------------------------------------------------------
# 清理
# ---------------------------------------------------------------------------
clean: clean-legacy clean-uefi

clean-legacy:
	$(PYTHON) -c "import os; [os.remove(p) for p in ('$(BOOT_BIN)',) if os.path.exists(p)]"

clean-uefi:
	$(MAKE) -C uefi clean
	$(PYTHON) -c "import shutil; shutil.rmtree('dist', ignore_errors=True)"
