#!/usr/bin/env python3
"""
Chatterbox TTS Server - Launcher Script
========================================

A user-friendly launcher with automatic setup, virtual environment
management, dependency installation, and browser auto-open.

Usage:
    Windows: Double-click start.bat
    Manual:  python start.py

Requirements:
    - Python 3.10+ installed and in PATH
    - Windows OS (Linux/Mac users should run server.py directly)
"""

import datetime
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

# ==================== CONFIGURATION ====================

# === Timeout Settings (seconds) ===
SERVER_STARTUP_TIMEOUT = 120  # Max wait for server (model loading takes time)
PORT_CHECK_INTERVAL = 0.5  # How often to check if port is ready
BROWSER_DELAY = 2.0  # Delay before opening browser

# === Path Settings ===
VENV_FOLDER = "venv"  # Virtual environment folder name
REQUIREMENTS_FILE = "requirements.txt"  # Requirements file

# === Debug Settings ===
VERBOSE_LOGGING = False  # Show detailed installation logs
SKIP_BROWSER_ON_ERROR = True  # Don't open browser if startup fails

# ===========================================================

# === Global State ===
_server_process = None


def print_banner():
    """Print the startup banner."""
    print()
    print("=" * 60)
    print("   Chatterbox TTS Server - Launcher")
    print("=" * 60)
    print()


def print_step(step: int, total: int, message: str):
    """Print a numbered step."""
    print(f"[{step}/{total}] {message}")


def print_substep(message: str, status: str = "info"):
    """Print a sub-step with status indicator."""
    icons = {"done": "✓", "error": "✗", "warning": "⚠", "info": "→"}
    icon = icons.get(status, "→")
    print(f"      {icon} {message}")


def print_status_box(host: str, port: int):
    """Print the final status box."""
    display_host = "localhost" if host == "0.0.0.0" else host
    url = f"http://{display_host}:{port}"

    print()
    print("=" * 60)
    print("🎙️  Chatterbox TTS Server is running!")
    print()
    print(f"   Web Interface:  {url}")
    print(f"   API Docs:       {url}/docs")
    if host == "0.0.0.0":
        print("   (Also accessible on your local network)")
    print()
    print("   Press Ctrl+C to stop the server.")
    print("=" * 60)
    print()


def check_windows():
    """Check if running on Windows. Show message for other OS."""
    if sys.platform != "win32":
        print()
        print("=" * 60)
        print("   ⚠️  This launcher is designed for Windows only")
        print("=" * 60)
        print()
        print("   For Linux/Mac users, please run the server directly:")
        print()
        print("   1. Create a virtual environment:")
        print("      python3 -m venv venv")
        print()
        print("   2. Activate it:")
        print("      source venv/bin/activate")
        print()
        print("   3. Install dependencies:")
        print("      pip install -r requirements.txt")
        print()
        print("   4. Run the server:")
        print("      python server.py")
        print()
        print("=" * 60)
        print()
        sys.exit(0)


def check_python_version():
    """Check Python version is 3.10+."""
    if sys.version_info < (3, 10):
        print_substep(f"Python 3.10+ required. Found: {sys.version}", status="error")
        print_substep("Please install Python 3.10 or newer.", status="info")
        sys.exit(1)
    print_substep(
        f"Python {sys.version_info.major}.{sys.version_info.minor} detected",
        status="done",
    )


