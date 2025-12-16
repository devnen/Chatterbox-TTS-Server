#!/usr/bin/env python3
"""
Chatterbox TTS Server - Cross-Platform Launcher Script
=======================================================

A user-friendly launcher with automatic setup, virtual environment
management, hardware detection, dependency installation, and server startup.

Features:
- Cross-platform support (Windows, Linux, macOS)
- Automatic GPU detection (NVIDIA, AMD)
- Interactive hardware selection menu
- Virtual environment management
- Dependency installation with progress indication
- Server startup with health checking
- Reinstall/upgrade support

Usage:
    Windows:  Double-click start.bat or run: python start.py
    Linux:    Run: ./start.sh or: python3 start.py

Options:
    --reinstall, -r     Remove existing installation and reinstall fresh
    --upgrade, -u       Upgrade to latest version (keeps hardware selection)
    --cpu               Install CPU version (skip menu)
    --nvidia            Install NVIDIA CUDA 12.1 version (skip menu)
    --nvidia-cu128      Install NVIDIA CUDA 12.8 version (skip menu)
    --rocm              Install AMD ROCm version (skip menu)
    --verbose, -v       Show detailed installation output
    --help, -h          Show this help message

Requirements:
    - Python 3.10 or later
    - Internet connection for downloading dependencies
"""

import argparse
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================

# Virtual environment settings
VENV_FOLDER = "venv"
SERVER_SCRIPT = "server.py"
CONFIG_FILE = "config.yaml"

# Installation type identifiers
INSTALL_CPU = "cpu"
INSTALL_NVIDIA = "nvidia"
INSTALL_NVIDIA_CU128 = "nvidia-cu128"
INSTALL_ROCM = "rocm"

# Requirements file mapping
REQUIREMENTS_MAP = {
    INSTALL_CPU: "requirements.txt",
    INSTALL_NVIDIA: "requirements-nvidia.txt",
    INSTALL_NVIDIA_CU128: "requirements-nvidia-cu128.txt",
    INSTALL_ROCM: "requirements-rocm.txt",
}

# Human-readable names for installation types
INSTALL_NAMES = {
    INSTALL_CPU: "CPU Only",
    INSTALL_NVIDIA: "NVIDIA GPU (CUDA 12.1)",
    INSTALL_NVIDIA_CU128: "NVIDIA GPU (CUDA 12.8 / Blackwell)",
    INSTALL_ROCM: "AMD GPU (ROCm 6.4)",
}

# Chatterbox fork URL (used for CUDA 12.8 installation)
CHATTERBOX_REPO = "git+https://github.com/devnen/chatterbox-v2.git@master"

# Timeout settings (seconds)
SERVER_STARTUP_TIMEOUT = 180  # Model loading can be slow
PORT_CHECK_INTERVAL = 0.5

# Global verbose mode flag (set from args)
VERBOSE_MODE = True


# ============================================================================
# ANSI COLOR SUPPORT
# ============================================================================


class Colors:
    """ANSI color codes for cross-platform colored terminal output."""

    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    # Status icons
    ICON_SUCCESS = "✓"
    ICON_ERROR = "✗"
    ICON_WARNING = "⚠"
    ICON_INFO = "→"
    ICON_WORKING = "●"

    @staticmethod
    def is_windows():
        """Check if running on Windows."""
        return platform.system() == "Windows"

    @staticmethod
    def is_linux():
        """Check if running on Linux."""
        return platform.system() == "Linux"

    @staticmethod
    def is_macos():
        """Check if running on macOS."""
        return platform.system() == "Darwin"

    @classmethod
    def enable_windows_colors(cls):
        """Enable ANSI color support on Windows 10+."""
        if cls.is_windows():
            try:
                import ctypes

                kernel32 = ctypes.windll.kernel32
                # Enable ANSI escape sequences on Windows 10+
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            except Exception:
                # If this fails, colors just won't work (non-fatal)
                pass


# Enable Windows colors at module load time
Colors.enable_windows_colors()


# ============================================================================
# PRINT HELPER FUNCTIONS
# ============================================================================


def print_banner():
    """Print the startup banner."""
    print()
    print("=" * 60)
    print("   Chatterbox TTS Server - Launcher")
    print("=" * 60)
    print()


def print_header(text):
    """Print a section header."""
    print(f"\n{Colors.CYAN}{text}{Colors.RESET}")


def print_step(step, total, message):
    """Print a numbered step."""
    print(f"\n[{step}/{total}] {message}")


def print_substep(message, status="info"):
    """
    Print a sub-step with status indicator.

    Args:
        message: The message to print
        status: One of "done", "error", "warning", "info"
    """
    icons = {
        "done": (Colors.GREEN, Colors.ICON_SUCCESS),
        "error": (Colors.RED, Colors.ICON_ERROR),
        "warning": (Colors.YELLOW, Colors.ICON_WARNING),
        "info": (Colors.RESET, Colors.ICON_INFO),
    }

    color, icon = icons.get(status, (Colors.RESET, Colors.ICON_INFO))
    print(f"      {color}{icon}{Colors.RESET} {message}")


def print_success(text):
    """Print a success message in green."""
    print(f"{Colors.GREEN}{text}{Colors.RESET}")


