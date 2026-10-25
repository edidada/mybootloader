#!/usr/bin/env python3
"""在 OVMF（UEFI 固件）中真实启动 BOOTX64.EFI，并验证链式加载。

测试流程:
  1. 创建临时 ESP：EFI/BOOT/BOOTX64.EFI + EFI/Microsoft/Boot/bootmgfw.efi（测试载荷）
  2. 用 QEMU + OVMF 启动
  3. 从 COM1 串口输出中等待 bootloader 横幅和载荷标记

依赖: qemu-system-x86_64、OVMF。缺失时默认 SKIP；REQUIRE_QEMU=1 时失败。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

BANNER = "ThinkBook 2024 UEFI Bootloader"
PAYLOAD_MARKER = "CHAINLOAD_PAYLOAD_OK"
PATH_MARKER = "LOADED_IMAGE_PATH_OK"
TIMEOUT_SECONDS = 45

OVMF_COMBINED = (
    "/usr/share/ovmf/OVMF.fd",
    "/usr/share/qemu/OVMF.fd",
    "/usr/share/OVMF/OVMF.fd",
    "/usr/share/edk2/ovmf/OVMF.fd",
)
OVMF_CODE = (
    "/usr/share/OVMF/OVMF_CODE_4M.fd",
    "/usr/share/OVMF/OVMF_CODE.fd",
    "/usr/share/edk2/ovmf/OVMF_CODE_4M.fd",
    "/usr/share/edk2/ovmf/OVMF_CODE.fd",
    "/usr/share/qemu/OVMF_CODE.fd",
)


def find_qemu() -> str | None:
    for candidate in ("qemu-system-x86_64", "qemu-system-i386"):
        if shutil.which(candidate):
            return candidate
    return None


def find_ovmf() -> tuple[str, Path, Path | None] | None:
    """返回 (类型, code/fd 路径, vars 路径或 None)。"""
    override = os.environ.get("OVMF")
    if override:
        path = Path(override)
        if path.is_file():
            if "CODE" in path.name:
                vars_path = path.with_name(path.name.replace("CODE", "VARS"))
                if vars_path.is_file():
                    return ("pflash", path, vars_path)
            else:
                return ("bios", path, None)

    for candidate in OVMF_COMBINED:
        path = Path(candidate)
        if path.is_file():
            return ("bios", path, None)

    for candidate in OVMF_CODE:
        code = Path(candidate)
        vars_path = code.with_name(code.name.replace("CODE", "VARS"))
        if code.is_file() and vars_path.is_file():
            return ("pflash", code, vars_path)

    return None


def make_esp(efi: Path, payload: Path | None) -> Path:
    root = Path(tempfile.mkdtemp(prefix="thinkbook-esp-"))
    boot_dir = root / "EFI" / "BOOT"
    boot_dir.mkdir(parents=True)
    shutil.copy2(efi, boot_dir / "BOOTX64.EFI")

    if payload:
        windows_dir = root / "EFI" / "Microsoft" / "Boot"
        windows_dir.mkdir(parents=True)
        shutil.copy2(payload, windows_dir / "bootmgfw.efi")

    return root


def run_qemu(
    qemu: str, ovmf: tuple[str, Path, Path | None], esp: Path
) -> tuple[int, str]:
    kind, code, vars_path = ovmf

    with tempfile.TemporaryDirectory(prefix="thinkbook-ovmf-") as tmp:
        command = [
            qemu,
            "-machine", "q35",
            "-m", "256",
            "-display", "none",
            "-serial", "stdio",
            "-monitor", "none",
            "-net", "none",
            "-no-reboot",
        ]

        if kind == "bios":
            command += ["-bios", str(code)]
        else:
            assert vars_path is not None
            writable_vars = Path(tmp) / "OVMF_VARS.fd"
            shutil.copy2(vars_path, writable_vars)
            command += [
                "-drive",
                f"if=pflash,format=raw,readonly=on,file={code}",
                "-drive",
                f"if=pflash,format=raw,file={writable_vars}",
            ]

        command += ["-drive", f"format=raw,file=fat:rw:{esp}"]

        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None

        chunks: list[str] = []

        def reader() -> None:
            for line in process.stdout:
                chunks.append(line)

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()

        deadline = time.monotonic() + TIMEOUT_SECONDS
        try:
            while time.monotonic() < deadline:
                text = "".join(chunks)
                if BANNER in text and PAYLOAD_MARKER in text and PATH_MARKER in text:
                    return 0, text
                time.sleep(0.25)
            return 1, "".join(chunks)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def main(argv: list[str]) -> int:
    efi = Path(argv[1]) if len(argv) > 1 else Path("uefi/BOOTX64.EFI")
    payload = Path(argv[2]) if len(argv) > 2 else Path("tests/payload.efi")

    if not efi.is_file():
        print(f"FAIL: 找不到 {efi}，请先运行 `make uefi`")
        return 1
    if not payload.is_file():
        print(f"FAIL: 找不到测试载荷 {payload}，请先运行 `make uefi-payload`")
        return 1

    qemu = os.environ.get("QEMU") or find_qemu()
    ovmf = find_ovmf()
    if not qemu or not ovmf:
        missing = "QEMU" if not qemu else "OVMF"
        if os.environ.get("REQUIRE_QEMU"):
            print(f"FAIL: 未找到 {missing}（REQUIRE_QEMU 已设置）")
            return 1
        print(f"SKIP: 未找到 {missing}，跳过 UEFI 启动测试")
        return 0

    esp = make_esp(efi, payload)
    try:
        result, output = run_qemu(qemu, ovmf, esp)
    finally:
        shutil.rmtree(esp, ignore_errors=True)

    if result == 0:
        print(
            f"PASS: OVMF 启动成功，输出包含 {BANNER!r}、"
            f"{PAYLOAD_MARKER!r} 和 {PATH_MARKER!r}"
        )
        return 0

    print(f"FAIL: 未在 {TIMEOUT_SECONDS} 秒内看到横幅、链式加载和 LoadedImage 路径标记")
    print("--- 串口输出末尾 ---")
    tail = "\n".join(output.strip().splitlines()[-40:])
    print(tail)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
