# Suggested README Addition for CUDA 12.8 Support

## Insert this section after "Option 2: NVIDIA GPU Installation (CUDA)" (around line 220)

```markdown
---

### **Option 2b: NVIDIA GPU with CUDA 12.8 (RTX 5090 / Blackwell)**

> **Note:** Only use this if you have an **RTX 5090** or other **Blackwell-based GPU**. For RTX 3000/4000 series, use Option 2 above.

For users with the latest NVIDIA RTX 5090 or other Blackwell architecture GPUs that require CUDA 12.8 and sm_120 support.

**Prerequisites:**
- NVIDIA RTX 5090 or Blackwell-based GPU
- CUDA 12.8+ drivers (driver version 570+)

**Using Docker (Recommended for RTX 5090):**
```bash
# Build and start with CUDA 12.8 support
docker compose -f docker-compose-cu128.yml up -d

# Access the web UI at http://localhost:8004
```

**Manual Installation:**
```bash
# Make sure your (venv) is active
pip install --upgrade pip
pip install -r requirements-nvidia-cu128.txt
pip install --no-deps git+https://github.com/devnen/chatterbox.git
```

**After installation, verify that PyTorch supports sm_120:**
```bash
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0)}'); print(f'Architectures: {torch.cuda.get_arch_list()}')"
```

You should see `sm_120` in the architectures list!

<details>
<summary><strong>💡 Why CUDA 12.8?</strong></summary>

The RTX 5090 uses NVIDIA's new **Blackwell architecture** with compute capability **sm_120**. PyTorch 2.8.0 with CUDA 12.8 is the first stable release that includes support for this architecture. Earlier versions (including CUDA 12.1) will fail with the error: `CUDA error: no kernel image is available for execution on the device`.

See [README_CUDA128.md](README_CUDA128.md) for detailed setup instructions and troubleshooting.
</details>
```

## Additional file to create

Add this note to the Docker section (around line 290-300):

```markdown
**For RTX 5090 / Blackwell GPUs:** Use the CUDA 12.8 configuration:
```bash
docker compose -f docker-compose-cu128.yml up -d
```
See [README_CUDA128.md](README_CUDA128.md) for details.
```
