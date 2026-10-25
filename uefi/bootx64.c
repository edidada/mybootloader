/*
 * bootx64.c —— ThinkBook 2024 可用的 UEFI x86-64 Bootloader
 *
 * 功能:
 *   - 在 UEFI 控制台显示启动菜单（同时镜像到 COM1，便于调试）
 *   - 从任意 FAT 分区扫描并链式启动 Windows Boot Manager
 *   - 启动 UEFI Shell（如果存在）
 *   - 重启、关机、进入固件设置
 *
 * 编译: 见 uefi/Makefile（MinGW-w64 x86_64 交叉编译）
 * 部署: 将 BOOTX64.EFI 放到 U 盘 FAT32 分区的 \EFI\BOOT\BOOTX64.EFI
 */

#include "uefi.h"

const EFI_GUID g_efi_simple_file_system_guid = {
    0x964E5B22, 0x6459, 0x11d2,
    {0x8E, 0x39, 0x00, 0xA0, 0xC9, 0x69, 0x72, 0x3B}};

const EFI_GUID g_efi_global_variable_guid = {
    0x8BE4DF61, 0x93CA, 0x11d2,
    {0xAA, 0x0D, 0x00, 0xE0, 0x98, 0x03, 0x2B, 0x8C}};

const EFI_GUID g_efi_device_path_guid = {
    0x09576E91, 0x6D3F, 0x11d2,
    {0x8E, 0x39, 0x00, 0xA0, 0xC9, 0x69, 0x72, 0x3B}};

static EFI_SYSTEM_TABLE *g_st;
static EFI_BOOT_SERVICES *g_bs;
static EFI_RUNTIME_SERVICES *g_rt;
static EFI_HANDLE g_image;

/* ------------------------------------------------------------------------- */
/* 编译器辅助函数（-ffreestanding 下仍可能被调用）                             */
/* ------------------------------------------------------------------------- */

void *memset(void *dst, int value, UINTN size)
{
    UINT8 *p = (UINT8 *)dst;
    while (size--) {
        *p++ = (UINT8)value;
    }
    return dst;
}

void *memcpy(void *dst, const void *src, UINTN size)
{
    UINT8 *d = (UINT8 *)dst;
    const UINT8 *s = (const UINT8 *)src;
    while (size--) {
        *d++ = *s++;
    }
    return dst;
}

/* ------------------------------------------------------------------------- */
/* COM1 串口输出（无串口的笔记本上写入会被忽略，不影响启动）                    */
/* ------------------------------------------------------------------------- */

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

static int g_serial_ready;

static void serial_init(void)
{
    outb(0x3F8 + 1, 0x00); /* 关闭串口中断 */
    outb(0x3F8 + 3, 0x80); /* 打开 DLAB */
    outb(0x3F8 + 0, 0x01); /* 115200 baud */
    outb(0x3F8 + 1, 0x00);
    outb(0x3F8 + 3, 0x03); /* 8N1 */
    outb(0x3F8 + 2, 0xC7); /* 启用 FIFO */

    /* 环回测试：没有 COM1 的笔记本上读取值不会等于写入值 */
    outb(0x3F8 + 4, 0x1E);
    outb(0x3F8 + 0, 0xAE);
    g_serial_ready = (inb(0x3F8 + 0) == 0xAE);
    outb(0x3F8 + 4, 0x0B); /* DTR/RTS，恢复正常模式 */
}

static void serial_putc(char c)
{
    if (!g_serial_ready) {
        return;
    }
    for (UINT32 i = 0; i < 100000; i++) {
        if (inb(0x3F8 + 5) & 0x20) {
            outb(0x3F8, (UINT8)c);
            return;
        }
    }
}

static void serial_write(const char *text)
{
    while (*text) {
        if (*text == '\n') {
            serial_putc('\r');
        }
        serial_putc(*text++);
    }
}

/* ------------------------------------------------------------------------- */
/* UEFI 控制台输出                                                           */
/* ------------------------------------------------------------------------- */