def print_warning(text):
    """Print a warning message in yellow."""
    print(f"{Colors.YELLOW}{text}{Colors.RESET}")


def print_error(text):
    """Print an error message in red."""
    print(f"{Colors.RED}{text}{Colors.RESET}")


def print_status_box(host, port):
    """Print the final status box with server information."""
    display_host = "localhost" if host == "0.0.0.0" else host
    url = f"http://{display_host}:{port}"

    print()
    print("=" * 60)
    print(f"   {Colors.GREEN}🎙️  Chatterbox TTS Server is running!{Colors.RESET}")
    print()
    print(f"   Web Interface:  {url}")
    print(f"   API Docs:       {url}/docs")

    if host == "0.0.0.0":
        print()
        print("   (Also accessible on your local network)")

    print()
    print("   Press Ctrl+C to stop the server.")
    print("=" * 60)
    print()


def print_reinstall_hint():
    """Print a hint about how to reinstall."""
    print(f"   {Colors.DIM}💡 Tip: To reinstall or upgrade, run:{Colors.RESET}")
    print(f"   {Colors.DIM}   python start.py --reinstall{Colors.RESET}")
    print()


# ============================================================================
# COMMAND EXECUTION
# ============================================================================


def run_command(cmd, cwd=None, check=True, capture=False, show_output=False):
    """
    Run a shell command.

    Args:
        cmd: Command string to execute
        cwd: Working directory (optional)
        check: If True, raise exception on non-zero exit
        capture: If True, capture and return output
        show_output: If True, show output in real-time

    Returns:
        If capture=True: subprocess.CompletedProcess result
        If capture=False: True on success, False on failure
    """
    try:
        if capture:
            result = subprocess.run(
                cmd, shell=True, cwd=cwd, capture_output=True, text=True, check=check
            )
            return result

        if show_output or VERBOSE_MODE:
            # Show output in real-time
            result = subprocess.run(cmd, shell=True, cwd=cwd, check=check)
            return result.returncode == 0 if not check else True
        else:
            # Suppress output
            result = subprocess.run(
                cmd, shell=True, cwd=cwd, capture_output=True, text=True, check=check
            )
            return True

    except subprocess.CalledProcessError as e:
        if check:
            raise
        return None if capture else False
    except Exception as e:
        if VERBOSE_MODE:
            print_error(f"Command error: {e}")
        return None if capture else False


def run_command_with_progress(cmd, cwd=None, description="Working"):
    """
    Run a command with a progress indicator for long operations.

    Args:
        cmd: Command string to execute
        cwd: Working directory (optional)
        description: Description to show during progress

    Returns:
        True on success, False on failure
    """
    if VERBOSE_MODE:
        # In verbose mode, just show output directly
        print_substep(f"Running: {cmd}", "info")
        return run_command(cmd, cwd=cwd, show_output=True, check=False)

    # Start progress indicator in background
    stop_progress = threading.Event()

    def progress_indicator():
        """Background thread to show progress spinner."""
        spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        idx = 0
        while not stop_progress.is_set():
            sys.stdout.write(f"\r      {spinner[idx]} {description}...")
            sys.stdout.flush()
            idx = (idx + 1) % len(spinner)
            time.sleep(0.1)
        # Clear the progress line
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()

    progress_thread = threading.Thread(target=progress_indicator, daemon=True)
    progress_thread.start()

    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True
        )

        stop_progress.set()
        progress_thread.join(timeout=1)

        if result.returncode != 0:
            print_substep(f"Command failed with exit code {result.returncode}", "error")
            if result.stderr:
                # Show last part of error message
                error_lines = result.stderr.strip().split("\n")
                for line in error_lines[-5:]:
                    print(f"         {line}")
            return False

        return True

    except Exception as e:
        stop_progress.set()
        progress_thread.join(timeout=1)
        print_error(f"Error running command: {e}")
        return False


# ============================================================================
# PLATFORM DETECTION
# ============================================================================


def is_windows():
    """Check if running on Windows."""
    return platform.system() == "Windows"


def is_linux():
    """Check if running on Linux."""
    return platform.system() == "Linux"


def is_macos():
    """Check if running on macOS."""
    return platform.system() == "Darwin"


def get_platform_name():
    """Get human-readable platform name."""
    system = platform.system()
    if system == "Windows":
        return "Windows"
    elif system == "Linux":
        return "Linux"
    elif system == "Darwin":
        return "macOS"
    else:
        return system


# ============================================================================
# PYTHON & VIRTUAL ENVIRONMENT FUNCTIONS
# ============================================================================


def check_python_version():
    """
    Verify Python version is 3.10 or later.
    Exits with error if version is too old.
    """
    major = sys.version_info.major
    minor = sys.version_info.minor

    if major < 3 or (major == 3 and minor < 10):
        print_error(f"Python 3.10+ required, but found Python {major}.{minor}")
        print()
        print("Please install Python 3.10 or newer from:")
        print("  https://www.python.org/downloads/")
        print()
        sys.exit(1)

    print_substep(f"Python {major}.{minor}.{sys.version_info.micro} detected", "done")


