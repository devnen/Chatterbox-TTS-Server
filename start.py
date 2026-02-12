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
    --portable          Use portable Python environment (Windows, skip prompt)
    --no-portable       Use standard virtual environment (Windows, skip prompt)
    --verbose, -v       Show detailed installation output
    --help, -h          Show this help message

Requirements:
    - Python 3.10 or later
    - Internet connection for downloading dependencies
"""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import stat
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================

# TESTING FLAG: Set to True to simulate Python 3.11+ on Windows
# (forces embedded Python fallback even if actual Python version is <3.11)
# This is useful for testing the embedded Python path without installing Python 3.11+
TEST_EMBEDDED_PYTHON_PATH = False

# Virtual environment settings
VENV_FOLDER = "venv"
SERVER_SCRIPT = "server.py"
CONFIG_FILE = "config.yaml"

# Embedded Python settings (Windows fallback for Python 3.11+)
EMBEDDED_PYTHON_DIR = "python_embedded"
EMBEDDED_PYTHON_VERSION = "3.10.11"
EMBEDDED_PYTHON_URL = (
    f"https://www.python.org/ftp/python/{EMBEDDED_PYTHON_VERSION}/"
    f"python-{EMBEDDED_PYTHON_VERSION}-embed-amd64.zip"
)
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

# SHA-256 hash of the embeddable zip for integrity verification.
# Set to "" to skip verification (not recommended for production).
# To compute: download the file from EMBEDDED_PYTHON_URL, then run:
#   python -c "import hashlib; print(hashlib.sha256(open('python-3.10.11-embed-amd64.zip','rb').read()).hexdigest())"
EMBEDDED_PYTHON_SHA256 = ""

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
# First run downloads large model files (~2GB). Subsequent starts are much faster.
SERVER_STARTUP_TIMEOUT = 1800
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


def robust_rmtree(path):
    """
    Remove a directory tree with Windows-hardened error handling.

    Uses an onerror callback to strip read-only attributes (common on
    extracted zip contents), retries on transient permission errors
    (antivirus, Explorer indexing), and falls back to renaming the
    directory aside if deletion fails entirely.

    Args:
        path: Path to directory to remove

    Returns:
        True if directory is gone (deleted or renamed aside), False if stuck
    """
    path = Path(path)
    if not path.exists():
        return True

    def handle_remove_readonly(func, fpath, exc):
        """Clear read-only flag and retry the failed operation."""
        os.chmod(fpath, stat.S_IWRITE)
        func(fpath)

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            shutil.rmtree(path, onerror=handle_remove_readonly)
            return True
        except PermissionError:
            if attempt < max_retries - 1:
                print_substep(
                    f"Files locked, retrying in {retry_delay}s... "
                    f"(attempt {attempt + 1}/{max_retries})",
                    "warning",
                )
                time.sleep(retry_delay)
        except Exception:
            break  # Non-permission error, skip to rename fallback

    # Fallback: rename aside so we can proceed even if deletion fails
    try:
        aside_name = f"{path.name}.old.{int(time.time())}"
        aside_path = path.parent / aside_name
        path.rename(aside_path)
        print_substep(
            f"Could not delete folder; renamed to {aside_name}",
            "warning",
        )
        print_substep("You can safely delete that folder later.", "info")
        return True
    except Exception:
        pass

    return False


def remove_venv(venv_dir):
    """
    Remove an environment directory (venv or embedded) with robust error handling.

    Args:
        venv_dir: Path to environment directory

    Returns:
        True on success, False on failure
    """
    if not venv_dir.exists():
        return True

    print_substep(f"Removing existing environment ({venv_dir.name})...")

    if robust_rmtree(venv_dir):
        print_substep("Environment removed", "done")
        return True

    print_error(f"Could not remove: {venv_dir}")
    print_substep(
        "Try closing any terminals, editors, or antivirus scanning this folder",
        "info",
    )
    if is_windows():
        print_substep(f'Or run: rmdir /s /q "{venv_dir.name}"', "info")
    else:
        print_substep(f'Or run: rm -rf "{venv_dir.name}"', "info")
    return False


# ============================================================================
# EMBEDDED PYTHON (WINDOWS FALLBACK)
# ============================================================================


def get_embedded_python_paths(root_dir):
    """
    Get paths for the embedded Python environment (Windows only).

    Args:
        root_dir: Root directory of the project

    Returns:
        Tuple of (embedded_dir, embedded_python, embedded_pip) as Path objects
    """
    embedded_dir = root_dir / EMBEDDED_PYTHON_DIR
    embedded_python = embedded_dir / "python.exe"
    embedded_pip = embedded_dir / "Scripts" / "pip.exe"
    return embedded_dir, embedded_python, embedded_pip


def is_embedded_python_available(root_dir):
    """
    Check if embedded Python is already set up and functional.

    Args:
        root_dir: Root directory of the project

    Returns:
        True if embedded Python is ready to use
    """
    embedded_dir, embedded_python, embedded_pip = get_embedded_python_paths(root_dir)

    if not embedded_python.exists() or not embedded_pip.exists():
        return False

    try:
        result = subprocess.run(
            [str(embedded_python), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def download_file(url, dest_path, description="Downloading"):
    """
    Download a file from a URL with progress indication.

    Uses urlopen with an explicit per-operation timeout to prevent
    indefinite hanging on flaky networks or corporate proxies.
    Downloads to a temporary .part file first, then atomically moves
    to dest_path so interrupted downloads never leave a valid-looking
    but truncated file at the final path.

    Args:
        url: URL to download from
        dest_path: Local path to save the file
        description: Description shown during download

    Returns:
        True on success, False on failure
    """
    print_substep(f"{description}...")

    dest_path = Path(dest_path)
    part_path = dest_path.parent / (dest_path.name + ".part")

    try:
        response = urllib.request.urlopen(url, timeout=30)
        total_size = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        last_percent = -1

        with open(part_path, "wb") as f:
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)

                if total_size > 0:
                    percent = min(100, int(downloaded * 100 / total_size))
                    if percent != last_percent and percent % 5 == 0:
                        last_percent = percent
                        mb_done = downloaded / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        sys.stdout.write(
                            f"\r      {Colors.ICON_WORKING} {description}... "
                            f"{percent}% ({mb_done:.1f}/{mb_total:.1f} MB)"
                        )
                        sys.stdout.flush()
                else:
                    # No Content-Length: show bytes downloaded without percentage
                    mb_done = downloaded / (1024 * 1024)
                    if int(mb_done * 10) != last_percent:
                        last_percent = int(mb_done * 10)
                        sys.stdout.write(
                            f"\r      {Colors.ICON_WORKING} {description}... "
                            f"{mb_done:.1f} MB"
                        )
                        sys.stdout.flush()

        sys.stdout.write("\n")
        sys.stdout.flush()

        # Atomic move: .part → final path
        os.replace(str(part_path), str(dest_path))
        print_substep(f"{description} complete", "done")
        return True

    except Exception as e:
        sys.stdout.write("\n")
        sys.stdout.flush()
        print_substep(f"Download failed: {e}", "error")
        print_substep(f"You can download manually from: {url}", "info")
        return False

    finally:
        # Clean up partial download on failure (no-op on success since
        # os.replace already moved the .part file to dest_path)
        try:
            if part_path.exists():
                part_path.unlink()
        except Exception:
            pass


def verify_checksum(file_path, expected_sha256):
    """
    Verify SHA-256 hash of a downloaded file.

    Args:
        file_path: Path to the file to verify
        expected_sha256: Expected hex digest string

    Returns:
        True if hash matches, False otherwise
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    actual = sha256.hexdigest()
    if actual != expected_sha256:
        print_substep("Checksum mismatch!", "error")
        print_substep(f"Expected: {expected_sha256}", "info")
        print_substep(f"Actual:   {actual}", "info")
        return False
    return True


