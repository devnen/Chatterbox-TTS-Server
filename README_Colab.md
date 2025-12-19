# README_Colab.md — Run Chatterbox TTS Server on Google Colab (T4 GPU)

This guide shows how to run **Chatterbox-TTS-Server** in a fresh Google Colab notebook with a T4 GPU, using an isolated micromamba environment to avoid Colab package conflicts.  
You will open the Web UI via Colab’s built-in port proxy: Colab displays a `https://localhost:PORT/` link that actually points to an externally reachable `*.colab.*` URL. [web:146]

---

## What you will get

After completing Cells **1 → 4**:
- The Web UI opens in your browser from the Colab proxy link. [web:146]
- The Turbo model downloads on first run and loads on GPU.
- The server status endpoint reports the model is loaded (Cell 4 prints `/api/model-info`). [file:21]

---

## Important rules (read first)

- **Do not use “Run all.”** Cell 4 runs the server in the foreground and will keep running while the server is up, so “Run all” will either hang or behave unexpectedly.
- Run cells **one-by-one**, waiting for each cell to finish before running the next cell.
- Keep the notebook tab open while using the Web UI; if the runtime disconnects, the server stops.

---

## First-time setup (Cells 1 → 4)

### Cell 1 — Create isolated Python 3.11 environment (micromamba)

```
%%bash
set -e

cd /content

# Download micromamba into /content/bin/micromamba
curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj bin/micromamba

# Create a clean env (isolated from Colab’s global packages)
./bin/micromamba create -y -n cb311 -c conda-forge python=3.11 pip

echo "✅ micromamba ready at /content/bin/micromamba"
echo "✅ env created: cb311"
```

---

### Cell 2 — Install PyTorch (CUDA 12.1) + ONNX + Chatterbox fork

Notes:
- This uses **absolute paths** (`/content/bin/micromamba`) so it works regardless of current directory.
- It force-reinstalls the package to avoid stale cached installs.

```
%%bash
set -euo pipefail

cd /content
MICROMAMBA="/content/bin/micromamba"

ts() { date +"[%Y-%m-%d %H:%M:%S]"; }

echo "$(ts) Sanity check micromamba:"
ls -lah "$MICROMAMBA"

echo "$(ts) Upgrading pip tooling inside cb311..."
"$MICROMAMBA" run -n cb311 python -m pip install -U pip setuptools wheel --progress-bar on

echo "$(ts) Installing PyTorch 2.5.1 (CUDA 12.1)... (this can take a while)"
"$MICROMAMBA" run -n cb311 pip install \
  --progress-bar on \
  torch==2.5.1+cu121 torchaudio==2.5.1+cu121 torchvision==0.20.1+cu121 \
  --index-url https://download.pytorch.org/whl/cu121

echo "$(ts) Installing ONNX (wheel)..."
"$MICROMAMBA" run -n cb311 pip install --progress-bar on onnx==1.16.0

echo "$(ts) Installing Chatterbox package (from GitHub, no-cache, upgrade)..."
"$MICROMAMBA" run -n cb311 pip uninstall -y chatterbox-tts chatterbox || true
"$MICROMAMBA" run -n cb311 pip install \
  --no-cache-dir --upgrade \
  --progress-bar on \
  "chatterbox-tts @ git+https://github.com/devnen/chatterbox-v2.git@master"

echo "$(ts) ✅ Installation complete!"
```

---

### Cell 3 — Verify GPU + verify Turbo won’t require Hugging Face tokens

This checks CUDA visibility and prints the installed `from_pretrained()` source so you can confirm it does **not** force Hugging Face auth via a `token=True` fallback (in `huggingface_hub`, `token=True` means “read token from local config,” and errors if none exists). [web:65]

```
%%bash
set -e

/content/bin/micromamba run -n cb311 python - <<'PY'
import inspect, torch
import chatterbox.tts_turbo as t

print("✅ torch:", torch.__version__)
print("✅ cuda available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("✅ gpu:", torch.cuda.get_device_name(0))

print("✅ chatterbox.tts_turbo path:", t.__file__)

src = inspect.getsource(t.ChatterboxTurboTTS.from_pretrained)
print("\n--- from_pretrained() (first ~80 lines) ---")
print("\n".join(src.splitlines()[:80]))

# Heuristic check for the common buggy pattern that forces token=True semantics
markers = [" or True", "token=True", "token = True", "use_auth_token=True"]
hits = [m for m in markers if m in src]
print("\nHeuristic auth-forcing markers found:", hits)

if hits:
    raise SystemExit(
        "\n❌ This install still appears to force HF auth.\n"
        "Re-run Cell 2 (it already uses --no-cache-dir --upgrade).\n"
    )

print("\n✅ Looks good: Turbo should download without requiring user tokens.")
PY
```

---

### Cell 4 — Clone server + run with full live logs (recommended)

What this cell does:
- Clones the server repo.
- Installs server dependencies inside `cb311`.
- Runs `server.py` in the **foreground** and prints all logs live.
- Writes a full log file to: `/content/chatterbox_server_stdout.log`
- Prints a Colab proxy link when port 8004 is reachable; Colab will show it as `https://localhost:8004/` but it resolves to a `*.colab.*` URL that opens in a new tab. [web:146]
- Queries `/api/model-info` to confirm the model is loaded. [file:21]