def get_venv_paths(root_dir):
    """
    Get paths for virtual environment components.

    Args:
        root_dir: Root directory of the project

    Returns:
        Tuple of (venv_dir, venv_python, venv_pip) as Path objects
    """
    venv_dir = root_dir / VENV_FOLDER

    if is_windows():
        venv_python = venv_dir / "Scripts" / "python.exe"
        venv_pip = venv_dir / "Scripts" / "pip.exe"
    else:
        venv_python = venv_dir / "bin" / "python"
        venv_pip = venv_dir / "bin" / "pip"

    return venv_dir, venv_python, venv_pip


def create_venv(venv_dir):
    """
    Create a virtual environment.

    Args:
        venv_dir: Path to create the virtual environment

    Returns:
        True on success, False on failure
    """
    print_substep("Creating virtual environment...")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print_substep("Failed to create virtual environment", "error")
            if result.stderr:
                print(f"         {result.stderr[:200]}")
            return False

        print_substep("Virtual environment created", "done")
        return True

    except Exception as e:
        print_substep(f"Error creating venv: {e}", "error")
        return False


def get_install_state(venv_dir):
    """
    Check if installation is complete and get the install type.

    Args:
        venv_dir: Path to virtual environment directory

    Returns:
        Tuple of (is_installed: bool, install_type: str or None)
    """
    install_complete_file = venv_dir / ".install_complete"
    install_type_file = venv_dir / ".install_type"

    if not install_complete_file.exists():
        return False, None

    install_type = None
    if install_type_file.exists():
        try:
            install_type = install_type_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    return True, install_type


def save_install_state(venv_dir, install_type):
    """
    Save installation state files.

    Args:
        venv_dir: Path to virtual environment directory
        install_type: Type of installation (cpu, nvidia, nvidia-cu128, rocm)
    """
    try:
        # Save install type
        install_type_file = venv_dir / ".install_type"
        install_type_file.write_text(install_type, encoding="utf-8")

        # Save completion marker with timestamp
        install_complete_file = venv_dir / ".install_complete"
        timestamp = datetime.now().isoformat()
        install_complete_file.write_text(
            f"Installation completed at {timestamp}\n" f"Type: {install_type}\n",
            encoding="utf-8",
        )
    except Exception as e:
        print_warning(f"Could not save install state: {e}")


def clear_install_complete(venv_dir):
    """
    Clear only the install complete marker (for upgrades).

    Args:
        venv_dir: Path to virtual environment directory
    """
    install_complete_file = venv_dir / ".install_complete"

    try:
        if install_complete_file.exists():
            install_complete_file.unlink()
    except Exception as e:
        print_warning(f"Could not clear install marker: {e}")


def remove_venv(venv_dir):
    """
    Remove virtual environment with retry for locked files (Windows).

    Args:
        venv_dir: Path to virtual environment directory

    Returns:
        True on success, False on failure
    """
    if not venv_dir.exists():
        return True

    print_substep("Removing existing virtual environment...")

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            shutil.rmtree(venv_dir)
            print_substep("Virtual environment removed", "done")
            return True

        except PermissionError as e:
            if attempt < max_retries - 1:
                print_substep(
                    f"Files locked, retrying in {retry_delay}s... "
                    f"(attempt {attempt + 1}/{max_retries})",
                    "warning",
                )
                time.sleep(retry_delay)
            else:
                print_error(f"Could not remove venv: {e}")
                print_substep(
                    "Try closing any terminals/editors using this folder", "info"
                )
                if is_windows():
                    print_substep("Or run: rmdir /s /q venv", "info")
                else:
                    print_substep("Or run: rm -rf venv", "info")
                return False

        except Exception as e:
            print_error(f"Failed to remove venv: {e}")
            return False

    return False


# ============================================================================
# GPU DETECTION
# ============================================================================


