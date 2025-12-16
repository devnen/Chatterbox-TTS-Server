# CUDA 12.8 Support for RTX 5090 and Blackwell GPUs

## Overview

This guide provides instructions for running Chatterbox TTS Server with **CUDA 12.8 and PyTorch 2.8.0**, which includes support for the new **RTX 5090 and Blackwell architecture (sm_120)** GPUs.

## Who Needs This?

Use the CUDA 12.8 configuration if you have:
- **NVIDIA RTX 5090** or other Blackwell-based GPUs
- CUDA compute capability **sm_120** or newer
- CUDA 12.8+ drivers installed on your system (driver version 570+)

**For older GPUs (RTX 20/30/40 series)**, continue using the standard NVIDIA configuration with CUDA 12.1.

## Quick Start (Recommended)

The easiest way to install with CUDA 12.8 support is using the automated launcher:

### Windows

```bash
# Clone the repository
git clone https://github.com/devnen/Chatterbox-TTS-Server.git
cd Chatterbox-TTS-Server

# Run the launcher (double-click or run from command prompt)
start.bat
```

When the installation menu appears, select option **[3] NVIDIA GPU (CUDA 12.8)**.

### Linux

```bash
# Clone the repository
git clone https://github.com/devnen/Chatterbox-TTS-Server.git
cd Chatterbox-TTS-Server

# Make the launcher executable and run it
chmod +x start.sh
./start.sh
```

When the installation menu appears, select option **[3] NVIDIA GPU (CUDA 12.8)**.

### Direct Installation (Skip Menu)

You can skip the menu by specifying the installation type directly:

```bash
# Windows
python start.py --nvidia-cu128

# Linux
python3 start.py --nvidia-cu128
```

## Docker Installation

For containerized deployment with CUDA 12.8 support:

```bash
# Clone the repository
git clone https://github.com/devnen/Chatterbox-TTS-Server.git
cd Chatterbox-TTS-Server

# Build and start the CUDA 12.8 container
docker compose -f docker-compose-cu128.yml up -d

# View logs to confirm GPU is detected
docker logs chatterbox-tts-server-cu128

# Access the web UI at http://localhost:8004
```

### Manual Docker Build

```bash
# Build the image
docker build -f Dockerfile.cu128 -t chatterbox-tts-server:cu128 .

# Run the container
docker run -d \
  --name chatterbox-tts-cu128 \
  --gpus all \
  -p 8004:8004 \
  -v $(pwd)/model_cache:/app/model_cache \
  -v $(pwd)/outputs:/app/outputs \
  -v $(pwd)/voices:/app/voices \
  -v ~/.cache/huggingface:/app/hf_cache \
  chatterbox-tts-server:cu128
```

## Manual Installation (Alternative)

If you prefer to install manually without using the launcher:

```bash
# Clone the repository
git clone https://github.com/devnen/Chatterbox-TTS-Server.git
cd Chatterbox-TTS-Server

# Create and activate virtual environment
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies (PyTorch 2.8.0 + other requirements)
pip install -r requirements-nvidia-cu128.txt

# IMPORTANT: Install Chatterbox separately with --no-deps
# This prevents PyTorch from being downgraded
pip install --no-deps git+https://github.com/devnen/chatterbox-v2.git@master

# Start the server
python server.py
```

⚠️ **Important:** The `--no-deps` flag is critical for CUDA 12.8 installations. Without it, installing Chatterbox would downgrade PyTorch to an older version that doesn't support Blackwell GPUs.

## Verification

After installation, verify that PyTorch recognizes your RTX 5090:

```bash
# If using the launcher, the verification is automatic
# For manual verification, run:

python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA Available: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0)}'); print(f'Supported Architectures: {torch.cuda.get_arch_list()}')"
```

Expected output should include:
```
PyTorch: 2.8.0+cu128
CUDA Available: True
GPU: NVIDIA GeForce RTX 5090
Supported Architectures: ['sm_70', 'sm_75', 'sm_80', 'sm_86', 'sm_90', 'sm_100', 'sm_120']
```

Look for **`sm_120`** in the supported architectures list - this confirms Blackwell support.

## What's Different from Standard Installation?

The CUDA 12.8 configuration differs from the standard CUDA 12.1 setup:

| Aspect | CUDA 12.1 (Standard) | CUDA 12.8 (Blackwell) |
|--------|---------------------|----------------------|
| PyTorch Version | 2.5.1 | 2.8.0 |
| CUDA Version | 12.1 | 12.8 |
| Blackwell Support | ❌ No | ✅ Yes (sm_120) |
| Requirements File | requirements-nvidia.txt | requirements-nvidia-cu128.txt |
| Chatterbox Install | Included in requirements | Separate with --no-deps |
| Driver Requirement | 525+ | 570+ |

## Prerequisites

### System Requirements

