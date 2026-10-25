/*
 * uefi.h —— 本项目的极简 UEFI 类型/协议定义（x86-64）
 *
 * 只定义 bootloader 实际用到的部分，避免依赖 EDK2 或 gnu-efi。
 * 结构体布局遵循 UEFI 2.10 规范，x86-64 下指针为 8 字节。
 */
#ifndef MYBOOTLOADER_UEFI_H
#define MYBOOTLOADER_UEFI_H

typedef unsigned char UINT8;
typedef unsigned short UINT16;
typedef unsigned int UINT32;
typedef unsigned long long UINT64;
typedef unsigned long long UINTN;
typedef signed short INT16;
typedef signed int INT32;
typedef signed long long INTN;
typedef UINTN EFI_STATUS;
typedef void VOID;
typedef void *EFI_HANDLE;
typedef UINTN EFI_EVENT;
typedef UINT16 CHAR16;

/* UEFI 使用 Microsoft x64 调用约定 */
#define EFIAPI __attribute__((ms_abi))

#define EFI_SUCCESS 0ULL
#define EFI_ERROR_MASK (1ULL << 63)
#define EFI_ERROR(status) (((status) & EFI_ERROR_MASK) != 0)
#define EFI_LOAD_ERROR (EFI_ERROR_MASK | 1ULL)
#define EFI_INVALID_PARAMETER (EFI_ERROR_MASK | 2ULL)
#define EFI_OUT_OF_RESOURCES (EFI_ERROR_MASK | 9ULL)
#define EFI_NOT_FOUND (EFI_ERROR_MASK | 14ULL)

#define EFI_RESET_COLD 0
#define EFI_RESET_SHUTDOWN 2

#define EFI_LOCATE_BY_PROTOCOL 2
#define EFI_LOADER_DATA 2

#define EFI_VARIABLE_NON_VOLATILE 0x00000001
#define EFI_VARIABLE_BOOTSERVICE_ACCESS 0x00000002
#define EFI_VARIABLE_RUNTIME_ACCESS 0x00000004
#define EFI_OS_INDICATIONS_BOOT_TO_FW_UI 0x0000000000000001ULL

typedef struct {
    UINT32 Data1;
    UINT16 Data2;
    UINT16 Data3;
    UINT8 Data4[8];
} EFI_GUID;

typedef struct {
    UINT64 Signature;
    UINT32 Revision;
    UINT32 HeaderSize;
    UINT32 CRC32;
    UINT32 Reserved;
} EFI_TABLE_HEADER;

typedef struct {
    UINT16 Year;
    UINT8 Month;
    UINT8 Day;
    UINT8 Hour;
    UINT8 Minute;
    UINT8 Second;
    UINT8 Pad1;
    UINT32 Nanosecond;
    INT16 TimeZone;
    UINT8 Daylight;
    UINT8 Pad2;
} EFI_TIME;

typedef struct {
    UINT16 ScanCode;
    CHAR16 UnicodeChar;
} EFI_INPUT_KEY;

typedef struct EFI_SIMPLE_TEXT_INPUT_PROTOCOL EFI_SIMPLE_TEXT_INPUT_PROTOCOL;
struct EFI_SIMPLE_TEXT_INPUT_PROTOCOL {
    EFI_STATUS (EFIAPI *Reset)(EFI_SIMPLE_TEXT_INPUT_PROTOCOL *This,
                               UINT8 ExtendedVerification);
    EFI_STATUS (EFIAPI *ReadKeyStroke)(EFI_SIMPLE_TEXT_INPUT_PROTOCOL *This,
                                       EFI_INPUT_KEY *Key);
    EFI_EVENT WaitForKey;
};

typedef struct {
    INT32 MaxMode;
    INT32 Mode;
    INT32 Attribute;
    INT32 CursorColumn;
    INT32 CursorRow;
    UINT8 CursorVisible;
    UINT8 Pad[3];
} EFI_SIMPLE_TEXT_OUTPUT_MODE;

typedef struct EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL;
struct EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL {
    EFI_STATUS (EFIAPI *Reset)(EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
                               UINT8 ExtendedVerification);
    EFI_STATUS (EFIAPI *OutputString)(EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
                                      CHAR16 *String);
    EFI_STATUS (EFIAPI *TestString)(EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
                                    CHAR16 *String);
    EFI_STATUS (EFIAPI *QueryMode)(EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
                                   UINTN ModeNumber,
                                   UINTN *Columns,
                                   UINTN *Rows);
    EFI_STATUS (EFIAPI *SetMode)(EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
                                 UINTN ModeNumber);
    EFI_STATUS (EFIAPI *SetAttribute)(EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
                                      UINTN Attribute);
    EFI_STATUS (EFIAPI *ClearScreen)(EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This);
    EFI_STATUS (EFIAPI *SetCursorPosition)(
        EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This, UINTN Column, UINTN Row);
    EFI_STATUS (EFIAPI *EnableCursor)(EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *This,
                                      UINT8 Visible);
    EFI_SIMPLE_TEXT_OUTPUT_MODE *Mode;
};

typedef struct EFI_DEVICE_PATH_PROTOCOL EFI_DEVICE_PATH_PROTOCOL;

typedef struct {
    UINT8 Type;
    UINT8 SubType;
    UINT16 Length;
} EFI_DEVICE_PATH_NODE;

typedef struct EFI_SYSTEM_TABLE EFI_SYSTEM_TABLE;
typedef struct EFI_BOOT_SERVICES EFI_BOOT_SERVICES;
typedef struct EFI_RUNTIME_SERVICES EFI_RUNTIME_SERVICES;