def detect_nvidia_gpu():
    """
    Detect NVIDIA GPU using nvidia-smi.

    Returns:
        Tuple of (found: bool, gpu_name: str or None)
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout.strip():
            gpu_name = result.stdout.strip().split("\n")[0]
            return True, gpu_name

        return False, None

    except FileNotFoundError:
        # nvidia-smi not found
        return False, None
    except subprocess.TimeoutExpired:
        return False, None
    except Exception:
        return False, None


def detect_amd_gpu():
    """
    Detect AMD GPU using rocm-smi.

    Returns:
        Tuple of (found: bool, gpu_name: str or None)
    """
    try:
        result = subprocess.run(
            ["rocm-smi", "--showproductname"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout.strip():
            # Parse output to find GPU name
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if "Card series" in line or "GPU" in line:
                    # Extract the name part
                    parts = line.split(":")
                    if len(parts) > 1:
                        return True, parts[1].strip()

            # If we got output but couldn't parse name, still report found
            return True, "AMD GPU (unknown model)"

        return False, None

    except FileNotFoundError:
        # rocm-smi not found
        return False, None
    except subprocess.TimeoutExpired:
        return False, None
    except Exception:
        return False, None


def detect_gpu():
    """
    Detect available GPUs.

    Returns:
        Dictionary with detection results:
        {
            "nvidia": bool,
            "nvidia_name": str or None,
            "amd": bool,
            "amd_name": str or None,
        }
    """
    nvidia_found, nvidia_name = detect_nvidia_gpu()
    amd_found, amd_name = detect_amd_gpu()

    return {
        "nvidia": nvidia_found,
        "nvidia_name": nvidia_name,
        "amd": amd_found,
        "amd_name": amd_name,
    }


# ============================================================================
# INSTALLATION MENU
# ============================================================================


def get_default_choice(gpu_info):
    """
    Determine the default installation choice based on detected hardware.

    Args:
        gpu_info: Dictionary from detect_gpu()

    Returns:
        Installation type string (INSTALL_CPU, INSTALL_NVIDIA, etc.)
    """
    if gpu_info["nvidia"]:
        return INSTALL_NVIDIA
    elif gpu_info["amd"] and is_linux():
        return INSTALL_ROCM
    else:
        return INSTALL_CPU


def show_installation_menu(gpu_info, default_choice):
    """
    Display installation menu and get user choice.

    Args:
        gpu_info: Dictionary from detect_gpu()
        default_choice: Default installation type

    Returns:
        Selected installation type string
    """
    # Map install types to menu numbers
    MENU_MAP = {
        "1": INSTALL_CPU,
        "2": INSTALL_NVIDIA,
        "3": INSTALL_NVIDIA_CU128,
        "4": INSTALL_ROCM,
    }

    # Reverse map for showing default
    REVERSE_MAP = {v: k for k, v in MENU_MAP.items()}
    default_num = REVERSE_MAP[default_choice]

    # Print GPU detection results
    print()
    print("=" * 60)
    print("   Hardware Detection")
    print("=" * 60)
    print()

    if gpu_info["nvidia"]:
        print_success(f"   NVIDIA GPU: Detected ({gpu_info['nvidia_name']})")
    else:
        print(f"   NVIDIA GPU: {Colors.DIM}Not detected{Colors.RESET}")

    if gpu_info["amd"]:
        print_success(f"   AMD GPU:    Detected ({gpu_info['amd_name']})")
    else:
        print(f"   AMD GPU:    {Colors.DIM}Not detected{Colors.RESET}")

    # Print menu
    print()
    print("=" * 60)
    print("   Select Installation Type")
    print("=" * 60)
    print()

    # Menu options with descriptions
    options = [
        ("1", "CPU Only", "No GPU acceleration - works on any system"),
        ("2", "NVIDIA GPU (CUDA 12.1)", "Standard for RTX 20/30/40 series"),
        ("3", "NVIDIA GPU (CUDA 12.8)", "For RTX 5090 / Blackwell GPUs only"),
        ("4", "AMD GPU (ROCm 6.4)", "For AMD GPUs on Linux"),
    ]

    for num, name, desc in options:
        # Determine if this is the default
        is_default = num == default_num

        # Check for special warnings
        warning = ""
        if num == "4" and is_windows():
            warning = f" {Colors.YELLOW}⚠️ Not supported on Windows{Colors.RESET}"

        # Build the option line
        default_marker = f" {Colors.GREEN}[DEFAULT]{Colors.RESET}" if is_default else ""

        print(f"   [{num}] {name}{default_marker}")
        print(f"       {Colors.DIM}{desc}{warning}{Colors.RESET}")
        print()

    # Get user input
    while True:
        try:
            prompt = f"   Enter choice [{default_num}]: "
            choice = input(prompt).strip()

            # Empty input = default
            if not choice:
                return default_choice

            # Validate input
            if choice in MENU_MAP:
                return MENU_MAP[choice]

            print_warning(f"   Invalid choice '{choice}'. Please enter 1, 2, 3, or 4.")
            print()

        except (EOFError, KeyboardInterrupt):
            print()
            print("   Aborted by user.")
            sys.exit(2)


# ============================================================================
# INSTALLATION FUNCTIONS
# ============================================================================


def upgrade_pip(venv_pip):
    """
    Upgrade pip in the virtual environment.
    """
    print_substep("Upgrading pip...")

    # Get the python executable associated with this pip
    # This prevents file locking issues on Windows by running via python -m
    venv_python = Path(venv_pip).parent / "python.exe"
    if not venv_python.exists():
        venv_python = Path(venv_pip).parent / "python"  # Linux/Mac fallback

    cmd = f'"{venv_python}" -m pip install --upgrade pip'

    # We force check=True here because having an old pip causes the
    # dependency resolution errors you are seeing
    try:
        if VERBOSE_MODE:
            subprocess.check_call(cmd, shell=True)
        else:
            subprocess.check_call(
                cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

        print_substep("pip upgraded", "done")
        return True
    except subprocess.CalledProcessError:
        print_substep("pip upgrade failed", "warning")
        return False


def install_requirements(venv_pip, requirements_file, root_dir):
    """
    Install dependencies from a requirements file.

    Args:
        venv_pip: Path to pip executable in venv
        requirements_file: Name of requirements file
        root_dir: Root directory of the project

    Returns:
        True on success, False on failure
    """
    requirements_path = root_dir / requirements_file

    if not requirements_path.exists():
        print_error(f"Requirements file not found: {requirements_file}")
        return False

    print_substep(f"Installing from {requirements_file}...")

    cmd = f'"{venv_pip}" install -r "{requirements_path}"'

    success = run_command_with_progress(
        cmd,
        cwd=str(root_dir),
        description=f"Installing dependencies from {requirements_file}",
    )

    if success:
        print_substep("Dependencies installed", "done")
    else:
        print_substep("Dependency installation failed", "error")

    return success


def install_chatterbox_no_deps(venv_pip):
    """
    Install Chatterbox TTS without dependencies (for CUDA 12.8).

    Args:
        venv_pip: Path to pip executable in venv

    Returns:
        True on success, False on failure
    """
    print_substep("Installing Chatterbox TTS (--no-deps to preserve PyTorch 2.8)...")

    cmd = f'"{venv_pip}" install --no-deps {CHATTERBOX_REPO}'

    success = run_command_with_progress(cmd, description="Installing Chatterbox TTS")

    if success:
        print_substep("Chatterbox TTS installed", "done")
    else:
        print_substep("Chatterbox TTS installation failed", "error")

    return success


def perform_installation(venv_pip, install_type, root_dir):
    """
    Perform installation based on selected type.

    Args:
        venv_pip: Path to pip executable in venv
        install_type: One of INSTALL_CPU, INSTALL_NVIDIA, INSTALL_NVIDIA_CU128, INSTALL_ROCM
        root_dir: Root directory of the project

    Returns:
        True on success, False on failure
    """
    requirements_file = REQUIREMENTS_MAP.get(install_type)

    if not requirements_file:
        print_error(f"Unknown installation type: {install_type}")
        return False

    # Step 1: Install requirements
    if not install_requirements(venv_pip, requirements_file, root_dir):
        return False

    # Step 2: For CUDA 12.8, install chatterbox separately with --no-deps
    if install_type == INSTALL_NVIDIA_CU128:
        if not install_chatterbox_no_deps(venv_pip):
            return False

    return True


def verify_installation(venv_python):
    """
    Verify critical dependencies are installed correctly.

    Args:
        venv_python: Path to Python executable in venv

    Returns:
        True if verification passed, False otherwise
    """
    print_substep("Verifying installation...")

    # Python script to run inside the venv to test imports
    test_script = """