def patch_pth_file(embedded_dir):
    """
    Patch the python3XX._pth file to enable pip and package imports.

    The embeddable Python distribution ships with a ._pth file that
    restricts the import path. We need to uncomment 'import site' and
    add 'Lib\\site-packages' so that pip-installed packages are importable.

    Note: pip usage with the embeddable distribution is "not supported"
    per CPython docs, but works reliably with this patching approach.
    The ._pth format has been stable since Python 3.5. Re-test if
    bumping EMBEDDED_PYTHON_VERSION to a new minor release.

    Args:
        embedded_dir: Path to the embedded Python directory

    Returns:
        True on success, False on failure
    """
    try:
        # Find the ._pth file (e.g., python310._pth)
        pth_files = list(embedded_dir.glob("python3*._pth"))

        if not pth_files:
            print_substep("Could not find ._pth file in embedded Python", "error")
            return False

        pth_file = pth_files[0]
        content = pth_file.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Collect path entries, skipping comments, blanks, and the
        # import site directive (which we'll re-add at the end in
        # the canonical position: paths first, import site last).
        path_lines = []
        has_site_packages = False

        for line in lines:
            stripped = line.strip()

            # Skip import site (commented or not) — added back at the end
            if stripped in ("#import site", "import site"):
                continue

            # Skip blank lines and the stock comment
            if not stripped or stripped.startswith("#"):
                continue

            path_lines.append(stripped)
            if "site-packages" in stripped:
                has_site_packages = True

        # Add site-packages path if not already present
        if not has_site_packages:
            path_lines.append("Lib\\site-packages")

        # Add parent directory (project root) so that project modules
        # like config.py, engine.py, utils.py are importable.
        # The embedded Python dir is always <project_root>/python_embedded/,
        # so ".." resolves to the project root at runtime.
        if ".." not in path_lines:
            path_lines.append("..")

        # Canonical order: paths first, then import site last
        path_lines.append("import site")

        pth_file.write_text("\n".join(path_lines) + "\n", encoding="utf-8")

        if VERBOSE_MODE:
            print_substep(f"Patched {pth_file.name}", "done")

        return True

    except Exception as e:
        print_substep(f"Failed to patch ._pth file: {e}", "error")
        return False