static void console_write(const char *text)
{
    CHAR16 buffer[128];

    if (!g_st || !g_st->ConOut) {
        return;
    }

    while (*text) {
        UINTN used = 0;
        while (*text && used < sizeof(buffer) / sizeof(buffer[0]) - 1) {
            if (*text == '\n') {
                buffer[used++] = '\r';
                if (used < sizeof(buffer) / sizeof(buffer[0]) - 1) {
                    buffer[used++] = '\n';
                }
                text++;
            } else {
                buffer[used++] = (CHAR16)(UINT8)*text++;
            }
        }
        buffer[used] = 0;
        g_st->ConOut->OutputString(g_st->ConOut, buffer);
    }
}

static void print(const char *text)
{
    console_write(text);
    serial_write(text);
}

static void print_hex(UINT64 value)
{
    static const char digits[] = "0123456789abcdef";
    char buffer[19];

    buffer[0] = '0';
    buffer[1] = 'x';
    for (int i = 0; i < 16; i++) {
        buffer[2 + i] = digits[(value >> ((15 - i) * 4)) & 0xF];
    }
    buffer[18] = 0;
    print(buffer);
}

static void print_status(EFI_STATUS status)
{
    print("status ");
    print_hex(status);
}

static void ascii_to_wide(const char *src, CHAR16 *dst, UINTN capacity)
{
    UINTN i = 0;
    for (; src[i] != 0 && i + 1 < capacity; i++) {
        dst[i] = (CHAR16)(UINT8)src[i];
    }
    dst[i] = 0;
}

static void print_firmware_info(void)
{
    CHAR16 *vendor = g_st ? g_st->FirmwareVendor : 0;
    char one[2] = {0, 0};

    print("Firmware: ");
    if (!vendor || !*vendor) {
        print("(unknown)");
    } else {
        for (; *vendor; vendor++) {
            one[0] = (*vendor < 0x80) ? (char)*vendor : '?';
            print(one);
        }
    }
    print("  revision ");
    print_hex(g_st ? g_st->FirmwareRevision : 0);
    print("\n");
}

/* ------------------------------------------------------------------------- */
/* 设备路径与 UEFI 映像加载                                                   */
/* ------------------------------------------------------------------------- */

/*
 * 为某个 FAT 卷上的文件构造完整设备路径：
 *   <卷的设备路径去掉 End 节点> + FilePath 节点 + End 节点
 *
 * 用 LoadImage(BootPolicy=FALSE, DevicePath=...) 让固件自己读取文件，
 * 这样 LoadedImage->DevicePath 是正确的，Windows Boot Manager 才能找到 BCD。
 */
static EFI_DEVICE_PATH_PROTOCOL *build_file_device_path(EFI_HANDLE device,
                                                        const char *path_ascii)
{
    EFI_DEVICE_PATH_PROTOCOL *device_path = 0;
    EFI_STATUS status;
    CHAR16 wide_path[128];
    UINTN path_length = 0;
    UINTN file_node_size;
    UINTN total_size;
    VOID *buffer = 0;

    status = g_bs->HandleProtocol(device, (EFI_GUID *)&g_efi_device_path_guid,
                                  (VOID **)&device_path);
    if (EFI_ERROR(status) || !device_path) {
        return 0;
    }

    UINTN device_path_size = 0;
    UINT8 *cursor = (UINT8 *)device_path;
    for (;;) {
        EFI_DEVICE_PATH_NODE *node = (EFI_DEVICE_PATH_NODE *)cursor;
        if (node->Length < 4 || device_path_size > 4096) {
            return 0;
        }
        device_path_size += node->Length;
        if (node->Type == 0x7F && node->SubType == 0xFF) {
            break;
        }
        cursor += node->Length;
    }
    if (device_path_size < 4) {
        return 0;
    }

    ascii_to_wide(path_ascii, wide_path, sizeof(wide_path) / sizeof(wide_path[0]));
    while (wide_path[path_length]) {
        path_length++;
    }

    file_node_size = 4 + (path_length + 1) * sizeof(CHAR16);
    total_size = (UINTN)(device_path_size - 4) + file_node_size + 4;

    status = g_bs->AllocatePool(EFI_LOADER_DATA, total_size, &buffer);
    if (EFI_ERROR(status) || !buffer) {
        return 0;
    }

    memcpy(buffer, device_path, device_path_size - 4);

    EFI_DEVICE_PATH_NODE *file_node =
        (EFI_DEVICE_PATH_NODE *)((UINT8 *)buffer + device_path_size - 4);
    file_node->Type = 0x04;    /* MEDIA_DEVICE_PATH */
    file_node->SubType = 0x04; /* MEDIA_FILEPATH_DP */
    file_node->Length = (UINT16)file_node_size;
    memcpy(file_node + 1, wide_path, (path_length + 1) * sizeof(CHAR16));

    EFI_DEVICE_PATH_NODE *end_node =
        (EFI_DEVICE_PATH_NODE *)((UINT8 *)file_node + file_node_size);
    end_node->Type = 0x7F;    /* END_DEVICE_PATH_TYPE */
    end_node->SubType = 0xFF; /* END_ENTIRE_DEVICE_PATH_SUBTYPE */
    end_node->Length = 4;

    return (EFI_DEVICE_PATH_PROTOCOL *)buffer;
}

