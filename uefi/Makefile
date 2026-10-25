# 交叉编译器；可用 make CC=... 覆盖
CC := x86_64-w64-mingw32-gcc

CFLAGS ?= -O2 -ffreestanding -fno-builtin -fno-stack-protector \
          -fshort-wchar -mno-red-zone -Wall -Wextra -Werror
LDFLAGS ?= -nostdlib -Wl,--subsystem,10 -Wl,-e,efi_main

ifeq ($(OS),Windows_NT)
PYTHON ?= python
else
PYTHON ?= python3
endif

TARGET := BOOTX64.EFI
OBJECT := bootx64.o
PAYLOAD := ../tests/payload.efi
PAYLOAD_OBJECT := ../tests/uefi_payload.o

.PHONY: all payload clean

all: $(TARGET)

$(TARGET): $(OBJECT)
	$(CC) $(LDFLAGS) -o $@ $^

$(OBJECT): bootx64.c uefi.h
	$(CC) $(CFLAGS) -c -o $@ $<

payload: $(PAYLOAD)

$(PAYLOAD): ../tests/uefi_payload.c uefi.h
	$(CC) $(CFLAGS) -c -o $(PAYLOAD_OBJECT) $<
	$(CC) $(LDFLAGS) -o $@ $(PAYLOAD_OBJECT)

clean:
	$(PYTHON) -c "import os; [os.remove(p) for p in ('$(TARGET)', '$(OBJECT)', '$(PAYLOAD)', '$(PAYLOAD_OBJECT)') if os.path.exists(p)]"