import sys
import json

results = {}

# Test PyTorch
try:
    import torch
    results["torch"] = {
        "ok": True,
        "version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda if torch.cuda.is_available() else None,
        "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() and torch.cuda.device_count() > 0 else None,
    }
except Exception as e:
    results["torch"] = {"ok": False, "error": str(e)}

# Test FastAPI
try:
    import fastapi
    results["fastapi"] = {"ok": True, "version": fastapi.__version__}
except Exception as e:
    results["fastapi"] = {"ok": False, "error": str(e)}

# Test Chatterbox
try:
    # Try different import paths
    try:
        import chatterbox
        results["chatterbox"] = {"ok": True}
    except ImportError:
        from chatterbox_tts import ChatterboxTTS
        results["chatterbox"] = {"ok": True}
except Exception as e:
    results["chatterbox"] = {"ok": False, "error": str(e)}

# Test audio libraries
try:
    import soundfile
    import librosa
    results["audio"] = {"ok": True}
except Exception as e:
    results["audio"] = {"ok": False, "error": str(e)}

print(json.dumps(results))
"""

    try:
        result = subprocess.run(
            [str(venv_python), "-c", test_script],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            print_substep("Verification script returned non-zero", "warning")
            if result.stderr:
                # Show relevant error info
                error_lines = result.stderr.strip().split("\n")[-3:]
                for line in error_lines:
                    print(f"         {line}")
            return False

        # Parse JSON results
        try:
            results = json.loads(result.stdout)
        except json.JSONDecodeError:
            print_substep("Could not parse verification results", "warning")
            return False

        all_ok = True

        # Report PyTorch status
        torch_result = results.get("torch", {})
        if torch_result.get("ok"):
            version_str = torch_result.get("version", "unknown")

            if torch_result.get("cuda_available"):
                cuda_ver = torch_result.get("cuda_version", "unknown")
                gpu_name = torch_result.get("gpu_name", "unknown")
                print_substep(f"PyTorch {version_str} with CUDA {cuda_ver}", "done")
                print_substep(f"GPU: {gpu_name}", "done")
            else:
                print_substep(f"PyTorch {version_str} (CPU mode)", "done")
        else:
            error = torch_result.get("error", "unknown error")
            print_substep(f"PyTorch: {error}", "error")
            all_ok = False

        # Report FastAPI status
        fastapi_result = results.get("fastapi", {})
        if fastapi_result.get("ok"):
            version = fastapi_result.get("version", "")
            print_substep(f"FastAPI {version}", "done")
        else:
            error = fastapi_result.get("error", "unknown error")
            print_substep(f"FastAPI: {error}", "error")
            all_ok = False

        # Report Chatterbox status
        chatterbox_result = results.get("chatterbox", {})
        if chatterbox_result.get("ok"):
            print_substep("Chatterbox TTS", "done")
        else:
            error = chatterbox_result.get("error", "unknown error")
            print_substep(f"Chatterbox: {error}", "error")
            all_ok = False

        # Report audio libraries status
        audio_result = results.get("audio", {})
        if audio_result.get("ok"):
            print_substep("Audio libraries (soundfile, librosa)", "done")
        else:
            error = audio_result.get("error", "unknown error")
            print_substep(f"Audio libraries: {error}", "error")
            all_ok = False

        return all_ok

    except subprocess.TimeoutExpired:
        print_substep("Verification timed out", "warning")
        return False
    except Exception as e:
        print_substep(f"Verification error: {e}", "warning")
        return False


# ============================================================================
# SERVER MANAGEMENT
# ============================================================================


def read_config(root_dir):
    """
    Read host and port from config.yaml using simple parsing.

    Does not require PyYAML - uses regex-based parsing.

    Args:
        root_dir: Root directory of the project

    Returns:
        Tuple of (host: str, port: int)
    """
    config_file = root_dir / CONFIG_FILE

    # Default values
    host = "0.0.0.0"
    port = 8004

    if not config_file.exists():
        return host, port

    try:
        content = config_file.read_text(encoding="utf-8")

        # Simple regex-based parsing for host and port
        # This handles basic YAML structure without full parsing

        # Look for host setting
        host_match = re.search(
            r'^\s*host:\s*["\']?([^"\'#\n\r]+)["\']?', content, re.MULTILINE
        )
        if host_match:
            parsed_host = host_match.group(1).strip()
            if parsed_host:
                host = parsed_host

        # Look for port setting
        port_match = re.search(r"^\s*port:\s*(\d+)", content, re.MULTILINE)
        if port_match:
            parsed_port = int(port_match.group(1))
            if 1 <= parsed_port <= 65535:
                port = parsed_port

    except Exception as e:
        # Silently use defaults on any error
        if VERBOSE_MODE:
            print_warning(f"Could not parse config.yaml: {e}")

    return host, port


def check_port_in_use(host, port):
    """
    Check if a port is already in use.

    Args:
        host: Host address
        port: Port number

    Returns:
        True if port is in use, False otherwise
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)

        # Use localhost for checking if host is 0.0.0.0
        check_host = "127.0.0.1" if host == "0.0.0.0" else host

        result = sock.connect_ex((check_host, port))
        sock.close()

        return result == 0

    except socket.error:
        return False