```
# @title 4. Install Server + Run With Full Live Logs (foreground)
import os, time, subprocess, socket, requests
from pathlib import Path

PORT = 8004
REPO_DIR = "/content/Chatterbox-TTS-Server"
LOG_STDOUT = "/content/chatterbox_server_stdout.log"

def sh(cmd, check=False):
    return subprocess.run(["bash", "-lc", cmd], check=check)

def port_open(host="127.0.0.1", port=PORT, timeout=0.25):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

os.chdir("/content")

# Fresh clone
sh("rm -rf /content/Chatterbox-TTS-Server", check=False)
sh("git clone https://github.com/devnen/Chatterbox-TTS-Server.git", check=True)
os.chdir(REPO_DIR)

print("=== Quick system checks ===")
sh("nvidia-smi || true", check=False)

print("\n=== Installing server requirements (prefer repo pins if present) ===")
if Path("requirements-nvidia.txt").exists():
    sh("/content/bin/micromamba run -n cb311 pip install -U pip setuptools wheel", check=False)
    sh("/content/bin/micromamba run -n cb311 pip install -r requirements-nvidia.txt", check=False)
else:
    sh(
        "/content/bin/micromamba run -n cb311 pip install -U pip setuptools wheel && "
        "/content/bin/micromamba run -n cb311 pip install "
        "fastapi 'uvicorn[standard]' pyyaml soundfile librosa safetensors "
        "python-multipart requests jinja2 watchdog aiofiles unidecode inflect tqdm "
        "pydub audiotsm praat-parselmouth",
        check=False
    )

print("\n=== Removing old stdout log ===")
Path(LOG_STDOUT).unlink(missing_ok=True)

print("\n=== Starting server with LIVE logs ===")
print("Log file:", LOG_STDOUT)
print("To stop the server, run Cell 5.\n")

env = os.environ.copy()
env["PYTHONUNBUFFERED"] = "1"

# Put HF cache somewhere inspectable/persistent for this runtime
env["HF_HOME"] = "/content/hf_home"
env["TRANSFORMERS_CACHE"] = "/content/hf_home/transformers"
env["HF_HUB_CACHE"] = "/content/hf_home/hub"
Path(env["HF_HOME"]).mkdir(parents=True, exist_ok=True)

proc = subprocess.Popen(
    ["/content/bin/micromamba", "run", "-n", "cb311", "python", "-u", "server.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
    env=env,
)

with open(LOG_STDOUT, "w", encoding="utf-8", errors="replace") as f:
    shown_link = False
    while True:
        line = proc.stdout.readline()
        if line:
            print(line, end="")
            f.write(line)
            f.flush()

        if (not shown_link) and port_open():
            shown_link = True
            print("\n=== Server port is reachable ===")
            print("Click the Colab proxy link below to open the Web UI.")
            from google.colab.output import serve_kernel_port_as_window
            serve_kernel_port_as_window(PORT)

            # Verify model load status via server endpoint
            try:
                mi = requests.get(f"http://127.0.0.1:{PORT}/api/model-info", timeout=2).json()
                print("\n/api/model-info:", mi)
            except Exception as e:
                print("\n/api/model-info query failed:", repr(e))

        if proc.poll() is not None:
            print("\n=== Server process exited with code", proc.returncode, "===")
            break
```

**First run note:** model downloads can take a while; watch the progress output in Cell 4.

---

## Stopping / restarting (Cell 5)

### Cell 5 — Stop the server (free port 8004)

Run this any time you want to stop the server process and free the port.

```
%%bash
PORT=8004

echo "PIDs listening on port $PORT:"
sudo lsof -t -i:$PORT || true

echo "Killing..."
sudo kill -9 $(sudo lsof -t -i:$PORT) 2>/dev/null || true

echo "Verify nothing is listening:"
sudo lsof -i:$PORT || true
```

---

## What to run when…

### Start it the first time
Run: **Cell 1 → Cell 2 → Cell 3 → Cell 4** (in order, one-by-one).

### Stop the server
Run: **Cell 5**

### Start the server again (same runtime, nothing changed)
Run: **Cell 4**  
If you get “address already in use,” run **Cell 5** and then rerun **Cell 4**.

### After changing / updating packages
Run:
1) **Cell 5** (stop server)  
2) **Cell 2** (reinstall packages)  
3) **Cell 3** (verify install)  
4) **Cell 4** (start server)

---

## Troubleshooting

### Web UI opens but TTS doesn’t work
The server can be reachable even if the model didn’t load; always check `/api/model-info` (Cell 4 prints it) to confirm `loaded: True`. [file:21]

### “Token is required (`token=True`), but no token found”
Something in your installed Turbo code is still requesting `huggingface_hub` to read a local token (token=True semantics). [web:65]  
Fix: re-run **Cell 2** and then confirm **Cell 3** does not show any auth-forcing markers.

### “/content/bin/micromamba: No such file or directory”
You likely restarted the runtime or Cell 1 didn’t complete; rerun **Cell 1**.

### Where are model files cached?
During Cell 4, downloads are stored under `/content/hf_home` (set by `HF_HOME` in Cell 4). [web:65]

---

## Notes
- If Colab warns that `serve_kernel_port_as_window` might stop working, it still usually provides a working link; click the link that Colab prints (it looks like `https://localhost:8004/` but maps to a `*.colab.*` URL). [web:146]
- For bug reports, attach `/content/chatterbox_server_stdout.log` and the `/api/model-info` output. [file:21]