struct EFI_SYSTEM_TABLE {
    EFI_TABLE_HEADER Hdr;
    CHAR16 *FirmwareVendor;
    UINT32 FirmwareRevision;
    UINT32 Pad;
    EFI_HANDLE ConsoleInHandle;
    EFI_SIMPLE_TEXT_INPUT_PROTOCOL *ConIn;
    EFI_HANDLE ConsoleOutHandle;
    EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *ConOut;
    EFI_HANDLE StandardErrorHandle;
    EFI_SIMPLE_TEXT_OUTPUT_PROTOCOL *StdErr;
    EFI_RUNTIME_SERVICES *RuntimeServices;
    EFI_BOOT_SERVICES *BootServices;
    UINTN NumberOfTableEntries;
    VOID *ConfigurationTable;
};

struct EFI_BOOT_SERVICES {
    EFI_TABLE_HEADER Hdr;

    VOID *RaiseTPL;
    VOID *RestoreTPL;

    EFI_STATUS (EFIAPI *AllocatePages)(UINT32 Type, UINT32 MemoryType,
                                       UINTN Pages, UINT64 *Memory);
    VOID *FreePages;
    VOID *GetMemoryMap;
    EFI_STATUS (EFIAPI *AllocatePool)(UINT32 PoolType, UINTN Size,
                                      VOID **Buffer);
    EFI_STATUS (EFIAPI *FreePool)(VOID *Buffer);

    VOID *CreateEvent;
    VOID *SetTimer;
    VOID *WaitForEvent;
    VOID *SignalEvent;
    VOID *CloseEvent;
    VOID *CheckEvent;
    VOID *InstallProtocolInterface;
    VOID *ReinstallProtocolInterface;
    VOID *UninstallProtocolInterface;
    EFI_STATUS (EFIAPI *HandleProtocol)(EFI_HANDLE Handle,
                                        EFI_GUID *Protocol,
                                        VOID **Interface);
    VOID *Reserved;
    VOID *RegisterProtocolNotify;
    VOID *LocateHandle;
    VOID *LocateDevicePath;

    VOID *InstallConfigurationTable;

    EFI_STATUS (EFIAPI *LoadImage)(UINT8 BootPolicy,
                                   EFI_HANDLE ParentImageHandle,
                                   EFI_DEVICE_PATH_PROTOCOL *DevicePath,
                                   VOID *SourceBuffer, UINTN SourceSize,
                                   EFI_HANDLE *ImageHandle);
    EFI_STATUS (EFIAPI *StartImage)(EFI_HANDLE ImageHandle,
                                    UINTN *ExitDataSize,
                                    CHAR16 **ExitData);
    VOID *Exit;
    EFI_STATUS (EFIAPI *UnloadImage)(EFI_HANDLE ImageHandle);
    VOID *ExitBootServices;
    VOID *GetNextMonotonicCount;

    EFI_STATUS (EFIAPI *Stall)(UINTN Microseconds);

    VOID *SetWatchdogTimer;
    VOID *ConnectController;
    VOID *DisconnectController;
    VOID *OpenProtocol;
    VOID *CloseProtocol;
    VOID *OpenProtocolInformation;
    VOID *ProtocolsPerHandle;

    EFI_STATUS (EFIAPI *LocateHandleBuffer)(UINT32 SearchType,
                                            EFI_GUID *Protocol,
                                            VOID *SearchKey,
                                            UINTN *NoHandles,
                                            EFI_HANDLE **Buffer);
    VOID *LocateProtocol;
    VOID *InstallMultipleProtocolInterfaces;
    VOID *UninstallMultipleProtocolInterfaces;
    VOID *CalculateCrc32;
    VOID *CopyMem;
    VOID *SetMem;
    VOID *CreateEventEx;
};

struct EFI_RUNTIME_SERVICES {
    EFI_TABLE_HEADER Hdr;

    EFI_STATUS (EFIAPI *GetTime)(EFI_TIME *Time, VOID *Capabilities);
    VOID *SetTime;
    VOID *GetWakeupTime;
    VOID *SetWakeupTime;
    VOID *SetVirtualAddressMap;
    VOID *ConvertPointer;

    EFI_STATUS (EFIAPI *GetVariable)(CHAR16 *VariableName,
                                     EFI_GUID *VendorGuid,
                                     UINT32 *Attributes, UINTN *DataSize,
                                     VOID *Data);
    VOID *GetNextVariableName;

    EFI_STATUS (EFIAPI *SetVariable)(CHAR16 *VariableName,
                                     EFI_GUID *VendorGuid,
                                     UINT32 Attributes, UINTN DataSize,
                                     VOID *Data);
    VOID *GetNextHighMonotonicCount;

    VOID (EFIAPI *ResetSystem)(UINT32 ResetType, EFI_STATUS ResetStatus,
                               UINTN DataSize, VOID *ResetData);

    VOID *UpdateCapsule;
    VOID *QueryCapsuleCapabilities;
    VOID *QueryVariableInfo;
};

typedef struct {
    UINT32 Revision;
    EFI_HANDLE ParentHandle;
    EFI_SYSTEM_TABLE *SystemTable;
    EFI_HANDLE DeviceHandle;
    EFI_DEVICE_PATH_PROTOCOL *FilePath;
    VOID *Reserved;
    UINT32 LoadOptionsSize;
    VOID *LoadOptions;
} EFI_LOADED_IMAGE_PROTOCOL;

extern const EFI_GUID g_efi_simple_file_system_guid;
extern const EFI_GUID g_efi_device_path_guid;
extern const EFI_GUID g_efi_global_variable_guid;

#endif /* MYBOOTLOADER_UEFI_H */