def wait_for_server(host, port, timeout=SERVER_STARTUP_TIMEOUT):
    """
    Wait for server to become ready by polling the port.

    Args:
        host: Host address
        port: Port number
        timeout: Maximum seconds to wait

    Returns:
        True if server is ready, False if timeout
    """
    print_substep(
        "Waiting for server to start (model loading may take 30-90 seconds)..."
    )

    start_time = time.time()
    check_host = "127.0.0.1" if host == "0.0.0.0" else host

    # Progress indicator
    sys.stdout.write("      ")
    sys.stdout.flush()

    dots = 0
    last_dot_time = start_time

    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((check_host, port))
            sock.close()

            if result == 0:
                # Server is ready
                sys.stdout.write("\n")
                sys.stdout.flush()
                elapsed = time.time() - start_time
                print_substep(f"Server ready! (took {elapsed:.1f}s)", "done")
                return True

        except socket.error:
            pass

        # Show progress dots
        current_time = time.time()
        if current_time - last_dot_time >= 2:
            sys.stdout.write(".")
            sys.stdout.flush()
            dots += 1
            last_dot_time = current_time

            # Line wrap every 30 dots
            if dots % 30 == 0:
                sys.stdout.write("\n      ")
                sys.stdout.flush()

        time.sleep(PORT_CHECK_INTERVAL)

    # Timeout reached
    sys.stdout.write("\n")
    sys.stdout.flush()
    print_substep(f"Timeout after {timeout}s waiting for server", "error")
    return False


def launch_server(venv_python, root_dir):
    """
    Launch the server as a subprocess.

    Args:
        venv_python: Path to Python executable in venv
        root_dir: Root directory of the project

    Returns:
        subprocess.Popen process object
    """
    server_script = root_dir / SERVER_SCRIPT

    if not server_script.exists():
        print_error(f"{SERVER_SCRIPT} not found!")
        return None

    print_substep(f"Starting {SERVER_SCRIPT}...")

    # Create subprocess
    # On Windows, we don't want to create a new console window
    kwargs = {}
    if is_windows():
        # CREATE_NO_WINDOW flag
        kwargs["creationflags"] = 0

    process = subprocess.Popen(
        [str(venv_python), str(server_script)], cwd=str(root_dir), **kwargs
    )

    return process


def cleanup_server(process):
    """
    Clean up server process gracefully.

    Args:
        process: subprocess.Popen process object
    """
    if process is None:
        return

    if process.poll() is not None:
        # Process already terminated
        return

    try:
        # Try graceful termination first
        process.terminate()

        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Force kill if graceful shutdown fails
            print_substep("Force stopping server...", "warning")
            process.kill()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                # Give up - process may be orphaned
                pass

    except Exception as e:
        # Process might already be gone
        if VERBOSE_MODE:
            print_warning(f"Error during cleanup: {e}")


# ============================================================================
# ARGUMENT PARSER
# ============================================================================