def _create_dll_search_sitecustomize(embedded_dir):
    """
    Create a sitecustomize.py in the embedded Python directory that configures
    Windows DLL search paths at interpreter startup.

    This ensures native extensions (.pyd files) can find their dependent DLLs
    regardless of how the embedded Python is launched (via start.py, manually,
    or from a subprocess). The file is automatically loaded by site.py
    (triggered by 'import site' in the ._pth file).

    No-op on non-Windows platforms.

    Args:
        embedded_dir: Path to the embedded Python directory
    """
    sitecustomize_path = Path(embedded_dir) / "sitecustomize.py"

    content = """\
# Auto-generated by start.py -- DO NOT EDIT
# Configures DLL search paths for the embedded Python environment on Windows.
# This ensures native extensions (.pyd) can locate their dependent DLLs.
import os
import sys

if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
    _exe_dir = os.path.dirname(sys.executable)
    _sp_dir = os.path.join(_exe_dir, "Lib", "site-packages")

    for _d in [_exe_dir, _sp_dir]:
        if os.path.isdir(_d):
            try:
                os.add_dll_directory(_d)
            except OSError:
                pass

    # Add *.libs directories (standard wheel pattern for vendored native DLLs,
    # created by auditwheel/delvewheel when packaging binary extensions)
    if os.path.isdir(_sp_dir):
        for _entry in os.listdir(_sp_dir):
            if _entry.endswith(".libs"):
                _libs_path = os.path.join(_sp_dir, _entry)
                if os.path.isdir(_libs_path):
                    try:
                        os.add_dll_directory(_libs_path)
                    except OSError:
                        pass
"""

    try:
        sitecustomize_path.write_text(content, encoding="utf-8")
        if VERBOSE_MODE:
            print_substep("Created sitecustomize.py for DLL search paths", "done")
    except Exception as e:
        print_substep(f"Could not create sitecustomize.py: {e}", "warning")