def check_port_in_use(host: str, port: int) -> bool:
    """Check if a port is already in use."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        check_host = "127.0.0.1" if host == "0.0.0.0" else host
        result = sock.connect_ex((check_host, port))
        sock.close()
        return result == 0
    except socket.error:
        return False


def wait_for_server(host: str, port: int) -> bool:
    """Wait for server to become ready."""
    print_substep(
        "Waiting for server to start (model loading may take 30-90 seconds)..."
    )

    start_time = time.time()
    check_host = "127.0.0.1" if host == "0.0.0.0" else host

    sys.stdout.write("      ")
    sys.stdout.flush()

    dots = 0
    last_dot = start_time

    while time.time() - start_time < SERVER_STARTUP_TIMEOUT:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((check_host, port))
            sock.close()

            if result == 0:
                sys.stdout.write("\n")
                elapsed = time.time() - start_time
                print_substep(f"Server ready! (took {elapsed:.1f}s)", status="done")
                return True
        except socket.error:
            pass

        # Progress dots
        if time.time() - last_dot >= 2:
            sys.stdout.write(".")
            sys.stdout.flush()
            dots += 1
            last_dot = time.time()
            if dots % 30 == 0:
                sys.stdout.write("\n      ")
                sys.stdout.flush()

        time.sleep(PORT_CHECK_INTERVAL)

    sys.stdout.write("\n")
    print_substep(f"Timeout after {SERVER_STARTUP_TIMEOUT}s", status="error")
    return False


def open_browser_delayed(host: str, port: int, delay: float):
    """Open browser after delay in separate thread."""

    def _open():
        time.sleep(delay)
        display_host = "localhost" if host == "0.0.0.0" else host
        url = f"http://{display_host}:{port}"
        try:
            webbrowser.open(url)
        except Exception as e:
            print_substep(f"Could not open browser: {e}", status="warning")

    thread = threading.Thread(target=_open, daemon=True)
    thread.start()


def run_command(
    command: str, cwd: str = None, capture: bool = False, show_output: bool = False
):
    """Run a shell command."""
    try:
        if capture:
            result = subprocess.check_output(
                command, shell=True, cwd=cwd, stderr=subprocess.STDOUT
            )
            return result.decode().strip()

        if show_output or VERBOSE_LOGGING:
            subprocess.check_call(command, shell=True, cwd=cwd)
        else:
            subprocess.check_call(
                command,
                shell=True,
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return True
    except subprocess.CalledProcessError as e:
        if VERBOSE_LOGGING:
            print(f"      [DEBUG] Command failed: {command}")
            print(f"      [DEBUG] Error: {e}")
        return None if capture else False


def ensure_venv(root_dir: Path, venv_dir: Path) -> tuple:
    """Create virtual environment if needed."""
    venv_python = venv_dir / "Scripts" / "python.exe"
    venv_pip = venv_dir / "Scripts" / "pip.exe"

    if not venv_dir.exists():
        print_substep("Creating virtual environment...")
        success = run_command(f'"{sys.executable}" -m venv "{venv_dir}"')
        if not success:
            print_substep("Failed to create virtual environment!", status="error")
            sys.exit(1)
        print_substep("Virtual environment created", status="done")
    else:
        print_substep("Virtual environment found", status="done")

    return str(venv_python), str(venv_pip)


def check_dependencies_installed(venv_pip: str) -> bool:
    """Check if key dependencies are already installed."""
    try:
        # Check for a few key packages that indicate a working install
        result = run_command(f'"{venv_pip}" show fastapi torch', capture=True)
        return result is not None and "Name: fastapi" in result
    except Exception:
        return False


def install_dependencies(
    root_dir: Path, venv_python: str, venv_pip: str, install_flag: Path
):
    """Install dependencies if needed."""
    # First check if flag exists
    if install_flag.exists():
        print_substep("Dependencies already installed", status="done")
        return False

    # Flag doesn't exist, but maybe deps are already installed (existing venv)
    if check_dependencies_installed(venv_pip):
        print_substep(
            "Dependencies already installed (existing venv detected)", status="done"
        )
        # Create the flag so we don't check again
        try:
            install_flag.parent.mkdir(parents=True, exist_ok=True)
            install_flag.write_text(
                f"Installation verified at {datetime.datetime.now().isoformat()}\n"
                f"(Existing venv detected)\n"
            )
        except Exception:
            pass
        return False

    # Actually need to install
    print_substep("First-time setup - installing dependencies...", status="info")
    print_substep("This may take several minutes...", status="info")

    # Upgrade pip
    print_substep("Upgrading pip...")
    run_command(f'"{venv_python}" -m pip install --upgrade pip')

    # Install requirements
    req_file = root_dir / REQUIREMENTS_FILE
    if req_file.exists():
        print_substep(f"Installing from {REQUIREMENTS_FILE}...")
        if not run_command(
            f'"{venv_pip}" install -r "{req_file}"', show_output=VERBOSE_LOGGING
        ):
            print_substep(
                "Some dependencies may have failed to install", status="warning"
            )
    else:
        print_substep(f"{REQUIREMENTS_FILE} not found!", status="error")
        sys.exit(1)

    # Write install flag
    try:
        install_flag.parent.mkdir(parents=True, exist_ok=True)
        install_flag.write_text(
            f"Installation completed at {datetime.datetime.now().isoformat()}\n"
        )
    except Exception as e:
        print_substep(f"Could not write install flag: {e}", status="warning")

    print_substep("Dependencies installed", status="done")
    return True


def read_config(root_dir: Path) -> tuple:
    """Read host and port from config.yaml."""
    config_file = root_dir / "config.yaml"

    # Defaults
    host = "0.0.0.0"
    port = 8004
    auto_open = False

    if config_file.exists():
        try:
            import yaml

            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            if config and "server" in config:
                host = config["server"].get("host", host)
                port = config["server"].get("port", port)

            print_substep(f"Loaded config: {host}:{port}", status="done")
        except ImportError:
            print_substep("PyYAML not available yet, using defaults", status="info")
        except Exception as e:
            print_substep(f"Could not read config.yaml: {e}", status="warning")
    else:
        print_substep("config.yaml not found, using defaults", status="info")

    return host, port, auto_open


def launch_server(
    root_dir: Path, venv_python: str, host: str, port: int
) -> subprocess.Popen:
    """Launch the server."""
    server_script = root_dir / "server.py"

    if not server_script.exists():
        print_substep("server.py not found!", status="error")
        sys.exit(1)

    print_substep(f"Starting server on {host}:{port}...")

    process = subprocess.Popen(
        [venv_python, str(server_script)],
        cwd=str(root_dir),
        creationflags=0,  # Same console window
    )

    return process


def cleanup_server(process: subprocess.Popen):
    """Clean up server process."""
    if process is None or process.poll() is not None:
        return

    try:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    except Exception:
        pass


def main():
    """Main entry point."""
    global _server_process

    # Check OS first
    check_windows()

    # Setup paths
    root_dir = Path(__file__).parent.absolute()
    venv_dir = root_dir / VENV_FOLDER
    install_flag = venv_dir / ".install_complete"

    print_banner()

    # Step 1: Check Python
    print_step(1, 4, "Checking Python installation...")
    check_python_version()

    # Step 2: Virtual environment
    print()
    print_step(2, 4, "Setting up virtual environment...")
    venv_python, venv_pip = ensure_venv(root_dir, venv_dir)

    # Step 3: Dependencies
    print()
    print_step(3, 4, "Checking dependencies...")
    install_dependencies(root_dir, venv_python, venv_pip, install_flag)

    # Step 4: Launch server
    print()
    print_step(4, 4, "Launching Chatterbox TTS Server...")

    # Read config for host/port
    host, port, auto_open = read_config(root_dir)

    # Check port availability
    if check_port_in_use(host, port):
        print_substep(f"Port {port} is already in use!", status="error")
        print_substep(
            "Stop the existing process or change the port in config.yaml", status="info"
        )
        sys.exit(1)

    # Launch
    _server_process = launch_server(root_dir, venv_python, host, port)

    # Wait for ready
    server_ready = wait_for_server(host, port)

    if not server_ready:
        print_substep("Server failed to start", status="error")
        print_substep("Check console output for errors", status="info")
        print_substep("Common issues:", status="info")
        print_substep("  - Missing CUDA/GPU drivers", status="info")
        print_substep("  - Insufficient memory", status="info")
        print_substep("  - Port already in use", status="info")
        cleanup_server(_server_process)
        sys.exit(1)

    # Show status and open browser
    print_status_box(host, port)

    if auto_open and server_ready:
        display_host = "localhost" if host == "0.0.0.0" else host
        print(f"Opening browser to http://{display_host}:{port}...")
        open_browser_delayed(host, port, BROWSER_DELAY)

    # Keep running
    try:
        while True:
            if _server_process.poll() is not None:
                exit_code = _server_process.returncode
                print()
                print_substep(f"Server exited with code {exit_code}", status="warning")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        print("-" * 40)
        print("Shutting down Chatterbox TTS Server...")
        print("-" * 40)
        cleanup_server(_server_process)
        print("Server stopped. Goodbye!")
        print()
        sys.exit(0)

    cleanup_server(_server_process)
    sys.exit(_server_process.returncode if _server_process.returncode else 0)


if __name__ == "__main__":
    main()