def parse_args():
    """
    Parse command-line arguments.

    Returns:
        argparse.Namespace with parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Chatterbox TTS Server - Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python start.py                    # Normal start (shows menu if first run)
  python start.py --reinstall        # Remove and reinstall (shows menu)
  python start.py --upgrade          # Upgrade keeping current hardware choice
  python start.py --nvidia           # Install/start with NVIDIA CUDA 12.1
  python start.py --nvidia-cu128     # Install/start with NVIDIA CUDA 12.8
  python start.py --cpu              # Install/start with CPU only
  python start.py --rocm             # Install/start with AMD ROCm
  python start.py -v                 # Verbose mode (show all output)
""",
    )

    # Reinstall/upgrade options
    action_group = parser.add_argument_group("Actions")
    action_group.add_argument(
        "--reinstall",
        "-r",
        action="store_true",
        help="Remove existing installation and reinstall fresh (prompts for hardware selection)",
    )
    action_group.add_argument(
        "--upgrade",
        "-u",
        action="store_true",
        help="Upgrade to latest version (keeps current hardware selection)",
    )

    # Direct installation type selection
    install_group = parser.add_argument_group("Installation Type (skip menu)")
    install_group.add_argument(
        "--cpu", action="store_true", help="Install CPU-only version"
    )
    install_group.add_argument(
        "--nvidia", action="store_true", help="Install NVIDIA CUDA 12.1 version"
    )
    install_group.add_argument(
        "--nvidia-cu128",
        action="store_true",
        help="Install NVIDIA CUDA 12.8 version (for RTX 5090/Blackwell)",
    )
    install_group.add_argument(
        "--rocm", action="store_true", help="Install AMD ROCm version (Linux only)"
    )

    # Other options
    other_group = parser.add_argument_group("Other Options")
    other_group.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed installation output"
    )

    return parser.parse_args()


def get_install_type_from_args(args):
    """
    Get installation type from command-line arguments.

    Args:
        args: Parsed arguments from argparse

    Returns:
        Installation type string or None if not specified
    """
    if args.cpu:
        return INSTALL_CPU
    elif args.nvidia:
        return INSTALL_NVIDIA
    elif args.nvidia_cu128:
        return INSTALL_NVIDIA_CU128
    elif args.rocm:
        return INSTALL_ROCM

    return None


# ============================================================================
# MAIN FUNCTION
# ============================================================================