def setup_embedded_python(root_dir):
    """
    Download and configure an embedded Python 3.10 environment for Windows.

    This creates a fully self-contained Python installation inside the
    project folder with pip bootstrapped and ready to install packages.

    Args:
        root_dir: Root directory of the project

    Returns:
        True on success, False on failure
    """
    embedded_dir = root_dir / EMBEDDED_PYTHON_DIR

    # Check if already available
    if is_embedded_python_available(root_dir):
        print_substep(
            f"Embedded Python {EMBEDDED_PYTHON_VERSION} already set up", "done"
        )
        return True

    # Clean up any partial previous attempt
    if embedded_dir.exists():
        if not robust_rmtree(embedded_dir):
            print_substep("Could not clean up partial install", "error")
            return False

    print_substep(
        f"Setting up portable Python {EMBEDDED_PYTHON_VERSION} environment...", "info"
    )

    zip_path = root_dir / "_python_embedded.zip"
    get_pip_path = root_dir / "_get-pip.py"

    try:
        # Step 1: Download embeddable Python
        if not download_file(
            EMBEDDED_PYTHON_URL,
            zip_path,
            f"Downloading Python {EMBEDDED_PYTHON_VERSION} embeddable package",
        ):
            return False

        # Step 1b: Verify download integrity
        if EMBEDDED_PYTHON_SHA256:
            if not verify_checksum(zip_path, EMBEDDED_PYTHON_SHA256):
                print_substep(
                    "Downloaded file may be corrupted. "
                    "Delete it and try again, or download manually.",
                    "error",
                )
                return False
            if VERBOSE_MODE:
                print_substep("Checksum verified", "done")

        # Step 1c: Validate zip archive
        if not zipfile.is_zipfile(str(zip_path)):
            print_substep("Downloaded file is not a valid zip archive", "error")
            print_substep("Your network may be returning an error page instead", "info")
            return False

        # Step 2: Extract
        print_substep("Extracting Python...")
        try:
            embedded_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(str(zip_path), "r") as zf:
                zf.extractall(str(embedded_dir))
            print_substep("Python extracted", "done")
        except Exception as e:
            print_substep(f"Extraction failed: {e}", "error")
            return False

        # Step 3: Patch ._pth file for pip and site-packages support
        if not patch_pth_file(embedded_dir):
            return False

        # Step 3b: Create sitecustomize.py for DLL search path configuration
        _create_dll_search_sitecustomize(embedded_dir)

        # Step 4: Bootstrap pip
        if not download_file(GET_PIP_URL, get_pip_path, "Downloading pip installer"):
            return False

        embedded_python = embedded_dir / "python.exe"
        print_substep("Installing pip...")

        pip_cmd = [str(embedded_python), str(get_pip_path)]
        if VERBOSE_MODE:
            result = subprocess.run(pip_cmd)
        else:
            result = subprocess.run(pip_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print_substep("Failed to install pip", "error")
            if not VERBOSE_MODE and hasattr(result, "stderr") and result.stderr:
                error_lines = result.stderr.strip().split("\n")[-3:]
                for line in error_lines:
                    print(f"         {line}")
            return False

        # Step 5: Verify pip is usable
        embedded_pip = embedded_dir / "Scripts" / "pip.exe"
        if not embedded_pip.exists():
            print_substep("pip was not created at expected location", "error")
            return False

        print_substep("pip installed", "done")

        # Step 6: Install setuptools (provides pkg_resources, needed by perth and others)
        # Modern get-pip.py no longer bundles setuptools, but many ML/AI packages
        # (including resemble-perth) still import pkg_resources at runtime.
        # Note: pkg_resources was removed in setuptools 81+ (targets Python 3.12+).
        # On Python 3.10 pip resolves to a compatible older version automatically.
        print_substep("Installing setuptools...")
        setuptools_cmd = [
            str(embedded_python),
            "-m",
            "pip",
            "install",
            "--no-warn-script-location",
            "setuptools",
        ]
        if VERBOSE_MODE:
            st_result = subprocess.run(setuptools_cmd)
        else:
            st_result = subprocess.run(setuptools_cmd, capture_output=True, text=True)

        if st_result.returncode != 0:
            print_substep(
                "setuptools installation failed (pkg_resources may be unavailable)",
                "warning",
            )
        else:
            print_substep("setuptools installed", "done")

        print()
        print_substep(
            f"Portable Python {EMBEDDED_PYTHON_VERSION} environment ready", "done"
        )
        return True

    except Exception as e:
        print_substep(f"Unexpected error during setup: {e}", "error")
        return False

    finally:
        # Clean up temporary downloads
        for temp_file in [zip_path, get_pip_path]:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass


def prompt_portable_install(reason="portability"):
    """
    Offer Windows users the portable Python installation option.

    Args:
        reason: "compatibility" (Python 3.11+) or "portability" (Python 3.10)

    Returns:
        True if user wants portable mode, False for standard venv
    """
    major = sys.version_info.major
    minor = sys.version_info.minor

    print()

    if reason == "compatibility":
        # Python 3.11+ — lead with compatibility problem, mention portability
        print(f"{Colors.YELLOW}{'=' * 60}{Colors.RESET}")
        print(
            f"   {Colors.YELLOW}{Colors.ICON_WARNING}  Python {major}.{minor} detected"
            f" — Portable Mode recommended{Colors.RESET}"
        )
        print(f"{Colors.YELLOW}{'=' * 60}{Colors.RESET}")
        print()
        print("   On Windows, Python 3.11+ lacks pre-built binary packages")
        print("   (wheels) for several key dependencies, including ONNX and")
        print("   ONNXRuntime. This causes installation failures that are")
        print("   difficult to resolve.")
        print()
        print(
            f"   {Colors.GREEN}Portable Mode solves this automatically{Colors.RESET}"
            f" by using a compatible"
        )
        print("   Python runtime, and as a bonus makes your entire installation")
        print("   fully portable — copy it to a USB drive, share it as a zip")
        print("   file, or move it anywhere.")
    else:
        # Python 3.10 — lead with portability benefits
        print(f"{Colors.CYAN}{'=' * 60}{Colors.RESET}")
        print(f"   {Colors.CYAN}📦  Portable Mode Available{Colors.RESET}")
        print(f"{Colors.CYAN}{'=' * 60}{Colors.RESET}")
        print()
        print("   The launcher can create a fully self-contained installation.")
        print("   The entire project folder — including Python and all")
        print("   dependencies — becomes completely portable:")
        print()
        print("     • Copy to a USB drive and run on another PC")
        print("     • Zip the folder and share it with others")
        print("     • Move it anywhere on your filesystem")
        print("     • No Python installation needed on the target machine")

    print()

    # Option 1 — Portable (default)
    print(f"   {Colors.BOLD}[1] Install in Portable Mode (recommended){Colors.RESET}")
    print("       Creates a self-contained Python environment inside this folder.")
    print(
        f"       Your system Python {major}.{minor} remains"
        f" {Colors.GREEN}completely untouched{Colors.RESET}."
    )
    print()

    # Option 2 — Standard venv
    print("   [2] Standard installation")
    if reason == "compatibility":
        print(
            f"       {Colors.DIM}Uses system Python {major}.{minor}"
            f" with a virtual environment.{Colors.RESET}"
        )
        print(
            f"       {Colors.DIM}May require Visual C++ Build Tools."
            f" Not portable.{Colors.RESET}"
        )
    else:
        print(
            f"       {Colors.DIM}Uses a standard virtual environment."
            f" Works fine but not portable.{Colors.RESET}"
        )
    print()

    while True:
        try:
            choice = input("   Enter choice [1]: ").strip()

            if choice in ("", "1"):
                return True
            elif choice == "2":
                print()
                if reason == "compatibility":
                    print_substep(
                        f"Continuing with system Python {major}.{minor}", "warning"
                    )
                    print_substep(
                        "If installation fails, re-run with:"
                        " python start.py --reinstall --portable",
                        "info",
                    )
                else:
                    print_substep("Using standard virtual environment", "info")
                return False
            else:
                print_warning(f"   Invalid choice '{choice}'. Please enter 1 or 2.")
                print()

        except (EOFError, KeyboardInterrupt):
            print()
            print("   Aborted by user.")
            sys.exit(2)


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


def upgrade_pip(venv_python):
    """
    Upgrade pip in the environment.

    Args:
        venv_python: Path to the Python executable (venv or embedded)
    """
    print_substep("Upgrading pip...")

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

    # Suppress pip warnings about scripts not on PATH (common with embedded Python)
    cmd = f'"{venv_pip}" install --no-warn-script-location -r "{requirements_path}"'

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


def _patch_chatterbox_watermarker(env_dir, use_embedded):
    """
    Patch installed chatterbox source files to make the Perth watermarker
    gracefully optional. If perth fails to load or PerthImplicitWatermarker
    is None, the server will skip watermarking instead of crashing.

    Uses a no-op watermarker class so that all call sites (apply_watermark)
    continue to work without modification — they just pass audio through
    unchanged.

    This patch is idempotent: re-running it on already-patched files is safe.

    Args:
        env_dir: Path to environment directory (venv or python_embedded)
        use_embedded: True if using embedded Python environment
    """
    # Locate site-packages (differs between embedded, Windows venv, Linux/macOS venv)
    if use_embedded or is_windows():
        site_packages = env_dir / "Lib" / "site-packages"
    else:
        # Linux/macOS venv: lib/python3.X/site-packages
        lib_dir = env_dir / "lib"
        site_packages = None
        if lib_dir.exists():
            for child in sorted(lib_dir.iterdir()):
                if child.name.startswith("python3") and child.is_dir():
                    candidate = child / "site-packages"
                    if candidate.is_dir():
                        site_packages = candidate
                        break
        if site_packages is None:
            print_substep(
                "Could not locate site-packages, skipping watermarker patch",
                "warning",
            )
            return

    # Find chatterbox package directory (name varies by package version)
    chatterbox_dir = None
    for name in ["chatterbox", "chatterbox_tts"]:
        candidate = site_packages / name
        if candidate.is_dir():
            chatterbox_dir = candidate
            break

    if chatterbox_dir is None:
        if VERBOSE_MODE:
            print_substep(
                "Chatterbox package not found, skipping watermarker patch", "info"
            )
        return

    SENTINEL = "# [patched by start.py: watermarker made optional]"
    INIT_TARGET = "self.watermarker = perth.PerthImplicitWatermarker()"
    target_files = ["tts.py", "tts_turbo.py", "mtl_tts.py", "vc.py"]
    patched_count = 0

    for filename in target_files:
        filepath = chatterbox_dir / filename
        if not filepath.exists():
            continue

        try:
            content = filepath.read_text(encoding="utf-8")
        except Exception as e:
            print_substep(f"{filename}: could not read ({e}), skipping", "warning")
            continue

        # Idempotency: skip if already patched
        if SENTINEL in content:
            if VERBOSE_MODE:
                print_substep(f"{filename}: already patched", "info")
            continue

        if INIT_TARGET not in content:
            if VERBOSE_MODE:
                print_substep(f"{filename}: target pattern not found, skipping", "info")
            continue

        # Determine whether this file uses the logging module
        has_logger = "import logging" in content or "getLogger" in content
        if has_logger:
            log_line = (
                "logger.warning("
                '"Perth watermarker unavailable '
                '\\u2014 audio will not be watermarked")'
            )
        else:
            log_line = (
                "print("
                '"Warning: Perth watermarker unavailable '
                '\\u2014 audio will not be watermarked")'
            )

        # Build the replacement block
        lines = content.split("\n")
        new_lines = []

        for line in lines:
            if INIT_TARGET in line and line.lstrip().startswith("self."):
                indent = line[: len(line) - len(line.lstrip())]
                new_lines.append(f"{indent}{SENTINEL}")
                new_lines.append(f"{indent}try:")
                new_lines.append(
                    f"{indent}    self.watermarker = perth.PerthImplicitWatermarker()"
                )
                new_lines.append(f"{indent}except Exception:")
                new_lines.append(f"{indent}    class _NoOpWatermarker:")
                new_lines.append(
                    f"{indent}        def apply_watermark(self, wav, *args, **kwargs):"
                )
                new_lines.append(f"{indent}            return wav")
                new_lines.append(f"{indent}    self.watermarker = _NoOpWatermarker()")
                new_lines.append(f"{indent}    {log_line}")
            else:
                new_lines.append(line)

        try:
            filepath.write_text("\n".join(new_lines), encoding="utf-8")
            print_substep(f"{filename}: watermarker made optional", "done")
            patched_count += 1
        except Exception as e:
            print_substep(f"{filename}: could not write ({e})", "warning")

    if patched_count > 0:
        print_substep(
            f"Patched {patched_count} file(s) for optional watermarking", "done"
        )
    elif VERBOSE_MODE:
        print_substep("No files needed watermarker patching", "info")


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
        "Waiting for server to start (this may take a few minutes on first run)..."
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

    # For embedded Python on Windows, ensure the interpreter directory is on
    # PATH so that python310.dll, vcruntime140.dll, and other co-located DLLs
    # are discoverable by Windows when loading native extensions (.pyd files).
    # This complements the sitecustomize.py os.add_dll_directory() approach.
    env = None
    embedded_dir = root_dir / EMBEDDED_PYTHON_DIR
    if (
        is_windows()
        and embedded_dir.exists()
        and str(venv_python).startswith(str(embedded_dir))
    ):
        env = os.environ.copy()
        env["PATH"] = (
            f"{embedded_dir}{os.pathsep}"
            f"{embedded_dir / 'Scripts'}{os.pathsep}"
            f"{env.get('PATH', '')}"
        )
        if VERBOSE_MODE:
            print_substep("Injected embedded Python into subprocess PATH", "info")

    process = subprocess.Popen(
        [str(venv_python), str(server_script)],
        cwd=str(root_dir),
        env=env,
        **kwargs,
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
  python start.py --portable         # Use portable mode (Windows)
  python start.py --no-portable      # Use standard venv (Windows)
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

    # Environment mode (Windows)
    env_group = parser.add_argument_group("Environment Mode (Windows)")
    env_group.add_argument(
        "--portable",
        action="store_true",
        help="Use portable Python environment (Windows only, skip prompt)",
    )
    env_group.add_argument(
        "--no-portable",
        action="store_true",
        help="Use standard virtual environment instead of portable (skip prompt)",
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

    # Validate portable mode flags
    if args.portable and args.no_portable:
        print_error("Cannot use --portable and --no-portable together.")
        sys.exit(1)

    if args.portable and not is_windows():
        print_error("Portable mode is only available on Windows.")
        print("On Linux and macOS, the standard virtual environment is used.")
        sys.exit(1)

    # Total steps for progress display
    total_steps = 6

    # ========================================================================
    # Step 1: Check Python version
    # ========================================================================
    print_step(1, total_steps, "Checking Python installation...")
    check_python_version()

    # Portable mode decision (Windows only)
    # Determines whether to use the self-contained embedded Python environment
    # or a standard virtual environment. On Linux/macOS, always uses venv.
    use_embedded = False

    if not is_windows():
        use_embedded = False

    elif args.upgrade:
        # During upgrade, preserve existing environment type
        if args.portable or args.no_portable:
            print_substep(
                "--portable/--no-portable ignored during --upgrade. "
                "Use --reinstall to switch modes.",
                "warning",
            )
        if is_embedded_python_available(root_dir):
            use_embedded = True
            print_substep(
                f"Using existing portable Python {EMBEDDED_PYTHON_VERSION}", "done"
            )
        else:
            use_embedded = False

    elif args.no_portable:
        use_embedded = False
        if sys.version_info >= (3, 11):
            print_substep(
                f"Using system Python {sys.version_info.major}.{sys.version_info.minor}"
                f" (--no-portable). Build tools may be required.",
                "warning",
            )

    elif args.portable:
        use_embedded = True
        print_substep("Portable Mode selected via --portable flag", "info")

    elif TEST_EMBEDDED_PYTHON_PATH:
        # In test mode: automatically use portable Python (no prompt)
        use_embedded = True
        print()
        print(f"{Colors.YELLOW}{'=' * 60}{Colors.RESET}")
        print(
            f"   {Colors.YELLOW}{Colors.ICON_INFO}  TEST MODE: Simulating Python 3.11+"
        )
        print(
            f"   {Colors.YELLOW}   → Forcing portable Python environment{Colors.RESET}"
        )
        print(f"{Colors.YELLOW}{'=' * 60}{Colors.RESET}")
        print()

    elif not args.reinstall and is_embedded_python_available(root_dir):
        # Existing portable environment found — reuse it
        use_embedded = True
        print_substep(
            f"Using existing portable Python {EMBEDDED_PYTHON_VERSION}", "done"
        )

    elif sys.version_info >= (3, 11):
        use_embedded = prompt_portable_install(reason="compatibility")

    else:
        # Python 3.10 on Windows — offer portability
        use_embedded = prompt_portable_install(reason="portability")

    # Set up portable Python if chosen but not yet available
    if use_embedded and not is_embedded_python_available(root_dir):
        print()
        if not setup_embedded_python(root_dir):
            print()
            print_error(
                "Could not set up portable Python environment. "
                "Falling back to system Python."
            )
            if sys.version_info >= (3, 11):
                print_substep(
                    "You may need Visual C++ Build Tools for a successful install",
                    "warning",
                )
            use_embedded = False

    # ========================================================================
    # Step 2: Setup paths
    # ========================================================================
    print_step(2, total_steps, "Setting up environment...")

    if use_embedded:
        venv_dir, venv_python, venv_pip = get_embedded_python_paths(root_dir)
        print_substep(f"Project directory: {root_dir}", "info")
        print_substep(f"Python environment: {venv_dir} (portable)", "info")
    else:
        venv_dir, venv_python, venv_pip = get_venv_paths(root_dir)
        print_substep(f"Project directory: {root_dir}", "info")
        print_substep(f"Virtual environment: {venv_dir}", "info")

    # ========================================================================
    # Step 3: Handle reinstall/upgrade flags
    # ========================================================================
    existing_type = None

    if args.reinstall:
        print_step(3, total_steps, "Preparing fresh reinstall...")

        # Remove all possible environment directories (venv and/or embedded)
        for env_name in [VENV_FOLDER, EMBEDDED_PYTHON_DIR]:
            env_path = root_dir / env_name
            if env_path.exists():
                if not remove_venv(env_path):
                    print_error(f"Could not remove {env_name}/.")
                    print_substep(
                        f"Please manually delete the '{env_name}' folder and try again.",
                        "info",
                    )
                    sys.exit(1)

        # Re-setup embedded Python if that path was chosen
        if use_embedded:
            if not setup_embedded_python(root_dir):
                print_error("Failed to set up embedded Python after reinstall!")
                print_substep(
                    "Try again, or run without --reinstall to use system Python.",
                    "info",
                )
                sys.exit(1)
            # Refresh paths after re-creation
            venv_dir, venv_python, venv_pip = get_embedded_python_paths(root_dir)

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

            # Warn Windows users on Python 3.11+ who are using system Python
            if is_windows() and sys.version_info >= (3, 11) and not use_embedded:
                major = sys.version_info.major
                minor = sys.version_info.minor
                print()
                print_warning(
                    f"   Note: You're running Python {major}.{minor} on Windows."
                )
                print_warning(
                    "   If you experience CUDA or dependency issues, your Python"
                )
                print_warning("   version may be the cause. Consider reinstalling with")
                print_warning(
                    "   portable mode:  python start.py --reinstall --portable"
                )
        else:
            print_substep("No existing installation found", "info")

    # ========================================================================
    # Step 4: Installation flow (if needed)
    # ========================================================================
    is_installed, current_type = get_install_state(venv_dir)

    if not is_installed:
        print_step(4, total_steps, "Installing Chatterbox TTS Server...")

        # Create environment if it doesn't exist
        if not venv_dir.exists():
            if use_embedded:
                # Re-setup embedded Python (e.g., after a partial failure)
                if not setup_embedded_python(root_dir):
                    print_error("Failed to set up embedded Python environment!")
                    sys.exit(1)
                venv_dir, venv_python, venv_pip = get_embedded_python_paths(root_dir)
            else:
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
        upgrade_pip(venv_python)

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

        # Patch chatterbox to make watermarker gracefully optional
        print()
        print_substep("Applying post-install patches...")
        _patch_chatterbox_watermarker(venv_dir, use_embedded)

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
