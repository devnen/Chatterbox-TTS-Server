# CUDA 12.8 Support for RTX 5090 and Blackwell GPUs

## Overview

This guide provides instructions for running Chatterbox TTS Server with **CUDA 12.8 and PyTorch 2.8.0**, which includes support for the new **RTX 5090 and Blackwell architecture (sm_120)** GPUs.

## Who Needs This?

Use the CUDA 12.8 configuration if you have:
- **NVIDIA RTX 5090** or other Blackwell-based GPUs
- CUDA compute capability **sm_120** or newer
- CUDA 12.8+ drivers installed on your system

For older GPUs (RTX 3000/4000 series, etc.), continue using the standard configuration with CUDA 12.1.

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/devnen/Chatterbox-TTS-Server.git
cd Chatterbox-TTS-Server

# Build and start the CUDA 12.8 container
docker compose -f docker-compose-cu128.yml up -d

# View logs to confirm GPU is detected
docker logs chatterbox-tts-server-cu128

# Access the web UI
# Open http://localhost:8004 in your browser
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

## Verification

Verify that PyTorch recognizes your RTX 5090:

```bash
docker exec chatterbox-tts-server-cu128 python -c \
  "import torch; \
   print(f'PyTorch: {torch.__version__}'); \
   print(f'CUDA Available: {torch.cuda.is_available()}'); \
   print(f'GPU: {torch.cuda.get_device_name(0)}'); \
   print(f'Supported Architectures: {torch.cuda.get_arch_list()}')"
```

Expected output should include:
```
PyTorch: 2.8.0+cu128
CUDA Available: True
GPU: NVIDIA GeForce RTX 5090
Supported Architectures: ['sm_70', 'sm_75', 'sm_80', 'sm_86', 'sm_90', 'sm_100', 'sm_120']
```

Look for **`sm_120`** in the supported architectures list.

## What's Different?

The CUDA 12.8 configuration differs from the standard setup in the following ways:

### 1. Dockerfile (`Dockerfile.cu128`)
- Uses `nvidia/cuda:12.8.1-runtime-ubuntu22.04` base image
- Installs **PyTorch 2.8.0** with CUDA 12.8 support **before** other dependencies
- Installs chatterbox with `--no-deps` to prevent PyTorch downgrade

### 2. Requirements File (`requirements-nvidia-cu128.txt`)
- Specifies PyTorch 2.8.0 from the `cu128` wheel index
- Documents compatibility with Blackwell architecture

### 3. Docker Compose (`docker-compose-cu128.yml`)
- Uses `Dockerfile.cu128` for building
- Otherwise identical to standard docker-compose.yml

## Prerequisites

### System Requirements
- **CUDA Drivers**: Version 570+ (supports CUDA 12.8)
- **Docker**: With NVIDIA Container Toolkit installed
- **GPU**: RTX 5090 or other Blackwell-based GPU

### Check Your CUDA Version

```bash
nvidia-smi
```

Look for "CUDA Version" in the output - it should show 12.8 or higher.

## Troubleshooting

### Error: "no kernel image is available for execution"

This means PyTorch doesn't support your GPU's compute capability. Verify:

1. **Check PyTorch version** inside the container:
   ```bash
   docker exec chatterbox-tts-server-cu128 python -c "import torch; print(torch.__version__)"
   ```
   Should show `2.8.0+cu128`

2. **Check supported architectures**:
   ```bash
   docker exec chatterbox-tts-server-cu128 python -c "import torch; print(torch.cuda.get_arch_list())"
   ```
   Should include `sm_120`

### Model Loads on CPU Instead of GPU

Check the server logs:
```bash
docker logs chatterbox-tts-server-cu128
```

Look for:
- `Using device: cuda` (confirms GPU mode)
- `TTS Model loaded successfully on cuda` (confirms successful GPU loading)

If you see CPU usage instead, verify:
- Docker has GPU access: `docker run --rm --gpus all nvidia/cuda:12.8.1-runtime-ubuntu22.04 nvidia-smi`
- CUDA is available in container: See verification steps above

### Slow Initial Startup

The first run downloads the Chatterbox model (~3GB). This is cached in:
- Container: `/app/hf_cache`
- Host: `~/.cache/huggingface` (via volume mount)

Subsequent starts will be much faster.

## Compatibility Matrix

| GPU Generation | Architecture | Compute Capability | Docker Config | PyTorch Version |
|----------------|--------------|-------------------|---------------|-----------------|
| RTX 5090 / Blackwell | Blackwell | sm_120 | docker-compose-cu128.yml | 2.8.0+cu128 |
| RTX 4090 / Ada | Ada Lovelace | sm_90 | docker-compose.yml | 2.5.1+cu121 |
| RTX 3090 / Ampere | Ampere | sm_86 | docker-compose.yml | 2.5.1+cu121 |
| RTX 20xx / Turing | Turing | sm_75 | docker-compose.yml | 2.5.1+cu121 |

## Performance Notes

- **VRAM Usage**: Expect ~8-10GB VRAM usage for the model
- **Generation Speed**: RTX 5090 provides significantly faster generation than previous generations
- **First Generation**: May be slower due to JIT compilation; subsequent generations are faster

## Additional Resources

- [PyTorch CUDA 12.8 Documentation](https://pytorch.org/get-started/locally/)
- [NVIDIA CUDA Toolkit](https://developer.nvidia.com/cuda-downloads)
- [Docker NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

## Downgrading to Standard CUDA 12.1

If you need to switch back to the standard configuration:

```bash
# Stop and remove CUDA 12.8 container
docker compose -f docker-compose-cu128.yml down

# Start standard CUDA 12.1 container
docker compose up -d
```

## Contributing

Found an issue with CUDA 12.8 support? Please [open an issue](https://github.com/devnen/Chatterbox-TTS-Server/issues) or submit a pull request.