def main():
    """Main entry point for the launcher."""
    global VERBOSE_MODE

    # Parse command-line arguments
    args = parse_args()
    if args.verbose:
        VERBOSE_MODE = True

    # Get root directory (where this script is located)
    root_dir = Path(__file__).parent.absolute()

    # Print banner
    print_banner()

    # Total steps for progress display
    total_steps = 6

    # ========================================================================
    # Step 1: Check Python version
    # ========================================================================
    print_step(1, total_steps, "Checking Python installation...")
    check_python_version()

    # ========================================================================
    # Step 2: Setup paths
    # ========================================================================
    print_step(2, total_steps, "Setting up environment...")
    venv_dir, venv_python, venv_pip = get_venv_paths(root_dir)
    print_substep(f"Project directory: {root_dir}", "info")
    print_substep(f"Virtual environment: {venv_dir}", "info")

    # ========================================================================
    # Step 3: Handle reinstall/upgrade flags
    # ========================================================================
    existing_type = None

    if args.reinstall:
        print_step(3, total_steps, "Preparing fresh reinstall...")
        if venv_dir.exists():
            if not remove_venv(venv_dir):
                print_error("Could not remove existing installation.")
                print_substep(
                    "Please manually delete the 'venv' folder and try again.", "info"
                )
                sys.exit(1)
        print_substep("Ready for fresh installation", "done")

    elif args.upgrade:
        print_step(3, total_steps, "Preparing upgrade...")
        is_installed, existing_type = get_install_state(venv_dir)

        if is_installed and existing_type:
            print_substep(
                f"Current installation: {INSTALL_NAMES.get(existing_type, existing_type)}",
                "info",
            )
            print_substep(
                "Upgrading will reinstall dependencies with the same hardware selection",
                "info",
            )
            # Clear only the install complete marker
            clear_install_complete(venv_dir)
        else:
            print_substep(
                "No existing installation found, will perform fresh install", "warning"
            )

    else:
        print_step(3, total_steps, "Checking existing installation...")
        is_installed, existing_type = get_install_state(venv_dir)

        if is_installed:
            type_name = INSTALL_NAMES.get(existing_type, existing_type)
            print_substep(f"Found existing {type_name} installation", "done")
        else:
            print_substep("No existing installation found", "info")

    # ========================================================================
    # Step 4: Installation flow (if needed)
    # ========================================================================
    is_installed, current_type = get_install_state(venv_dir)

    if not is_installed:
        print_step(4, total_steps, "Installing Chatterbox TTS Server...")

        # Create venv if it doesn't exist
        if not venv_dir.exists():
            if not create_venv(venv_dir):
                print_error("Failed to create virtual environment!")
                print()
                print("Try creating it manually:")
                print(f"  python -m venv {VENV_FOLDER}")
                print()
                sys.exit(1)

        # Determine installation type
        install_type = None

        # First check CLI flags
        install_type = get_install_type_from_args(args)

        # If upgrading, use the existing type
        if install_type is None and existing_type:
            install_type = existing_type
            print_substep(
                f"Using existing hardware selection: {INSTALL_NAMES.get(install_type, install_type)}",
                "info",
            )

        # If still no type, show menu
        if install_type is None:
            print()
            print_substep("Detecting available hardware...", "info")
            gpu_info = detect_gpu()
            default_choice = get_default_choice(gpu_info)
            install_type = show_installation_menu(gpu_info, default_choice)

        # Show selected type
        type_name = INSTALL_NAMES.get(install_type, install_type)
        print()
        print_substep(f"Selected: {type_name}", "done")

        # ROCm warning on Windows
        if install_type == INSTALL_ROCM and is_windows():
            print()
            print_warning("=" * 60)
            print_warning("   ⚠️  WARNING: ROCm is not supported on Windows!")
            print_warning("=" * 60)
            print()
            print_warning("   ROCm (AMD GPU acceleration) only works on Linux.")
            print_warning("   Installation will proceed, but GPU acceleration")
            print_warning("   will NOT work. The server will run on CPU only.")
            print()

            try:
                response = input("   Continue anyway? (y/n) [n]: ").strip().lower()
                if response != "y":
                    print()
                    print("   Installation cancelled.")
                    print("   Tip: Use --nvidia for NVIDIA GPUs or --cpu for CPU-only.")
                    sys.exit(2)
            except (EOFError, KeyboardInterrupt):
                print()
                print("   Cancelled.")
                sys.exit(2)

            print()

        # Upgrade pip
        print()
        upgrade_pip(venv_pip)

        # Perform installation
        print()
        success = perform_installation(venv_pip, install_type, root_dir)

        if not success:
            print()
            print_error("=" * 60)
            print_error("   Installation failed!")
            print_error("=" * 60)
            print()
            print("Troubleshooting tips:")
            print()
            print("  1. Check your internet connection")
            print("  2. Try running with --verbose for more details:")
            print("     python start.py --reinstall --verbose")
            print()
            print("  3. Check if you have enough disk space")
            print()
            print("  4. Try installing manually:")
            requirements_file = REQUIREMENTS_MAP.get(install_type, "requirements.txt")
            print(f"     pip install -r {requirements_file}")
            if install_type == INSTALL_NVIDIA_CU128:
                print(f"     pip install --no-deps {CHATTERBOX_REPO}")
            print()
            sys.exit(1)

        # Verify installation
        print()
        verification_ok = verify_installation(venv_python)

        if not verification_ok:
            print()
            print_warning("Installation verification had some issues.")
            print_warning("The server may still work. Attempting to continue...")

        # Save installation state
        save_install_state(venv_dir, install_type)

        print()
        print_success("=" * 60)
        print_success("   Installation complete!")
        print_success("=" * 60)

    else:
        print_step(4, total_steps, "Using existing installation...")
        type_name = INSTALL_NAMES.get(current_type, current_type or "unknown")
        print_substep(f"Installation type: {type_name}", "done")

    # ========================================================================
    # Step 5: Read configuration
    # ========================================================================
    print_step(5, total_steps, "Loading configuration...")

    host, port = read_config(root_dir)
    print_substep(f"Server will run on {host}:{port}", "done")

    # Check if port is already in use
    if check_port_in_use(host, port):
        print()
        print_error("=" * 60)
        print_error(f"   Port {port} is already in use!")
        print_error("=" * 60)
        print()
        print("Another instance may be running, or another program is using this port.")
        print()
        print("Options:")
        print(f"  1. Stop the other process using port {port}")
        print(f"  2. Change the port in {CONFIG_FILE}")
        print()
        sys.exit(1)

    # ========================================================================
    # Step 6: Launch server
    # ========================================================================
    print_step(6, total_steps, "Launching Chatterbox TTS Server...")

    server_process = launch_server(venv_python, root_dir)

    if server_process is None:
        print_error("Failed to launch server!")
        sys.exit(1)

    # Wait for server to become ready
    server_ready = wait_for_server(host, port)

    if not server_ready:
        print()
        print_error("=" * 60)
        print_error("   Server failed to start!")
        print_error("=" * 60)
        print()
        print("The server did not become ready within the timeout period.")
        print()
        print("Common causes:")
        print("  - Missing CUDA drivers (for GPU installation)")
        print("  - Insufficient memory (model requires ~8GB+ VRAM)")
        print("  - Network issues downloading the model")
        print("  - Port conflict")
        print()
        print("Check the server output above for error messages.")
        print()
        print("Try running with verbose mode for more details:")
        print("  python start.py --verbose")
        print()

        cleanup_server(server_process)
        sys.exit(1)

    # Show success status
    print_status_box(host, port)
    print_reinstall_hint()

    # ========================================================================
    # Keep running until interrupted
    # ========================================================================
    try:
        while True:
            # Check if server process is still running
            exit_code = server_process.poll()

            if exit_code is not None:
                # Server has exited
                print()
                if exit_code == 0:
                    print_substep("Server stopped normally", "done")
                else:
                    print_substep(f"Server exited with code {exit_code}", "warning")
                break

            time.sleep(1)

    except KeyboardInterrupt:
        print()
        print()
        print("-" * 40)
        print("Shutting down Chatterbox TTS Server...")
        print("-" * 40)

        cleanup_server(server_process)

        print()
        print("Server stopped. Goodbye!")
        print()
        sys.exit(0)

    # Clean up
    cleanup_server(server_process)

    # Exit with server's exit code
    exit_code = server_process.returncode if server_process.returncode else 0
    sys.exit(exit_code)


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print()
        print("Interrupted by user.")
        sys.exit(2)
    except Exception as e:
        print()
        print_error(f"Unexpected error: {e}")
        print()
        if VERBOSE_MODE:
            import traceback

            traceback.print_exc()
        else:
            print("Run with --verbose for more details.")
        print()
        sys.exit(1)
