#!/usr/bin/env python3
"""
ComfyUI Video Generation Environment Validator

Run this script on the gaming PC before setting up Wan 2.2 I2V.
Checks: NVIDIA driver, CUDA, disk space, system RAM, model files, custom nodes.

Usage:
    python validate_comfyui_env.py
    python validate_comfyui_env.py --comfyui-path "D:\\ComfyUI"
    python validate_comfyui_env.py --comfyui-path "D:\\ComfyUI" --verbose
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# ANSI colors (Windows terminal supports these in modern versions)
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def icon(passed: bool) -> str:
    return f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"


def warn_icon() -> str:
    return f"{YELLOW}[WARN]{RESET}"


class ValidationResult:
    def __init__(self):
        self.checks: list[tuple[bool, str]] = []
        self.warnings: list[str] = []

    def add(self, passed: bool, message: str):
        self.checks.append((passed, message))

    def add_warning(self, message: str):
        self.warnings.append(message)

    @property
    def all_passed(self) -> bool:
        return all(passed for passed, _ in self.checks)

    @property
    def fail_count(self) -> int:
        return sum(1 for passed, _ in self.checks if not passed)

    def print_summary(self):
        print(f"\n{BOLD}{'=' * 60}{RESET}")
        print(f"{BOLD}VALIDATION SUMMARY{RESET}")
        print(f"{'=' * 60}")

        for passed, msg in self.checks:
            print(f"  {icon(passed)} {msg}")

        if self.warnings:
            print(f"\n{BOLD}Warnings:{RESET}")
            for w in self.warnings:
                print(f"  {warn_icon()} {w}")

        total = len(self.checks)
        passed = total - self.fail_count
        print(f"\n  {passed}/{total} checks passed", end="")
        if self.fail_count > 0:
            print(f" -- {RED}{self.fail_count} failed{RESET}")
        else:
            print(f" -- {GREEN}All good!{RESET}")
        print()


def find_comfyui_path(hint: str | None) -> Path | None:
    """Try to locate ComfyUI installation."""
    if hint:
        p = Path(hint)
        if p.exists():
            return p

    # Common Windows locations
    candidates = [
        Path("C:/ComfyUI"),
        Path("D:/ComfyUI"),
        Path("C:/Users") / os.environ.get("USERNAME", "") / "ComfyUI",
        Path(os.environ.get("USERPROFILE", "")) / "ComfyUI",
        Path(os.environ.get("USERPROFILE", "")) / "Desktop" / "ComfyUI",
        # Portable installations
        Path("C:/ComfyUI_windows_portable/ComfyUI"),
        Path("D:/ComfyUI_windows_portable/ComfyUI"),
    ]

    for c in candidates:
        if c.exists() and (c / "main.py").exists():
            return c

    return None


def check_nvidia_driver(result: ValidationResult, verbose: bool):
    """Check NVIDIA driver version and CUDA availability."""
    print(f"\n{CYAN}-- NVIDIA / CUDA --{RESET}")

    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=driver_version,name,memory.total",
             "--format=csv,noheader"],
            text=True, timeout=10
        ).strip()

        parts = output.split(", ")
        driver_ver = parts[0] if len(parts) > 0 else "unknown"
        gpu_name = parts[1] if len(parts) > 1 else "unknown"
        vram_mb = parts[2] if len(parts) > 2 else "unknown"

        if verbose:
            print(f"  GPU: {gpu_name}")
            print(f"  Driver: {driver_ver}")
            print(f"  VRAM: {vram_mb}")

        # Check driver version >= 570
        try:
            major = int(driver_ver.split(".")[0])
            result.add(major >= 570, f"NVIDIA driver {driver_ver} (need 570+)")
        except ValueError:
            result.add(False, f"Could not parse driver version: {driver_ver}")

        # Check for RTX 5080
        is_5080 = "5080" in gpu_name
        result.add(True, f"GPU detected: {gpu_name}")
        if not is_5080:
            result.add_warning(f"Expected RTX 5080, found {gpu_name}. Settings may need adjustment.")

        # Check VRAM
        try:
            vram_val = int(vram_mb.replace("MiB", "").strip())
            result.add(vram_val >= 15000, f"VRAM: {vram_mb} (need 16GB)")
        except ValueError:
            result.add_warning(f"Could not parse VRAM: {vram_mb}")

    except FileNotFoundError:
        result.add(False, "nvidia-smi not found -- NVIDIA driver not installed?")
    except subprocess.TimeoutExpired:
        result.add(False, "nvidia-smi timed out")
    except Exception as e:
        result.add(False, f"nvidia-smi error: {e}")

    # Check CUDA version from nvidia-smi
    try:
        output = subprocess.check_output(["nvidia-smi"], text=True, timeout=10)
        for line in output.split("\n"):
            if "CUDA Version" in line:
                cuda_ver = line.split("CUDA Version:")[1].strip().split()[0]
                try:
                    major, minor = cuda_ver.split(".")[:2]
                    ok = int(major) >= 12 and int(minor) >= 8
                    result.add(ok, f"CUDA version {cuda_ver} (need 12.8+)")
                except ValueError:
                    result.add_warning(f"Could not parse CUDA version: {cuda_ver}")
                break
    except Exception:
        pass


def check_system_ram(result: ValidationResult, verbose: bool):
    """Check system RAM (need 32GB+ for model offloading)."""
    print(f"\n{CYAN}-- System RAM --{RESET}")

    if platform.system() == "Windows":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            total_gb = stat.ullTotalPhys / (1024 ** 3)
            avail_gb = stat.ullAvailPhys / (1024 ** 3)
        except Exception:
            total_gb = 0
            avail_gb = 0
    else:
        # Linux fallback
        try:
            with open("/proc/meminfo") as f:
                meminfo = f.read()
            for line in meminfo.split("\n"):
                if line.startswith("MemTotal:"):
                    total_gb = int(line.split()[1]) / (1024 ** 2)
                if line.startswith("MemAvailable:"):
                    avail_gb = int(line.split()[1]) / (1024 ** 2)
        except Exception:
            total_gb = 0
            avail_gb = 0

    if total_gb > 0:
        if verbose:
            print(f"  Total RAM: {total_gb:.1f} GB")
            print(f"  Available: {avail_gb:.1f} GB")
        result.add(total_gb >= 30, f"System RAM: {total_gb:.0f} GB (need 32GB+ for model offloading)")
        if total_gb < 32:
            result.add_warning(
                "Wan 2.2 dual-expert offloads ~14GB model to system RAM between samplers. "
                "With < 32GB RAM, generation may be very slow or fail."
            )
    else:
        result.add_warning("Could not detect system RAM")


def check_disk_space(result: ValidationResult, comfyui_path: Path | None, verbose: bool):
    """Check available disk space."""
    print(f"\n{CYAN}-- Disk Space --{RESET}")

    check_path = comfyui_path or Path(".")
    try:
        usage = shutil.disk_usage(check_path)
        free_gb = usage.free / (1024 ** 3)
        total_gb = usage.total / (1024 ** 3)

        if verbose:
            print(f"  Drive: {check_path.anchor or check_path}")
            print(f"  Total: {total_gb:.0f} GB")
            print(f"  Free: {free_gb:.0f} GB")

        # Wan 2.2 FP8 = ~37GB, HunyuanVideo = ~19GB
        result.add(free_gb >= 40, f"Free disk: {free_gb:.0f} GB (need 40GB+ for Wan 2.2 models)")
        if free_gb < 60:
            result.add_warning(
                f"Only {free_gb:.0f} GB free. Wan 2.2 FP8 needs ~37GB, "
                "HunyuanVideo needs another ~19GB."
            )
    except Exception as e:
        result.add(False, f"Could not check disk space: {e}")


def check_comfyui_install(result: ValidationResult, comfyui_path: Path | None, verbose: bool):
    """Check ComfyUI installation."""
    print(f"\n{CYAN}-- ComfyUI Installation --{RESET}")

    if comfyui_path is None:
        result.add(False, "ComfyUI directory not found. Use --comfyui-path to specify.")
        return

    if verbose:
        print(f"  Path: {comfyui_path}")

    result.add(True, f"ComfyUI found at {comfyui_path}")

    # Check main.py exists
    main_py = comfyui_path / "main.py"
    result.add(main_py.exists(), f"main.py exists")

    # Check custom_nodes directory
    custom_nodes = comfyui_path / "custom_nodes"
    result.add(custom_nodes.exists(), "custom_nodes/ directory exists")

    # Check for ComfyUI Manager
    manager = custom_nodes / "ComfyUI-Manager" if custom_nodes.exists() else None
    if manager and manager.exists():
        result.add(True, "ComfyUI-Manager installed")
    else:
        result.add_warning("ComfyUI-Manager not found -- install it for easy node management")

    # Check for VideoHelperSuite (needed for VHS_VideoCombine)
    vhs = custom_nodes / "ComfyUI-VideoHelperSuite" if custom_nodes.exists() else None
    if vhs and vhs.exists():
        result.add(True, "ComfyUI-VideoHelperSuite installed")
    else:
        result.add(False, "ComfyUI-VideoHelperSuite not found (needed for video output)")


def check_model_files(result: ValidationResult, comfyui_path: Path | None, verbose: bool):
    """Check if required model files are present."""
    print(f"\n{CYAN}-- Wan 2.2 Model Files --{RESET}")

    if comfyui_path is None:
        result.add_warning("Skipping model check -- ComfyUI path not found")
        return

    models_dir = comfyui_path / "models"

    wan22_files = {
        "diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors": "14.3 GB",
        "diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors": "14.3 GB",
        "text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors": "6.74 GB",
        "vae/wan_2.1_vae.safetensors": "254 MB",
        "clip_vision/clip_vision_h.safetensors": "1.7 GB",
    }

    found_count = 0
    for rel_path, expected_size in wan22_files.items():
        full_path = models_dir / rel_path
        exists = full_path.exists()
        if exists:
            found_count += 1
            actual_size = full_path.stat().st_size / (1024 ** 3)
            if verbose:
                print(f"  {GREEN}Found{RESET}: {rel_path} ({actual_size:.2f} GB)")
        else:
            if verbose:
                print(f"  {RED}Missing{RESET}: {rel_path} (expected ~{expected_size})")

        result.add(exists, f"{'Found' if exists else 'MISSING'}: {Path(rel_path).name}")

    print(f"\n{CYAN}-- HunyuanVideo 1.5 Model Files (Optional) --{RESET}")

    hunyuan_files = {
        "diffusion_models/hunyuanvideo1.5_480p_i2v_cfg_distilled_fp8_scaled.safetensors": "8.33 GB",
        "text_encoders/clip_l.safetensors": "250 MB",
        "text_encoders/llava_llama3_fp8_scaled.safetensors": "8 GB",
        "clip_vision/llava_llama3_vision.safetensors": "1.7 GB",
        "vae/hunyuan_video_vae_bf16.safetensors": "250 MB",
    }

    for rel_path, expected_size in hunyuan_files.items():
        full_path = models_dir / rel_path
        exists = full_path.exists()
        label = f"HunyuanVideo: {Path(rel_path).name}"
        if exists:
            if verbose:
                actual_size = full_path.stat().st_size / (1024 ** 3)
                print(f"  {GREEN}Found{RESET}: {rel_path} ({actual_size:.2f} GB)")
            result.add(True, label)
        else:
            if verbose:
                print(f"  {YELLOW}Not found{RESET}: {rel_path} (optional, ~{expected_size})")
            result.add_warning(f"HunyuanVideo not downloaded yet: {Path(rel_path).name}")


def check_python_torch(result: ValidationResult, comfyui_path: Path | None, verbose: bool):
    """Check if Python/PyTorch with CUDA is available."""
    print(f"\n{CYAN}-- Python / PyTorch --{RESET}")

    # Try to find python in ComfyUI's embedded environment
    python_candidates = ["python", "python3"]
    if comfyui_path:
        embedded = comfyui_path / "python_embeded" / "python.exe"
        if embedded.exists():
            python_candidates.insert(0, str(embedded))
        # Also check venv
        venv_python = comfyui_path / "venv" / "Scripts" / "python.exe"
        if venv_python.exists():
            python_candidates.insert(0, str(venv_python))

    for py in python_candidates:
        try:
            ver = subprocess.check_output(
                [py, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
                text=True, timeout=10
            ).strip()

            if verbose:
                print(f"  Python: {py} -> {ver}")

            major, minor = ver.split(".")
            result.add(int(major) >= 3 and int(minor) >= 11, f"Python {ver} (need 3.11+)")

            # Check PyTorch CUDA
            try:
                torch_info = subprocess.check_output(
                    [py, "-c",
                     "import torch; print(f'{torch.__version__}|{torch.version.cuda}|{torch.cuda.is_available()}')"],
                    text=True, timeout=15
                ).strip()

                torch_ver, cuda_ver, cuda_avail = torch_info.split("|")
                if verbose:
                    print(f"  PyTorch: {torch_ver}")
                    print(f"  PyTorch CUDA: {cuda_ver}")
                    print(f"  CUDA available: {cuda_avail}")

                result.add(cuda_avail == "True", f"PyTorch CUDA available: {cuda_avail}")
                if cuda_ver and cuda_ver != "None":
                    try:
                        c_major, c_minor = cuda_ver.split(".")[:2]
                        ok = int(c_major) >= 12 and int(c_minor) >= 8
                        result.add(ok, f"PyTorch CUDA version: {cuda_ver} (need 12.8+)")
                    except ValueError:
                        result.add_warning(f"Could not parse PyTorch CUDA version: {cuda_ver}")
                else:
                    result.add(False, "PyTorch not built with CUDA support")

            except Exception as e:
                result.add(False, f"PyTorch/CUDA check failed: {e}")

            break  # Found a working python

        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    else:
        result.add(False, "No Python found. Check PATH or ComfyUI embedded python.")


def main():
    parser = argparse.ArgumentParser(description="Validate ComfyUI video generation environment")
    parser.add_argument("--comfyui-path", type=str, default=None,
                        help="Path to ComfyUI installation directory")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show detailed output for each check")
    args = parser.parse_args()

    print(f"{BOLD}ComfyUI Video Generation Environment Validator{RESET}")
    print(f"Target: Wan 2.2 I2V 14B FP8 on RTX 5080 (16GB VRAM)")
    print(f"Platform: {platform.system()} {platform.release()}")

    comfyui_path = find_comfyui_path(args.comfyui_path)
    if comfyui_path:
        print(f"ComfyUI: {comfyui_path}")
    else:
        print(f"{YELLOW}ComfyUI not auto-detected. Use --comfyui-path to specify.{RESET}")

    result = ValidationResult()

    check_nvidia_driver(result, args.verbose)
    check_system_ram(result, args.verbose)
    check_disk_space(result, comfyui_path, args.verbose)
    check_comfyui_install(result, comfyui_path, args.verbose)
    check_model_files(result, comfyui_path, args.verbose)
    check_python_torch(result, comfyui_path, args.verbose)

    result.print_summary()

    if not result.all_passed:
        print(f"Fix the {RED}[FAIL]{RESET} items above before proceeding with setup.")
        print(f"See docs/COMFYUI_VIDEO_SETUP.md for download URLs and setup instructions.\n")
        sys.exit(1)
    else:
        print(f"{GREEN}Environment ready for Wan 2.2 I2V setup!{RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