static EFI_STATUS try_boot_paths(const char *const *paths, UINTN path_count)
{
    EFI_HANDLE *handles = 0;
    UINTN handle_count = 0;
    EFI_STATUS status;
    EFI_STATUS last_error = EFI_NOT_FOUND;

    status = g_bs->LocateHandleBuffer(EFI_LOCATE_BY_PROTOCOL,
                                      (EFI_GUID *)&g_efi_simple_file_system_guid,
                                      0, &handle_count, &handles);
    if (EFI_ERROR(status)) {
        return status;
    }

    print("Scanning file systems...\n");

    for (UINTN i = 0; i < handle_count; i++) {
        for (UINTN p = 0; p < path_count; p++) {
            EFI_DEVICE_PATH_PROTOCOL *file_path =
                build_file_device_path(handles[i], paths[p]);
            if (!file_path) {
                continue;
            }

            EFI_HANDLE loaded_image = 0;
            status = g_bs->LoadImage(0, g_image, file_path, 0, 0, &loaded_image);
            if (EFI_ERROR(status)) {
                g_bs->FreePool(file_path);
                last_error = status;
                continue;
            }

            print("Found ");
            print(paths[p]);
            print("\n");

            print("Starting image...\n");
            UINTN exit_data_size = 0;
            CHAR16 *exit_data = 0;
            status = g_bs->StartImage(loaded_image, &exit_data_size, &exit_data);
            if (EFI_ERROR(status)) {
                print("StartImage failed: ");
                print_status(status);
                print("\n");
                g_bs->UnloadImage(loaded_image);
                g_bs->FreePool(file_path);
                last_error = status;
                continue;
            }

            if (exit_data && exit_data_size) {
                g_bs->FreePool(exit_data);
            }
            g_bs->FreePool(file_path);
            g_bs->FreePool(handles);
            return EFI_SUCCESS;
        }
    }

    g_bs->FreePool(handles);
    return last_error;
}

static EFI_STATUS boot_windows(void)
{
    static const char *const paths[] = {
        "\\EFI\\Microsoft\\Boot\\bootmgfw.efi",
    };
    return try_boot_paths(paths, sizeof(paths) / sizeof(paths[0]));
}

static EFI_STATUS boot_shell(void)
{
    static const char *const paths[] = {
        "\\EFI\\TOOLS\\Shell.efi",
        "\\EFI\\Shell\\Shell.efi",
        "\\shellx64.efi",
    };
    return try_boot_paths(paths, sizeof(paths) / sizeof(paths[0]));
}

/* ------------------------------------------------------------------------- */
/* 电源与固件操作                                                             */
/* ------------------------------------------------------------------------- */

static void reboot_system(void)
{
    print("Rebooting...\n");
    g_rt->ResetSystem(EFI_RESET_COLD, EFI_SUCCESS, 0, 0);
}

static void shutdown_system(void)
{
    print("Shutting down...\n");
    g_rt->ResetSystem(EFI_RESET_SHUTDOWN, EFI_SUCCESS, 0, 0);
}

