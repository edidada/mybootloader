/*
 * uefi_payload.c —— 仅供测试使用的链式启动目标
 *
 * 由 uefi_boot_test.py 放到 ESP 的 \EFI\Microsoft\Boot\bootmgfw.efi 位置，
 * 验证主 bootloader 的设备路径构造、LoadImage 和 StartImage 流程是否正常。
 */

#include "../uefi/uefi.h"

static EFI_SYSTEM_TABLE *g_st;

static const EFI_GUID loaded_image_guid = {
    0x5B1B31A1, 0x9562, 0x11d2,
    {0x8E, 0x3F, 0x00, 0xA0, 0xC9, 0x69, 0x72, 0x3B}};

static int loaded_image_has_file_path(EFI_HANDLE image,
                                      EFI_SYSTEM_TABLE *system_table)
{
    EFI_LOADED_IMAGE_PROTOCOL *loaded = 0;
    EFI_STATUS status = system_table->BootServices->HandleProtocol(
        image, (EFI_GUID *)&loaded_image_guid, (VOID **)&loaded);

    if (EFI_ERROR(status) || !loaded || !loaded->FilePath) {
        return 0;
    }

    UINT8 *node = (UINT8 *)loaded->FilePath;
    for (int i = 0; i < 32; i++) {
        if (node[0] == 0x7F && node[1] == 0xFF) {
            break;
        }
        if (node[0] == 0x04 && node[1] == 0x04) {
            return 1; /* MEDIA_FILEPATH_DP */
        }
        UINT16 length = *(UINT16 *)(node + 2);
        if (length < 4) {
            break;
        }
        node += length;
    }
    return 0;
}

static inline void outb(UINT16 port, UINT8 value)
{
    __asm__ __volatile__("outb %0, %1" : : "a"(value), "Nd"(port));
}

static inline UINT8 inb(UINT16 port)
{
    UINT8 value;
    __asm__ __volatile__("inb %1, %0" : "=a"(value) : "Nd"(port));
    return value;
}

static void serial_puts(const char *text)
{
    outb(0x3F8 + 1, 0x00);
    outb(0x3F8 + 3, 0x80);
    outb(0x3F8 + 0, 0x01);
    outb(0x3F8 + 1, 0x00);
    outb(0x3F8 + 3, 0x03);
    outb(0x3F8 + 2, 0xC7);
    outb(0x3F8 + 4, 0x0B);

    while (*text) {
        if (*text == '\n') {
            while ((inb(0x3F8 + 5) & 0x20) == 0) {
            }
            outb(0x3F8, '\r');
        }
        while ((inb(0x3F8 + 5) & 0x20) == 0) {
        }
        outb(0x3F8, (UINT8)*text++);
    }
}

EFI_STATUS EFIAPI efi_main(EFI_HANDLE image_handle, EFI_SYSTEM_TABLE *system_table)
{
    static CHAR16 message[] = {
        'C', 'H', 'A', 'I', 'N', 'L', 'O', 'A', 'D', '_', 'P', 'A', 'Y',
        'L', 'O', 'A', 'D', '_', 'O', 'K', '\r', '\n', 0};

    g_st = system_table;

    serial_puts("CHAINLOAD_PAYLOAD_OK\n");
    if (loaded_image_has_file_path(image_handle, system_table)) {
        serial_puts("LOADED_IMAGE_PATH_OK\n");
    } else {
        serial_puts("LOADED_IMAGE_PATH_MISSING\n");
    }
    if (g_st && g_st->ConOut) {
        g_st->ConOut->OutputString(g_st->ConOut, message);
    }
    return EFI_SUCCESS;
}
