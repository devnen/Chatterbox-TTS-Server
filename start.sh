#!/bin/bash
# ============================================================================
# Chatterbox TTS Server - Linux/macOS Launcher
# ============================================================================
# Run this script to start the Chatterbox TTS Server.
# This script finds Python and runs start.py with all arguments.
#
# Usage:
#   ./start.sh                    # Normal start
#   ./start.sh --reinstall        # Reinstall dependencies
#   ./start.sh --upgrade          # Upgrade to latest version
#   ./start.sh --help             # Show all options
#
# First time setup:
#   chmod +x start.sh
#   ./start.sh
# ============================================================================

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Change to the directory where this script is located
cd "$(dirname "$0")" || exit 1

echo ""
echo "============================================================"
echo "   Chatterbox TTS Server - Launcher"
echo "============================================================"
echo ""

# Check if start.py exists
if [ ! -f "start.py" ]; then
    echo -e "${RED}[ERROR] start.py not found!${NC}"
    echo ""
    echo "Please make sure start.py is in the same folder as this script."
    echo "Current directory: $(pwd)"
    echo ""
    exit 1
fi

# ============================================================================
# Find Python Installation
# ============================================================================
echo "Checking for Python installation..."
echo ""

PYTHON_CMD=""
PYTHON_VERSION=""

# Try python3 first (standard on Linux/macOS)
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    if [[ $PYTHON_VERSION == Python\ 3* ]]; then
        echo -e "${GREEN}[OK]${NC} Found $PYTHON_VERSION (python3)"
        PYTHON_CMD="python3"
    fi
fi

# If python3 not found, try python
if [ -z "$PYTHON_CMD" ]; then
    if command -v python &> /dev/null; then
        PYTHON_VERSION=$(python --version 2>&1)
        if [[ $PYTHON_VERSION == Python\ 3* ]]; then
            echo -e "${GREEN}[OK]${NC} Found $PYTHON_VERSION (python)"
            PYTHON_CMD="python"
        else
            echo -e "${YELLOW}[WARNING]${NC} Found $PYTHON_VERSION but need Python 3.10+"
        fi
    fi
fi

# If still not found, show error
if [ -z "$PYTHON_CMD" ]; then
    echo ""
    echo "============================================================"
    echo -e "${RED}[ERROR] Python 3.10+ not found!${NC}"
    echo "============================================================"
    echo ""
    echo "Please install Python 3.10 or newer."
    echo ""
    echo "On Ubuntu/Debian:"
    echo "  sudo apt update"
    echo "  sudo apt install python3 python3-venv python3-pip"
    echo ""
    echo "On Fedora:"
    echo "  sudo dnf install python3 python3-pip"
    echo ""
    echo "On macOS (with Homebrew):"
    echo "  brew install python@3.12"
    echo ""
    echo "On Arch Linux:"
    echo "  sudo pacman -S python python-pip"
    echo ""
    exit 1
fi

# ============================================================================
# Verify Python version is 3.10+
# ============================================================================
echo ""
echo "Verifying Python version..."

# Extract version numbers
FULL_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
MAJOR=$(echo "$FULL_VERSION" | cut -d. -f1)
MINOR=$(echo "$FULL_VERSION" | cut -d. -f2)

# Check if version is at least 3.10
if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]); then
    echo ""
    echo "============================================================"
    echo -e "${RED}[ERROR] Python version too old!${NC}"
    echo "============================================================"
    echo ""
    echo "Chatterbox TTS Server requires Python 3.10 or newer."
    echo "Found: Python $MAJOR.$MINOR"
    echo ""
    echo "Please install a newer version of Python."
    echo ""
    exit 1
fi

echo -e "${GREEN}[OK]${NC} Python $MAJOR.$MINOR meets requirements (3.10+)"

# ============================================================================
# Check for venv module (required on some Linux distros)
# ============================================================================
echo ""
echo "Checking for Python venv module..."

if ! $PYTHON_CMD -m venv --help &> /dev/null; then
    echo ""
    echo "============================================================"
    echo -e "${YELLOW}[WARNING] Python venv module not found!${NC}"
    echo "============================================================"
    echo ""
    echo "The venv module is required but not installed."
    echo ""
    echo "On Ubuntu/Debian, install it with:"
    echo "  sudo apt install python3-venv"
    echo ""
    echo "On Fedora:"
    echo "  sudo dnf install python3-libs"
    echo ""
    exit 1
fi

echo -e "${GREEN}[OK]${NC} Python venv module available"

# ============================================================================
# Run the main Python script
# ============================================================================
echo ""
echo "============================================================"
echo "Starting Chatterbox TTS Server..."
echo "============================================================"
echo ""
echo "Using: $PYTHON_CMD"
echo ""

# Launch Python script with all arguments
$PYTHON_CMD start.py --verbose "$@"

# Capture the exit code
EXIT_CODE=$?

# Show result message
echo ""
echo "============================================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "Server stopped normally."
elif [ $EXIT_CODE -eq 1 ]; then
    echo -e "${RED}Server exited with an error (code: $EXIT_CODE)${NC}"
elif [ $EXIT_CODE -eq 2 ]; then
    echo "Installation was cancelled."
else
    echo "Server exited with code: $EXIT_CODE"
fi
echo "============================================================"
echo ""

exit $EXIT_CODE