static void firmware_setup(void)
{
    CHAR16 name[16];
    UINT64 indications = EFI_OS_INDICATIONS_BOOT_TO_FW_UI;

    ascii_to_wide("OsIndications", name, sizeof(name) / sizeof(name[0]));
    EFI_STATUS status = g_rt->SetVariable(
        name, (EFI_GUID *)&g_efi_global_variable_guid,
        EFI_VARIABLE_NON_VOLATILE | EFI_VARIABLE_BOOTSERVICE_ACCESS |
            EFI_VARIABLE_RUNTIME_ACCESS,
        sizeof(indications), &indications);

    if (!EFI_ERROR(status)) {
        print("Rebooting into firmware setup...\n");
        g_bs->Stall(500000);
        g_rt->ResetSystem(EFI_RESET_COLD, EFI_SUCCESS, 0, 0);
    }

    print("Firmware setup is not supported by this system, ");
    print_status(status);
    print("\n");
}

/* ------------------------------------------------------------------------- */
/* 菜单                                                                       */
/* ------------------------------------------------------------------------- */

static void print_banner(void)
{
    print("\n");
    print("============================================================\n");
    print(" ThinkBook 2024 UEFI Bootloader (x86-64)\n");
    print(" USB boot -> menu -> chainload Windows / UEFI Shell\n");
    print("============================================================\n");
    print_firmware_info();
}

static void print_menu(void)
{
    print("\n");
    print("[1] Boot Windows Boot Manager (default)\n");
    print("[2] Boot UEFI Shell\n");
    print("[3] Reboot\n");
    print("[4] Shut down\n");
    print("[5] Firmware setup\n");
    print("[0] Exit to firmware boot manager\n");
    print("\nPress 0-5, Enter = Windows. Auto-boot in 10 seconds...\n");
}

static int read_key(CHAR16 *unicode, UINT16 *scan_code)
{
    EFI_INPUT_KEY key;

    if (!g_st || !g_st->ConIn) {
        return 0;
    }
    if (EFI_ERROR(g_st->ConIn->ReadKeyStroke(g_st->ConIn, &key))) {
        return 0;
    }
    if (key.ScanCode == 0x17) { /* ESC */
        *unicode = 0;
        *scan_code = key.ScanCode;
        return 1;
    }
    if (key.UnicodeChar == 0) {
        return 0;
    }
    *unicode = key.UnicodeChar;
    *scan_code = key.ScanCode;
    return 1;
}

static int wait_for_choice(unsigned timeout_seconds)
{
    const unsigned ticks = timeout_seconds * 10;

    for (unsigned i = 0; i < ticks; i++) {
        CHAR16 unicode = 0;
        UINT16 scan_code = 0;

        while (read_key(&unicode, &scan_code)) {
            if (scan_code == 0x17) {
                return 0;
            }
            if (unicode == 13) { /* Enter */
                return 1;
            }
            if (unicode >= '0' && unicode <= '5') {
                return (int)(unicode - '0');
            }
        }
        g_bs->Stall(100000); /* 100 ms */
    }
    return 1;
}

/* ------------------------------------------------------------------------- */
/* 入口                                                                       */
/* ------------------------------------------------------------------------- */

EFI_STATUS EFIAPI efi_main(EFI_HANDLE image_handle, EFI_SYSTEM_TABLE *system_table)
{
    g_image = image_handle;
    g_st = system_table;
    g_bs = system_table->BootServices;
    g_rt = system_table->RuntimeServices;

    serial_init();
    if (g_st->ConOut) {
        g_st->ConOut->ClearScreen(g_st->ConOut);
    }

    print_banner();

    for (;;) {
        print_menu();
        int choice = wait_for_choice(10);
        print("\n");

        switch (choice) {
        case 0:
            print("Exiting to firmware boot manager...\n");
            return EFI_SUCCESS;

        case 1: {
            EFI_STATUS status = boot_windows();
            if (EFI_ERROR(status)) {
                print("Windows Boot Manager not found or failed: ");
                print_status(status);
                print("\n");
                g_bs->Stall(2000000);
            }
            break;
        }

        case 2: {
            EFI_STATUS status = boot_shell();
            if (EFI_ERROR(status)) {
                print("UEFI Shell not found or failed: ");
                print_status(status);
                print("\n");
                g_bs->Stall(2000000);
            }
            break;
        }

        case 3:
            reboot_system();
            break;

        case 4:
            shutdown_system();
            break;

        case 5:
            firmware_setup();
            break;

        default:
            break;
        }
    }

    return EFI_SUCCESS;
}