- **Operating System:** Windows 10/11 (64-bit) or Linux
- **Python:** 3.10 or later
- **CUDA Drivers:** Version 570+ (supports CUDA 12.8)
- **GPU:** RTX 5090 or other Blackwell-based GPU
- **VRAM:** 8GB+ recommended

### Check Your CUDA Version

```bash
nvidia-smi
```

Look for "CUDA Version" in the output - it should show **12.8 or higher**.

### Check Your Driver Version

The driver version should be **570 or higher** for CUDA 12.8 support.

## Troubleshooting

### Error: "no kernel image is available for execution"

This error means PyTorch doesn't support your GPU's compute capability. This typically happens when:

1. **Wrong PyTorch version installed** - Verify PyTorch version:
   ```bash
   python -c "import torch; print(torch.__version__)"
   ```
   Should show `2.8.0+cu128` or similar with `cu128`.

2. **PyTorch was downgraded** - This can happen if Chatterbox was installed without `--no-deps`. Reinstall:
   ```bash
   # Using launcher
   python start.py --reinstall --nvidia-cu128
   
   # Or manually
   pip install torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128
   pip install --no-deps git+https://github.com/devnen/chatterbox-v2.git@master
   ```

3. **Check supported architectures**:
   ```bash
   python -c "import torch; print(torch.cuda.get_arch_list())"
   ```
   Should include `sm_120` for Blackwell support.

### Model Loads on CPU Instead of GPU

Check the server logs for device information:
- `Using device: cuda` (confirms GPU mode)
- `TTS Model loaded successfully on cuda` (confirms successful GPU loading)

If you see CPU usage instead:

1. **Verify CUDA is available:**
   ```bash
   python -c "import torch; print(torch.cuda.is_available())"
   ```

2. **Check GPU is visible:**
   ```bash
   python -c "import torch; print(torch.cuda.device_count())"
   ```

3. **Verify driver installation:**
   ```bash
   nvidia-smi
   ```

### Installation Verification Failed

If the launcher reports verification issues:

1. **Run with verbose mode:**
   ```bash
   python start.py --reinstall --nvidia-cu128 --verbose
   ```

2. **Check for import errors manually:**
   ```bash
   # Activate venv first
   python -c "import torch; import fastapi; import chatterbox"
   ```

### Slow Initial Startup

The first run downloads the Chatterbox model (~3GB). This is cached in the Hugging Face cache directory:
- Linux: `~/.cache/huggingface`
- Windows: `C:\Users\<username>\.cache\huggingface`

Subsequent starts will be much faster.

## Compatibility Matrix

| GPU Generation | Architecture | Compute Capability | Installation Option | PyTorch Version |
|----------------|--------------|-------------------|---------------------|-----------------|
| RTX 5090 / Blackwell | Blackwell | sm_120 | `--nvidia-cu128` | 2.8.0+cu128 |
| RTX 4090 / Ada | Ada Lovelace | sm_89 | `--nvidia` | 2.5.1+cu121 |
| RTX 3090 / Ampere | Ampere | sm_86 | `--nvidia` | 2.5.1+cu121 |
| RTX 2080 / Turing | Turing | sm_75 | `--nvidia` | 2.5.1+cu121 |

## Performance Notes

- **VRAM Usage:** Expect ~8-10GB VRAM usage for the model
- **Generation Speed:** RTX 5090 provides significantly faster generation than previous generations
- **First Generation:** May be slower due to JIT compilation; subsequent generations are faster
- **Batch Processing:** Long texts are automatically chunked for optimal memory usage

## Upgrading

To upgrade an existing CUDA 12.8 installation to the latest version:

```bash
# Pull latest changes
git pull origin main

# Upgrade dependencies
python start.py --upgrade
```

Or for a clean reinstall:

```bash
python start.py --reinstall --nvidia-cu128
```

## Switching Between CUDA Versions

### From CUDA 12.1 to CUDA 12.8

```bash
python start.py --reinstall --nvidia-cu128
```

### From CUDA 12.8 to CUDA 12.1

```bash
python start.py --reinstall --nvidia
```

## Docker: Switching Between Configurations

### Switch to CUDA 12.8

```bash
# Stop current container
docker compose down

# Start CUDA 12.8 container
docker compose -f docker-compose-cu128.yml up -d
```

### Switch back to CUDA 12.1

```bash
# Stop CUDA 12.8 container
docker compose -f docker-compose-cu128.yml down

# Start standard container
docker compose up -d
```

## Additional Resources

- [PyTorch CUDA 12.8 Documentation](https://pytorch.org/get-started/locally/)
- [NVIDIA CUDA Toolkit](https://developer.nvidia.com/cuda-downloads)
- [NVIDIA Driver Downloads](https://www.nvidia.com/Download/index.aspx)
- [Docker NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

## Contributing

Found an issue with CUDA 12.8 support? Please [open an issue](https://github.com/devnen/Chatterbox-TTS-Server/issues) or submit a pull request.
