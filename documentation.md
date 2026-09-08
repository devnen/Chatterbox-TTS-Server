# Chatterbox TTS Server - Technical Documentation

**Version:** 1.0.0
**Last Updated:** 5/31/2025
**Project Repository:** [https://github.com/devnen/Chatterbox-TTS-Server](https://github.com/devnen/Chatterbox-TTS-Server)

This server is based on the architecture and UI of our [Dia-TTS-Server](https://github.com/devnen/Dia-TTS-Server) project but uses the distinct `chatterbox-tts` engine.

## Table of Contents

1.  [Visual Overview](#1-visual-overview)
    *   [1.1 Directory Structure](#11-directory-structure)
    *   [1.2 Component Diagram](#12-component-diagram)
2.  [Introduction](#2-introduction)
    *   [2.1 Purpose](#21-purpose)
    *   [2.2 Core Engine: Chatterbox TTS](#22-core-engine-chatterbox-tts)
    *   [2.3 Key Server Features](#23-key-server-features)
    *   [2.4 Intended Audience](#24-intended-audience)
3.  [System Requirements](#3-system-requirements)
    *   [3.1 Operating Systems](#31-operating-systems)
    *   [3.2 Python Environment](#32-python-environment)
    *   [3.3 Hardware](#33-hardware)
        *   [3.3.1 CPU](#331-cpu)
        *   [3.3.2 GPU (Recommended)](#332-gpu-recommended)
        *   [3.3.3 Memory and Storage](#333-memory-and-storage)
    *   [3.4 Software Dependencies](#34-software-dependencies)
        *   [3.4.1 Python Packages](#341-python-packages)
        *   [3.4.2 System Libraries (Linux)](#342-system-libraries-linux)
4.  [Installation and Setup](#4-installation-and-setup)
    *   [4.1 Prerequisites Checklist](#41-prerequisites-checklist)
    *   [4.2 Cloning the Repository](#42-cloning-the-repository)
    *   [4.3 Python Virtual Environment Setup](#43-python-virtual-environment-setup)
        *   [4.3.1 Windows](#431-windows)
        *   [4.3.2 Linux/macOS](#432-linuxmacos)
    *   [4.4 Installing Dependencies](#44-installing-dependencies)
    *   [4.5 GPU Acceleration Setup (NVIDIA)](#45-gpu-acceleration-setup-nvidia)
        *   [4.5.1 NVIDIA Driver Installation](#451-nvidia-driver-installation)
        *   [4.5.2 PyTorch with CUDA Support](#452-pytorch-with-cuda-support)
        *   [4.5.3 Verification](#453-verification)
    *   [4.6 Initial Configuration (`config.yaml`)](#46-initial-configuration-configyaml)
5.  [Configuration (`config.yaml`)](#5-configuration-configyaml)
    *   [5.1 Overview](#51-overview)
    *   [5.2 File Location and Creation](#52-file-location-and-creation)
    *   [5.3 Main Configuration Sections and Parameters](#53-main-configuration-sections-and-parameters)
        *   [5.3.1 `server`](#531-server)
        *   [5.3.2 `model`](#532-model)
        *   [5.3.3 `tts_engine`](#533-tts_engine)
        *   [5.3.4 `paths`](#534-paths)
        *   [5.3.5 `generation_defaults`](#535-generation_defaults)
        *   [5.3.6 `audio_output`](#536-audio_output)
        *   [5.3.7 `ui_state`](#537-ui_state)
        *   [5.3.8 `ui`](#538-ui)
        *   [5.3.9 `debug`](#539-debug)
        *   [5.3.10 `audio_processing` (Conceptual)](#5310-audio_processing-conceptual)
    *   [5.4 Managing Configuration via Web UI](#54-managing-configuration-via-web-ui)
6.  [Running the Server](#6-running-the-server)
    *   [6.1 Starting the Server](#61-starting-the-server)
    *   [6.2 Model Downloading](#62-model-downloading)
    *   [6.3 Accessing the Web UI and API](#63-accessing-the-web-ui-and-api)
    *   [6.4 Stopping the Server](#64-stopping-the-server)
    *   [6.5 Running with Docker](#65-running-with-docker)
7.  [Feature Deep Dive](#7-feature-deep-dive)
    *   [7.1 Text Input](#71-text-input)
    *   [7.2 Large Text Processing (Chunking)](#72-large-text-processing-chunking)
    *   [7.3 Voice Cloning](#73-voice-cloning)
    *   [7.4 Predefined Voices](#74-predefined-voices)
    *   [7.5 Consistent Generation (Seeding)](#75-consistent-generation-seeding)
    *   [7.6 Audio Post-Processing](#76-audio-post-processing)
    *   [7.7 Model Management](#77-model-management)
8.  [Usage Guide](#8-usage-guide)
    *   [8.1 Web User Interface (Web UI)](#81-web-user-interface-web-ui)
        *   [8.1.1 Main Generation Form](#811-main-generation-form)
        *   [8.1.2 Text Splitting / Chunking Controls](#812-text-splitting--chunking-controls)
        *   [8.1.3 Voice Mode Selection](#813-voice-mode-selection)
        *   [8.1.4 Presets](#814-presets)
        *   [8.1.5 Generation Parameters](#815-generation-parameters)
        *   [8.1.6 Server Configuration (UI)](#816-server-configuration-ui)
        *   [8.1.7 Generated Audio Player](#817-generated-audio-player)
        *   [8.1.8 Theme Toggle](#818-theme-toggle)
        *   [8.1.9 Session Persistence](#819-session-persistence)
    *   [8.2 Application Programming Interface (API)](#82-application-programming-interface-api)
        *   [8.2.1 API Overview and Authentication](#821-api-overview-and-authentication)
        *   [8.2.2 POST `/v1/audio/speech` (OpenAI Compatible)](#822-post-v1audiospeech-openai-compatible)
        *   [8.2.3 POST `/tts` (Custom Parameters)](#823-post-tts-custom-parameters)
        *   [8.2.4 Helper Endpoints](#824-helper-endpoints)
9.  [Troubleshooting](#9-troubleshooting)
    *   [9.1 Common Issues and Solutions](#91-common-issues-and-solutions)
    *   [9.2 Log Files](#92-log-files)
10. [Project Architecture](#10-project-architecture)
    *   [10.1 Key Modules and Their Roles](#101-key-modules-and-their-roles)
    *   [10.2 Data Flow for TTS Generation](#102-data-flow-for-tts-generation)
11. [Testing (Conceptual)](#11-testing-conceptual)
12. [License and Disclaimer](#12-license-and-disclaimer)

---

## 1. Visual Overview

This section provides a high-level visual representation of the Chatterbox TTS Server project structure and its primary components.

### 1.1 Directory Structure

The following tree illustrates the organization of files and directories within the project root:

```
Chatterbox-TTS-Server/
│
├── config.py             # Manages config.yaml, default values, accessors
├── config.yaml           # PRIMARY configuration file (created/managed by server)
├── docker-compose.yml    # Docker Compose setup for containerized deployment
├── Dockerfile            # Docker image definition
├── documentation.md      # This comprehensive documentation file
├── download_model.py     # Utility to download specific model files to a local cache
├── engine.py             # Core model loading (from_pretrained) & generation logic
├── models.py             # Pydantic models for API request validation and structure
├── README.md             # Project summary and quick start guide
├── requirements.txt      # Python package dependencies
├── server.py             # Main FastAPI application, API endpoints, UI routes
│
├── ui/                   # Contains all files for the Web User Interface
│   ├── index.html        # Main HTML template for the UI
│   ├── presets.yaml      # Predefined examples for TTS generation, loaded by the UI
│   └── script.js         # Frontend JavaScript for UI interactivity and API communication
│
├── model_cache/          # Default directory for download_model.py script (Note: Not the runtime Hugging Face cache)
├── outputs/              # Default directory for audio files saved from UI or API
├── reference_audio/      # Default directory for user-uploaded reference audio files for voice cloning
└── voices/               # Default directory for predefined voice audio files
```

### 1.2 Component Diagram

This diagram illustrates the major functional components of the server and their interactions:

```
┌───────────────────┐      ┌───────────────────┐      ┌───────────────────────────┐      ┌───────────────────┐
│ User (Web UI /    │────→ │ FastAPI Server    │────→ │ TTS Engine (engine.py)    │────→ │ ChatterboxTTS     │
│ API Client)       │      │ (server.py)       │      │ (Handles Chunks/Params)   │      │ (from HF Hub)     │
└───────────────────┘      └─────────┬─────────┘      └──────┬─────────┬──────────┘      └─────────┬─────────┘
      ↑                            │                      │ Calls   │                            │ (Uses PyTorch)
      │ (Serves UI,               │ Uses                 │         │                            │
      │  API data)                ▼                      ▼         ▼                            │
      │                  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐      │
      └───────────────── │ Configuration     │ ←─ │ config.yaml     │  │ Utilities         │      │
                         │ (config.py)       │  └───────────────────┘  │ (utils.py)        │      │
                         └───────────────────┘                         │ - Chunking Logic  │      │
                                   ▲                                   │ - Audio Proc.     │      │
                                   │ Uses                              │ - File Handling   │      │
                                   │                                   └──────┬────────────┘      │
┌───────────────────┐      ┌───────────────────┐      ┌───────────────────┐      │                   │
│ Web UI Files      │ ←─── │ API Data / HTML   │      │ Audio Libraries   │←─────┘                   │
│ (ui/*)            │      │ (via server.py)   │      │ (soundfile, librosa)│                       ▼
└───────────────────┘      └───────────────────┘      └───────────────────┘                 ┌───────────────────┐
                                                                                              │ PyTorch / CUDA    │
                                                                                              └───────────────────┘
```

**Diagram Legend:**
*   Boxes represent major software components or groups of files.
*   Arrows (`→`) indicate the primary direction of data flow or control.
*   Lines with descriptive text (e.g., "Uses", "Calls") indicate dependencies or interactions.

---

## 2. Introduction

### 2.1 Purpose

The Chatterbox TTS Server is a self-hostable application designed to provide an accessible and feature-rich interface to the `chatterbox-tts` speech synthesis engine. It aims to simplify the process of generating high-quality speech by offering:
*   A user-friendly Web User Interface (Web UI) for interactive use.
*   A robust Application Programming Interface (API) for programmatic integration, including an OpenAI-compatible endpoint.
*   Advanced features such as voice cloning, predefined voices, large text handling through intelligent chunking, and fine-grained control over generation parameters.

### 2.2 Core Engine: Chatterbox TTS

The server uses the **`chatterbox-tts`** engine family developed by Resemble AI, via the `devnen/chatterbox-v2` fork. Three model variants are supported and hot-swappable at runtime through the Web UI engine dropdown (no restart required). The selected model is configured via `model.repo_id` in `config.yaml`.

**2.2.1 Original Chatterbox** (`model.repo_id: chatterbox`)

- 0.5B-parameter LLaMA-backed model trained on 0.5M hours of cleaned data.
- English only. High fidelity, strong voice cloning, supports `exaggeration` and `cfg_weight` parameters for emotion control.
- Best choice when English quality is the priority and multilingual is not needed.

**2.2.2 Chatterbox Turbo** (`model.repo_id: chatterbox-turbo`)

- 350M-parameter streamlined variant. Distills the speech-token-to-mel diffusion decoder from 10 steps to 1, removing a major inference bottleneck.
- Supports **paralinguistic tags** in the input text: `[laugh]`, `[cough]`, `[chuckle]`, plus text-based prompting for sigh / gasp / cough reactions.
- Ignores `exaggeration`, `cfg_weight`, and `min_p` parameters (the model API does not take them) — the server logs a warning when these are passed and proceeds with the supported subset.
- Best choice for real-time / agent workflows where latency matters more than absolute fidelity.

**2.2.3 Chatterbox Multilingual** (`model.repo_id: chatterbox-multilingual`)

- 0.5B-parameter variant trained on 23 languages: Arabic, Chinese, Danish, Dutch, English, Finnish, French, German, Greek, Hebrew, Hindi, Italian, Japanese, Korean, Malay, Norwegian, Polish, Portuguese, Russian, Spanish, Swahili, Swedish, Turkish.
- Zero-shot voice cloning across languages, plus emotion exaggeration.
- The `language` parameter on `/tts` selects the target language (ISO 639-1 code, e.g. `"de"`, `"ja"`). The Web UI populates the dropdown from `SUPPORTED_LANGUAGES` exposed by the loaded engine.
- Best choice for international content; trades some English-specific fidelity for broad language coverage.

**Important Note on Text Input:** The engine processes **plain text** plus the Turbo-only paralinguistic tags described above. It does **not** support speaker-differentiation tags like `[S1]` / `[S2]`. The synthesis is single-speaker, driven by the selected voice mode (predefined or cloned).

### 2.3 Key Server Features

*   **High-Quality Single-Speaker TTS:** Leverages the `chatterbox-tts` model.
*   **Voice Cloning:** Enables voice replication from user-provided audio samples.
*   **Predefined Voices:** Offers a library of ready-to-use voices for consistent output.
*   **Large Text Handling:** Implements intelligent chunking to process long plain text inputs without overwhelming the TTS engine.
*   **Flexible API:** Includes a custom `/tts` endpoint for full control and an OpenAI-compatible `/v1/audio/speech` endpoint for broader integration.
*   **Interactive Web UI:** Provides a comprehensive interface for generation, configuration, and audio management.
*   **Configuration Management:** Centralized settings via `config.yaml`, editable through the UI or directly.
*   **GPU Acceleration:** Supports NVIDIA CUDA and Apple MPS for faster inference, with CPU fallback.
*   **Optional Audio Post-Processing:** Features for silence trimming and audio cleanup.
*   **Docker Support:** Facilitates easy deployment and scaling.

### 2.4 Intended Audience

This documentation is intended for:
*   **End Users:** Individuals wishing to use the Web UI for generating speech.
*   **Developers:** Programmers looking to integrate TTS capabilities into their applications via the API.
*   **System Administrators:** Personnel responsible for deploying and maintaining the server.

---

## 3. System Requirements

Ensure your system meets the following requirements before proceeding with installation.

### 3.1 Operating Systems

*   **Windows:** Windows 10 (64-bit) or Windows 11 (64-bit).
*   **Linux:** Most modern distributions (Debian/Ubuntu and derivatives are well-tested).
*   **macOS:** While potentially runnable, macOS is not a primary test environment; GPU acceleration is typically limited to NVIDIA hardware.

### 3.2 Python Environment

*   **Python Version:** Python 3.10 or later is required.

### 3.3 Hardware

#### 3.3.1 CPU
*   A modern multi-core CPU is recommended for reasonable performance, especially if GPU acceleration is unavailable.

#### 3.3.2 GPU (Recommended)
*   **NVIDIA GPU:** For optimal performance, an NVIDIA GPU supporting CUDA is highly recommended.
    *   **Architecture:** Maxwell architecture or newer.
    *   **VRAM:** Specific VRAM requirements depend on the `chatterbox-tts` model variant, but generally, 6GB+ is advisable for smoother operation.
    *   See Section [4.5 GPU Acceleration Setup (NVIDIA)](#45-gpu-acceleration-setup-nvidia) for driver and toolkit details.
*   **Apple Silicon:** M1, M2, M3, or newer Apple Silicon chips with macOS 12.3+ provide excellent acceleration via Apple Metal Performance Shaders (MPS).

#### 3.3.3 Memory and Storage
*   **RAM:** Minimum 8 GB, 16 GB or more recommended.
*   **Storage:** Sufficient disk space for Python environment, dependencies, downloaded models (Hugging Face cache can grow to several GBs), and generated audio files.

### 3.4 Software Dependencies

#### 3.4.1 Python Packages
The server relies on several Python packages, managed via `requirements.txt`. Key dependencies include:
*   `chatterbox-tts`: The core text-to-speech engine.
*   `fastapi`: Web framework for building the API.
*   `uvicorn`: ASGI server for running FastAPI.
*   `torch` & `torchaudio`: For deep learning and audio operations.
*   `numpy`: Numerical operations.
*   `soundfile`: Reading and writing audio files.
*   `huggingface_hub`: Interacting with the Hugging Face Hub for model downloads.
*   `PyYAML`: For parsing `config.yaml` and `presets.yaml`.
*   `pydantic`: Data validation for API requests.
*   `librosa`: For advanced audio processing like resampling and speed adjustment.
*   `praat-parselmouth`: (Optional) For unvoiced segment removal feature.
*   `python-multipart`: For file uploads.
*   `Jinja2`: For HTML templating (though UI is primarily API-driven).

Refer to `requirements.txt` [1] for the complete list.

#### 3.4.2 System Libraries (Linux)
*   **`libsndfile1`**: Required by the `soundfile` Python package for audio file I/O.
    *   Installation (Debian/Ubuntu): `sudo apt install libsndfile1`
*   **`ffmpeg`**: Recommended for robust audio operations by some underlying libraries (e.g., `librosa` or `torchaudio` for certain formats).
    *   Installation (Debian/Ubuntu): `sudo apt install ffmpeg`

---

## 4. Installation and Setup

This section details the **manual / advanced** installation path. For most users, the recommended path is the automated launcher (`python start.py` on any OS, or `start.bat` / `start.sh`) documented in the main [README.md](README.md#-installation-and-setup), which covers Portable Mode on Windows and all six hardware paths (CPU, NVIDIA cu121 / cu128 / cu130, AMD ROCm, AMD Strix Halo, Apple MPS). The instructions below are kept for users who prefer to manage the venv and requirements directly.

### 4.1 Prerequisites Checklist

Before you begin, ensure you have:
1.  Met all [System Requirements](#3-system-requirements).
2.  Installed Python 3.10 or later.
3.  Installed Git.
4.  (If using GPU) Installed compatible NVIDIA drivers.

### 4.2 Cloning the Repository

1.  Open a terminal or command prompt.
2.  Navigate to the directory where you want to install the server.
3.  Clone the project repository from GitHub:
    ```bash
    git clone https://github.com/devnen/Chatterbox-TTS-Server.git
    ```
4.  Change into the project directory:
    ```bash
    cd Chatterbox-TTS-Server
    ```

### 4.3 Python Virtual Environment Setup

It is strongly recommended to use a Python virtual environment to isolate project dependencies.

#### 4.3.1 Windows
```powershell
# Ensure you are in the Chatterbox-TTS-Server directory
python -m venv venv
.\venv\Scripts\activate
# Your command prompt should now be prefixed with (venv).
```

#### 4.3.2 Linux/macOS
```bash
# Ensure you are in the Chatterbox-TTS-Server directory
python3 -m venv venv
source venv/bin/activate
# Your command prompt should now be prefixed with (venv).
```

### 4.4 Installing Dependencies

With the virtual environment activated:
1.  Upgrade `pip` to its latest version (recommended):
    ```bash
    pip install --upgrade pip
    ```
2.  Install all required Python packages from `requirements.txt` [1]:
    ```bash
    pip install -r requirements.txt
    ```
    **Note:** This step may take several minutes as it downloads and installs numerous packages, including large ones like `torch` and `chatterbox-tts`. By default, this may install a CPU-only version of PyTorch. If GPU support is desired, proceed to the next section.

### 4.5 GPU Acceleration Setup (NVIDIA)

Skip this section if you intend to run the server on CPU only.

#### 4.5.1 NVIDIA Driver Installation
*   Ensure you have the latest NVIDIA drivers installed for your operating system and GPU. You can download them from the [NVIDIA Driver Downloads page](https://www.nvidia.com/Download/index.aspx).
*   After installation or update, reboot your system if prompted.
*   Verify driver installation by running `nvidia-smi` in your terminal. This command should output information about your GPU and the highest CUDA version supported by the driver.

#### 4.5.2 PyTorch with CUDA Support
The `chatterbox-tts` engine and this server rely on PyTorch. To enable CUDA acceleration, you must install a version of PyTorch compiled with CUDA support.
1.  Visit the [Official PyTorch Get Started page](https://pytorch.org/get-started/locally/).
2.  Use the configuration tool on their website:
    *   **PyTorch Build:** Stable
    *   **Your OS:** Select your operating system (Linux or Windows).
    *   **Package:** Pip
    *   **Language:** Python
    *   **Compute Platform:** Select a CUDA version (e.g., CUDA 11.8, CUDA 12.1). **Crucially, choose a CUDA version that is compatible with (less than or equal to) the CUDA version reported by your `nvidia-smi` command.**
3.  The website will generate a `pip install` command. Copy this command.
4.  In your **activated virtual environment**, first uninstall any existing CPU-only PyTorch versions that might have been installed by `requirements.txt`:
    ```bash
    pip uninstall torch torchvision torchaudio -y
    ```
5.  Then, paste and run the command obtained from the PyTorch website. Example (for CUDA 12.1, **replace with your specific command**):
    ```bash
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
    ```

#### 4.5.3 Verification
To verify that PyTorch can utilize your GPU:
1.  In your activated virtual environment, start a Python interpreter: `python`
2.  Execute the following commands:
    ```python
    import torch
    print(f"PyTorch version: {torch.__version__}")
    cuda_available = torch.cuda.is_available()
    print(f"CUDA available: {cuda_available}")
    if cuda_available:
        print(f"Number of GPUs: {torch.cuda.device_count()}")
        print(f"Current GPU Name: {torch.cuda.get_device_name(torch.cuda.current_device())}")
    exit()
    ```
*   If `CUDA available:` prints `True`, your setup is correct. If `False`, revisit driver and PyTorch installation steps.

### 4.6 GPU Acceleration Setup (MPS)

For Apple Silicon Macs (M1, M2, M3, etc.), follow this specific installation sequence:

#### 4.6.1 Prerequisites
- macOS 12.3 or later for MPS support
- An Apple Silicon Mac (M1, M2, M3, or newer)

#### 4.6.2 Installation Steps

1. **Install PyTorch with MPS support first:**
   ```bash
   # With virtual environment activated
   pip install torch torchvision torchaudio
   ```

2. **Install chatterbox-tts without dependencies:**
   ```bash
   pip install --no-deps git+https://github.com/resemble-ai/chatterbox.git
   ```

3. **Install core server dependencies:**
   ```bash
   pip install fastapi 'uvicorn[standard]' librosa safetensors soundfile pydub audiotsm praat-parselmouth python-multipart requests aiofiles PyYAML watchdog unidecode inflect tqdm
   ```

4. **Install missing chatterbox dependencies:**
   ```bash
   pip install conformer==0.3.2 diffusers==0.29.0 resemble-perth==1.0.1 transformers==4.46.3
   ```

5. **Install remaining dependencies (if not already installed):**
   ```bash
   pip install --no-deps s3tokenizer
   pip install onnx==1.16.0
   ```

6. **Configure MPS device in config.yaml:**
   ```yaml
   tts_engine:
     device: mps  # Set to 'mps' instead of 'auto' or 'cuda'
   ```

#### 4.6.3 Verification
```bash
python -c "import torch; print(f'PyTorch version: {torch.__version__}'); print(f'MPS available: {torch.backends.mps.is_available()}')"
```

#### 4.6.4 Why This Process Is Necessary

Apple Silicon requires careful dependency management due to conflicts between the pinned PyTorch versions in chatterbox-tts requirements and the latest PyTorch versions that support MPS acceleration. This step-by-step process avoids version conflicts while ensuring MPS support.

### 4.7 Initial Configuration (`config.yaml`)

The server uses a `config.yaml` file for all its settings.
*   On the first run, if `config.yaml` is not found in the project root, the server will automatically create it using default values defined internally (see `config.py` [1]).
*   You can review and modify this `config.yaml` file after it's created or before the first run if you wish to customize settings like port numbers, paths, or default generation parameters. See Section [5. Configuration (`config.yaml`)](#5-configuration-configyaml) for details.

---

## 5. Configuration (`config.yaml`)

The Chatterbox TTS Server is configured primarily through a single YAML file, `config.yaml`, located in the root directory of the project.

### 5.1 Overview
`config.yaml` allows customization of various aspects of the server, including network settings, model parameters, file paths, TTS engine behavior, UI preferences, and default generation values. The server reads this file upon startup.

### 5.2 File Location and Creation
*   **Location:** The `config.yaml` file must reside in the project's root directory.
*   **Creation:** If `config.yaml` does not exist when the server starts, it will be automatically generated with a default set of configurations. These defaults are defined within `config.py` [1] (specifically in the `DEFAULT_CONFIG` dictionary).

### 5.3 Main Configuration Sections and Parameters

The following table describes the main sections and some key parameters you might find in `config.yaml`. For a complete list of all possible parameters and their default values, refer to the `DEFAULT_CONFIG` structure in `config.py` [1].

| Section               | Parameter                     | Type          | Description                                                                                                   | Default (Example)        |
| :-------------------- | :---------------------------- | :------------ | :------------------------------------------------------------------------------------------------------------ | :----------------------- |
| **`server`**          | `host`                        | string        | IP address the server listens on. `0.0.0.0` for all available interfaces.                                     | `0.0.0.0`                |
|                       | `port`                        | integer       | Port number for the server.                                                                                   | `8000`                   |
|                       | `log_file_path`               | string        | Path to the server log file (relative to project root or absolute).                                           | `logs/tts_server.log`    |
|                       | `log_file_max_size_mb`        | integer       | Maximum size of a single log file before rotation.                                                            | `10`                     |
|                       | `log_file_backup_count`       | integer       | Number of backup log files to keep.                                                                           | `5`                      |
|                       | `ssl_certfile`                | string/null   | Path to SSL certificate file for HTTPS. Leave `null` to serve plain HTTP.                                     | `null`                   |
|                       | `ssl_keyfile`                 | string/null   | Path to SSL private key file. Must be set together with `ssl_certfile`.                                       | `null`                   |
| **`model`**           | `repo_id`                     | string        | Selects the engine: `chatterbox` / `original`, `chatterbox-turbo` / `turbo`, or `chatterbox-multilingual` / `multilingual`. Hot-swappable from the UI. | `chatterbox-turbo`       |
| **`tts_engine`**      | `device`                      | string        | TTS processing device: `auto`, `cuda`, `mps`, or `cpu`. `auto` attempts CUDA, then MPS, falls back to CPU.     | `auto`                   |
|                       | `predefined_voices_path`      | string        | Directory for predefined voice audio files.                                                                   | `voices`                 |
|                       | `reference_audio_path`        | string        | Directory for user-uploaded reference audio files for voice cloning.                                          | `reference_audio`        |
|                       | `default_voice_id`            | string        | Filename of the default predefined voice to use if none selected (primarily for UI).                            | `default_sample.wav`     |
|                       | `voice_cache_size`            | integer       | Max distinct voices whose encoded conditionals are cached (LRU, stored on CPU). `0` disables caching.           | `8`                      |
| **`paths`**           | `model_cache`                 | string        | Directory for caching models downloaded by `download_model.py`. **Note:** Runtime uses global HF cache.         | `./model_cache`          |
|                       | `output`                      | string        | Default directory for audio files saved from the UI or API.                                                   | `./outputs`              |
| **`generation_defaults`**| `temperature`                | float         | Controls randomness (0.0-1.5). Lower is more deterministic.                                                   | `0.8`                    |
|                       | `exaggeration`                | float         | Controls expressiveness (0.0-2.0).                                                                            | `0.5`                    |
|                       | `cfg_weight`                  | float         | Classifier-Free Guidance weight (0.0-2.0). Influences adherence to style.                                     | `0.5`                    |
|                       | `seed`                        | integer       | Random seed for generation. `0` often means random/engine default.                                            | `0`                      |
|                       | `speed_factor`                | float         | Playback speed factor (0.25-4.0). `1.0` is normal.                                                            | `1.0`                    |
|                       | `language`                    | string        | Default language code (e.g., `en`). Primarily for UI, engine may infer.                                       | `en`                     |
| **`audio_output`**    | `format`                      | string        | Default output audio format (e.g., `wav`, `opus`).                                                            | `wav`                    |
|                       | `sample_rate`                 | integer       | Target sample rate for output audio files (e.g., `24000`, `48000`). Resampling applied if needed.              | `24000`                  |
|                       | `max_reference_duration_sec`  | integer       | Maximum duration for reference audio files for cloning.                                                       | `30`                     |
| **`ui_state`**        | `last_text`                   | string        | Last text entered in the UI.                                                                                  | `""`                     |
|                       | `last_voice_mode`             | string        | Last selected voice mode (`predefined` or `clone`).                                                           | `predefined`             |
|                       | `last_predefined_voice`       | string/null   | Filename of the last used predefined voice.                                                                   | `null`                   |
|                       | `last_reference_file`         | string/null   | Filename of the last used reference audio.                                                                    | `null`                   |
|                       | `last_seed`                   | integer       | Last used generation seed in UI.                                                                              | `0`                      |
|                       | `last_chunk_size`             | integer       | Last used chunk size in UI.                                                                                   | `120`                    |
|                       | `last_split_text_enabled`     | boolean       | Whether text splitting was last enabled in UI.                                                                | `true`                   |
|                       | `hide_chunk_warning`          | boolean       | Flag to hide the chunking warning modal.                                                                      | `false`                  |
|                       | `hide_generation_warning`     | boolean       | Flag to hide the general generation quality notice modal.                                                     | `false`                  |
|                       | `theme`                       | string        | Default UI theme (`dark` or `light`).                                                                         | `dark`                   |
| **`ui`**              | `title`                       | string        | Title displayed in the web UI.                                                                                | `Chatterbox TTS Server`  |
|                       | `show_language_select`        | boolean       | Whether to show language selection in the UI.                                                                 | `true`                   |
|                       | `max_predefined_voices_in_dropdown`| integer  | Max predefined voices to list in UI dropdown before it might become less usable.                            | `20`                     |
| **`debug`**           | `save_intermediate_audio`     | boolean       | If true, save intermediate audio files during chunk processing for debugging.                                 | `false`                  |

**Note:** Paths can be specified relative to the project root or as absolute paths.

**Performance environment variable (not in `config.yaml`):**

- `TTS_BF16` — controls whether the T3 model is converted to bfloat16 and run under autocast.
  - `off` (default) — keep T3 in float32, no autocast. Preserves pre-v2.0 behavior on upgrade.
  - `on` / `1` / `true` — force-enable. Assumes the hardware supports bf16.
  - `auto` — enable only if `torch.cuda.is_bf16_supported()` reports `True` at runtime.
  - Typical speedup on bf16-capable GPUs (RTX 30/40/50, A100, H100, Strix Halo) is around 40% on T3 token generation. Output is numerically slightly different from float32 but typically inaudible.

#### 5.3.10 `audio_processing` (Conceptual)
While not explicitly a top-level section in the provided `config.py`'s `DEFAULT_CONFIG`, flags for enabling audio post-processing features (like silence trimming) are typically boolean values. They might be under `debug` or a dedicated `audio_processing` section if you choose to group them. Example:
```yaml
# audio_processing: # Or under debug:
#   enable_silence_trimming: true
#   enable_internal_silence_fix: true
#   enable_unvoiced_removal: false # Requires parselmouth
```
The server logic in `server.py` and `utils.py` would then check these flags from `config_manager`.

### 5.4 Managing Configuration via Web UI
The Web UI provides sections to manage parts of `config.yaml`:
*   **Generation Parameters:** Sliders and inputs for parameters like temperature, seed, etc., reflect values from `generation_defaults`. Clicking "Save Generation Parameters" updates this section in `config.yaml`.
*   **Server Configuration:** Allows viewing and, for some fields, editing settings related to `server`, `tts_engine`, and `paths`. Clicking "Save Server Configuration" updates `config.yaml`. **Remember that changes to server host/port, model settings, or fundamental paths require a server restart to take effect.**
*   **UI State:** Settings like last entered text, selected voice mode, chosen files, chunking toggle/size, and theme preference are automatically saved to the `ui_state` section in `config.yaml` (typically with a debounce mechanism) as you interact with the UI.

---

## 6. Running the Server

### 6.1 Starting the Server
1.  Ensure your Python virtual environment is activated (see Section [4.3 Python Virtual Environment Setup](#43-python-virtual-environment-setup)).
2.  Navigate to the root directory of the `Chatterbox-TTS-Server` project in your terminal.
3.  Execute the following command:
    ```bash
    python server.py
    ```
    The server will start, and you will see log output in the terminal, including the address and port it's running on.

### 6.2 Model Downloading
*   **Automatic Download (Runtime):** The first time you run the server (or if the model is not found in the cache), the `engine.py` module, specifically `ChatterboxTTS.from_pretrained()`, will attempt to download the `chatterbox-tts` model from the Hugging Face Hub (specified by `model.repo_id` in `config.yaml`). This download occurs to the standard Hugging Face cache directory (e.g., `~/.cache/huggingface/hub` on Linux/macOS, or `%USERPROFILE%\.cache\huggingface\hub` on Windows, or as defined by `HF_HOME` environment variable). This process can take some time depending on your internet connection and model size. The server will fully start after the model is successfully loaded.
*   **Optional Pre-download Script (`download_model.py` [1]):** The project includes a `download_model.py` script. This script downloads specific model files (listed in its `CHATTERBOX_MODEL_FILES` array) into the local directory specified by `paths.model_cache` in `config.yaml` (default: `./model_cache/`).
    *   **Important Distinction:** The `engine.py` at runtime **does not** load models from this `paths.model_cache` directory. It uses the global Hugging Face cache. The `download_model.py` script is a utility for users who might want to create a local, self-contained copy of model components, perhaps for offline use or custom model management, but it's not part of the default runtime model loading path.

### 6.3 Accessing the Web UI and API
*   **Web UI:** Once the server is running, open your web browser and navigate to the address shown in the startup logs, typically `http://localhost:PORT` (e.g., `http://localhost:8000` if `server.port` is 8000). The server attempts to open this automatically.
*   **API Documentation (Swagger UI):** Interactive API documentation is available at `http://localhost:PORT/docs`.

### 6.4 Stopping the Server
*   To stop the server, press `CTRL+C` in the terminal window where it is running.

### 6.5 Running with Docker
For containerized deployment, refer to the `Dockerfile` [1] and `docker-compose.yml` [1] files in the project root, and the Docker instructions in the [README.md](README.md) file. Docker provides an isolated environment and simplifies dependency management.

---

## 7. Feature Deep Dive

This section elaborates on key features of the Chatterbox TTS Server.

### 7.1 Text Input

The Chatterbox TTS Server expects **plain text** as input for speech synthesis.
*   Standard punctuation (periods, commas, question marks, exclamation marks) is generally recognized by the underlying TTS engine to influence prosody.
*   The server and the `chatterbox-tts` engine do **not** support special tags for:
    *   Speaker differentiation (e.g., `[S1]`, `[S2]`). All generated speech will be in a single voice per request, determined by the selected voice mode.
    *   Explicit emotional control (e.g., `(emotion:sad)`).
    *   Other complex control commands embedded in the text.
*   Any text provided will be synthesized as is, including any characters or symbols that might resemble tags from other systems.

### 7.2 Large Text Processing (Chunking)

To handle long plain text inputs that might exceed the processing capacity of the TTS engine or lead to overly long audio files, the server implements an intelligent chunking mechanism.
*   **Process:** Enabled by default (can be toggled in UI/API). When active, `utils.py` [1] first splits the input text into sentences using `split_into_sentences()`. Then, `chunk_text_by_sentences()` groups these sentences into chunks, respecting a maximum character `chunk_size` (configurable).
*   **Benefits:** Ensures stable generation for long documents, better resource management, and more manageable audio segments.
*   **Configuration:**
    *   UI: "Split text into chunks" checkbox and "Chunk Size" slider.
    *   API (`/tts`): `split_text` (boolean) and `chunk_size` (integer) parameters.
*   See Section [3. Large Text Processing & Chunking](#3-large-text-processing--chunking) for a detailed explanation.

### 7.3 Voice Cloning

The server allows generating speech in a voice cloned from a reference audio sample.
*   **Mechanism:** The user provides a reference audio file (`.wav` or `.mp3`). The path to this file is passed to the `chatterbox-tts` engine, which uses it as an `audio_prompt` to condition the synthesis.
*   **Reference Audio:**
    *   Files are uploaded to or placed in the directory specified by `tts_engine.reference_audio_path` (default: `./reference_audio/`) [1].
    *   Quality of the reference audio (clear speech, minimal noise) significantly impacts clone quality.
    *   Duration is also a factor; refer to `audio_output.max_reference_duration_sec` in `config.yaml`.
*   **Usage:**
    *   UI: Select "Voice Clone" mode, choose a reference file.
    *   API (`/tts`): Set `voice_mode` to `clone` and provide `reference_audio_filename`.
*   See Section [4. Voice Cloning: Replicating Voices with Reference Audio](#4-voice-cloning-replicating-voices-with-reference-audio) for more details.

### 7.4 Predefined Voices

For ease of use and consistent voice output, the server supports predefined voices.
*   **Mechanism:** A collection of curated voice samples (audio files) are stored on the server. When a predefined voice is selected, its audio file is used as the `audio_prompt` for the `chatterbox-tts` engine.
*   **Voice Files:**
    *   Stored in the directory specified by `tts_engine.predefined_voices_path` (default: `./voices/`) [1].
    *   Supported formats: `.wav`, `.mp3`.
*   **Usage:**
    *   UI: Select "Predefined Voices" mode, choose a voice from the dropdown.
    *   API (`/tts`): Set `voice_mode` to `predefined` and provide `predefined_voice_id` (the filename).
*   See Section [5. Predefined Voices: Consistent Synthetic Voices](#5-predefined-voices-consistent-synthetic-voices) for more details.

### 7.5 Consistent Generation (Seeding)

To achieve reproducible audio output, particularly when experimenting or generating multiple parts of a longer text, a generation seed can be used.
*   **Mechanism:** The `seed` parameter (an integer) initializes the random number generators within the TTS engine.
*   **Effect:** Using the same seed, input text, voice, and other generation parameters will typically produce identical or very similar audio output. This is useful for maintaining voice consistency across chunks if not using a specific cloned or predefined voice.
*   **Usage:**
    *   UI: "Generation Seed" input field.
    *   API (`/tts` and `/v1/audio/speech`): `seed` parameter.
*   See Section [6. Consistent Generation (Seeding)](#6-consistent-generation-seeding) for more details.

### 7.6 Audio Post-Processing

The server includes optional audio post-processing steps handled by `utils.py` [1] to enhance the quality of the generated audio. These are applied if their respective flags are enabled in `config.yaml` (e.g., under a conceptual `audio_processing` section or individual debug flags).
*   **Silence Trimming (`trim_lead_trail_silence`):** Removes excessive silence from the beginning and end of audio segments.
*   **Internal Silence Reduction (`fix_internal_silence`):** Shortens unnaturally long pauses within the speech.
*   **Unvoiced Segment Removal (`remove_long_unvoiced_segments`):** If `praat-parselmouth` is installed, this can remove long segments of audio that contain no voiced speech (e.g., long breaths).
*   **Speed Adjustment (`apply_speed_factor`):** Modifies the playback speed of the audio. Uses `librosa` for pitch-preserving adjustment if available.

### 7.7 Model Management

*   **Runtime Model Loading:** The `engine.py` [1] module loads the `chatterbox-tts` model using `ChatterboxTTS.from_pretrained(repo_id=..., device=...)`. This method downloads the model from the specified Hugging Face repository (defined in `config.yaml` via `model.repo_id`) into the standard Hugging Face local cache if it's not already present. This is the primary mechanism for model access during server operation.
*   **Hugging Face Cache:** The default location for this cache is platform-dependent (e.g., `~/.cache/huggingface/hub`). It can be overridden by setting the `HF_HOME` environment variable.
*   **`download_model.py` Script:** This utility script [1] allows users to download specific model files (listed in its internal `CHATTERBOX_MODEL_FILES` array) to a custom local directory defined by `paths.model_cache` in `config.yaml`. This is for users who might want a separate, managed local copy of model assets, but it's **not** the directory the server's `engine.py` uses for runtime loading.
*   **Configuration:** The `model.repo_id` in `config.yaml` specifies the default Hugging Face repository to load from.

---

## 8. Usage Guide

This section explains how to use the Chatterbox TTS Server through its Web UI and API.

### 8.1 Web User Interface (Web UI)

The Web UI provides an interactive way to generate speech and manage server settings. Access it by navigating to the server's root URL (e.g., `http://localhost:8000`).

#### 8.1.1 Main Generation Form
*   **Text to synthesize:** A large text area for inputting the plain text you want to convert to speech. Character count is displayed.
*   **Generate Speech Button:** Initiates the TTS process using the current settings.

#### 8.1.2 Text Splitting / Chunking Controls
*   Located below the main text input area.
*   **"Split text into chunks" Checkbox:** Toggles the automatic text chunking feature (see Section [7.2 Large Text Processing (Chunking)](#72-large-text-processing-chunking)). Enabled by default.
*   **"Chunk Size" Slider:** Appears when splitting is enabled. Allows adjusting the target character length for chunks (default 120). The current value is displayed next to the slider.

#### 8.1.3 Voice Mode Selection
Radio buttons allow choosing the voice generation method:
*   **Predefined Voices:** Activates the dropdown to select from available predefined voices (see Section [7.4 Predefined Voices](#74-predefined-voices)). Includes an "Import" button to upload new predefined voice files and a "Refresh" button to reload the list from the server.
*   **Voice Cloning:** Activates the dropdown to select a reference audio file for voice cloning (see Section [7.3 Voice Cloning](#73-voice-cloning)). Includes an "Import" button to upload new reference files and a "Refresh" button.

#### 8.1.4 Presets
*   A section displaying buttons for predefined text and parameter examples, loaded from `ui/presets.yaml` [1]. Clicking a preset button populates the text area and relevant generation parameters.

#### 8.1.5 Generation Parameters
An expandable section allows fine-tuning of TTS generation:
*   **Temperature:** Slider controlling output randomness.
*   **Exaggeration:** Slider controlling speech expressiveness.
*   **CFG Weight:** Slider for Classifier-Free Guidance weight.
*   **Speed Factor:** Slider to adjust playback speed. A warning may appear if set to values other than 1.0, as it can affect quality.
*   **Generation Seed:** Input field for an integer seed.
*   **Language:** Dropdown for selecting language (primarily for UI state, engine may infer).
*   **"Save Generation Parameters" Button:** Saves the current slider/input values as new defaults in the `generation_defaults` section of `config.yaml`.

#### 8.1.6 Server Configuration (UI)
An expandable section that displays current server configuration values loaded from `config.yaml` via an API call.
*   Fields like server host/port, TTS device, model paths, audio output settings are shown.
*   Some fields may be editable here, though changes to critical settings like paths or port numbers require a server restart to take effect.
*   **"Save Server Configuration" Button:** Attempts to save changes made in editable fields back to `config.yaml`. A restart prompt may appear.
*   **"Restart Server" Button:** (May appear after saving certain settings) Logs a request to restart the server.

#### 8.1.7 Generated Audio Player
*   Appears below the main form after successful audio generation.
*   Uses **WaveSurfer.js** to display an interactive waveform.
*   Includes Play/Pause button, a Download link for the generated audio file (WAV or Opus), and information about the generation (voice mode, file used, generation time, audio duration).

#### 8.1.8 Theme Toggle
*   A button (usually in the navigation bar) to switch between light and dark UI themes. The preference is saved in the browser's local storage and also synced to `ui_state.theme` in `config.yaml`.

#### 8.1.9 Session Persistence
*   The UI attempts to save the last used text, voice mode, selected files, generation parameter values, chunking settings, and theme choice to the `ui_state` section in `config.yaml`. These settings are reloaded when the page is next visited.

### 8.2 Application Programming Interface (API)

The server exposes RESTful API endpoints for programmatic interaction. Interactive documentation (Swagger UI) is available at the `/docs` path.

#### 8.2.1 API Overview and Authentication
*   The API is served by FastAPI.
*   Currently, the API endpoints do not implement authentication by default (this can be added if needed by modifying `server.py`).

#### 8.2.2 POST `/v1/audio/speech` (OpenAI Compatible)

This endpoint is designed to be compatible with the basic OpenAI TTS API structure, facilitating integration with tools expecting this format.

*   **Request Body:** JSON, expected to follow a structure similar to `OpenAITTSRequest`.
    | Field             | Type    | Required | Description                                                                                                                                                              | Default (Server-Side) |
    | :---------------- | :------ | :------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------- |
    | `model`           | string  | No       | Model identifier. Often ignored by self-hosted servers as they use a fixed engine. Can be included for compatibility.                                                    | `chatterbox` (example) |
    | `input`           | string  | Yes      | The plain text to be synthesized.                                                                                                                                        |                       |
    | `voice`           | string  | No       | Specifies the voice. This would map to either a predefined voice filename (e.g., `"default_sample.wav"`) or a reference audio filename for cloning (e.g., `"my_clone.mp3"`). | Engine default/config |
    | `response_format` | string  | No       | Desired audio output format. Supported: `"wav"`, `"opus"`.                                                                                                               | `"wav"` (from config) |
    | `speed`           | float   | No       | Playback speed factor (e.g., 0.5 to 2.0). Applied post-generation.                                                                                                       | `1.0`                 |
    | `seed`            | integer | No       | Generation seed for reproducibility. `0` or absent might use default engine randomness.                                                                                  | `0` (from config)     |

*   **Processing Logic (Hypothetical for Chatterbox Server):**
    *   The server would parse the `voice` parameter. It would need to check if the `voice` string matches a filename in the `predefined_voices_path` or `reference_audio_path` to determine if it's a predefined voice or a clone request.
    *   If `voice` corresponds to a predefined voice, `voice_mode="predefined"` and `predefined_voice_id` would be set internally.
    *   If `voice` corresponds to a reference audio, `voice_mode="clone"` and `reference_audio_filename` would be set internally.
    *   The `input` text is processed. Chunking is typically applied with default server settings.
    *   Generation parameters like temperature, exaggeration, cfg_weight would use server defaults from `config.yaml` as they are not standard OpenAI API fields.
    *   The `speed` and `seed` parameters, if provided, would be used.
*   **Response:**
    *   **Success (200 OK):** `StreamingResponse` containing binary audio data (media type `audio/wav` or `audio/opus`).
    *   **Error:** Standard FastAPI JSON error response (e.g., 400, 404, 500).

#### 8.2.3 POST `/tts` (Custom Parameters)

This is the primary and most flexible endpoint for TTS generation, offering full control over all available parameters.

*   **Request Body (`CustomTTSRequest` from `models.py` [1]):**
    | Field                       | Type                             | Required    | Description                                                                                                   | Default (from `config.yaml` if not provided) |
    | :-------------------------- | :------------------------------- | :---------- | :------------------------------------------------------------------------------------------------------------ | :------------------------------------------- |
    | `text`                      | string                           | **Yes**     | Plain text to be synthesized.                                                                                 |                                              |
    | `voice_mode`                | `"predefined"` \| `"clone"`      | No          | Specifies the voice generation mode.                                                                          | `"predefined"`                               |
    | `predefined_voice_id`       | string \| null                   | Conditional | Filename of the voice from `voices/`. Required if `voice_mode` is `predefined`.                             | `tts_engine.default_voice_id`                |
    | `reference_audio_filename`  | string \| null                   | Conditional | Filename of the audio from `reference_audio/`. Required if `voice_mode` is `clone`.                           | `null`                                       |
    | `output_format`             | `"wav"` \| `"mp3"` \| `"opus"`   | No          | Desired audio output format. Ignored when `stream=true` (streaming always uses WAV).                          | `audio_output.format`                        |
    | `stream`                    | boolean                          | No          | If true, returns a `StreamingResponse` that flushes WAV bytes as each chunk is synthesized. Chunk-level streaming only — see note below. | `false`                          |
    | `split_text`                | boolean \| null                  | No          | Enable/disable automatic text chunking.                                                                       | `true`                                       |
    | `chunk_size`                | integer \| null                  | No          | Approximate target character length for chunks (50-500 recommended).                                          | `120`                                        |
    | `temperature`               | float \| null                    | No          | Overrides default temperature.                                                                                | `generation_defaults.temperature`            |
    | `exaggeration`              | float \| null                    | No          | Overrides default exaggeration.                                                                               | `generation_defaults.exaggeration`           |
    | `cfg_weight`                | float \| null                    | No          | Overrides default CFG weight.                                                                                 | `generation_defaults.cfg_weight`             |
    | `seed`                      | integer \| null                  | No          | Overrides default seed.                                                                                       | `generation_defaults.seed`                   |
    | `speed_factor`              | float \| null                    | No          | Overrides default speed factor.                                                                               | `generation_defaults.speed_factor`           |
    | `language`                  | string \| null                   | No          | Overrides default language.                                                                                   | `generation_defaults.language`               |

*   **Response:**
    *   **Success (200 OK):** `StreamingResponse` containing binary audio data (media type `audio/wav`, `audio/mpeg`, or `audio/opus`) with appropriate `Content-Disposition` headers for download.
    *   **Error:** Standard FastAPI JSON error response (e.g., 400 for bad input or path traversal in voice parameters, 404 for missing voice file, 500 for server error, 503 if model not loaded).

*   **Streaming caveat:** the Chatterbox engine synthesizes a full chunk of audio in one forward pass; there is no token-by-token streaming inside a chunk. With `stream: true` the server flushes each chunk's WAV bytes to the client as soon as that chunk completes (with 20 ms crossfades stitched between chunks). This means streaming gives **no benefit for short inputs** (1 chunk = client waits for full synthesis before any audio plays), but for long-form input (audiobooks, multi-paragraph content) the client can start playback as soon as chunk 1 is ready while later chunks render in the background.

#### 8.2.4 Helper Endpoints
These endpoints are primarily used by the Web UI to populate dynamic content and manage settings.
*   **`GET /api/ui/initial-data`**:
    *   Returns a JSON object containing the full server configuration (stringified paths), lists of available reference files and predefined voices, and UI presets. Crucial for UI initialization.
*   **`POST /save_settings`**:
    *   Accepts a partial JSON representation of the configuration. Merges these changes into the current `config.yaml` and saves it.
    *   Response: `UpdateStatusResponse` [1] indicating success/failure and if a restart is needed.
*   **`POST /reset_settings`**:
    *   Resets the `config.yaml` file to its hardcoded defaults (from `config.py` [1]).
    *   Response: `UpdateStatusResponse` [1].
*   **`POST /restart_server`**:
    *   Logs a request to restart the server. Actual restart depends on the deployment environment (e.g., process manager, Docker).
    *   Response: `UpdateStatusResponse` [1].
*   **`GET /get_reference_files`**:
    *   Returns a JSON list of filenames available in the `reference_audio` directory.
*   **`GET /get_predefined_voices`**:
    *   Returns a JSON list of dictionaries, each with `display_name` and `filename` for voices in the `voices` directory.
*   **`POST /upload_reference`**:
    *   Endpoint for uploading reference audio files. Expects `multipart/form-data`.
    *   Validates and saves files to `reference_audio_path`.
    *   Response: JSON detailing uploaded files, any errors, and the updated list of all reference files.
*   **`POST /upload_predefined_voice`**:
    *   Endpoint for uploading predefined voice audio files. Expects `multipart/form-data`.
    *   Validates and saves files to `predefined_voices_path`.
    *   Response: JSON detailing uploaded files, any errors, and the updated list of all predefined voices.
*   **`GET /api/model-info`**:
    *   Returns the currently-loaded model's status, type (`original` / `turbo` / `multilingual`), device, BF16 state, and the `SUPPORTED_LANGUAGES` map when the multilingual engine is active.
*   **`POST /api/unload`**:
    *   Releases the loaded model from GPU/CPU memory and clears the voice conditioning cache without restarting the server. Useful when switching engines or freeing VRAM for other workloads. The next `/tts` or `/v1/audio/speech` request triggers a fresh model load.
*   **`GET /v1/audio/voices`**:
    *   OpenAI-compatible voice listing endpoint. Accepts an optional `model` query parameter for compatibility but does not gate the response on it. Returns the same predefined-voice list as `GET /get_predefined_voices` in OpenAI's `{ "voices": [...] }` shape.

#### 8.2.5 Security: path traversal protection

The `predefined_voice_id`, `reference_audio_filename` fields on `/tts` and the `voice` field on `/v1/audio/speech` are sandboxed under their configured directories (`tts_engine.predefined_voices_path` and `tts_engine.reference_audio_path` respectively) using `utils.safe_resolve_within()`. Traversal attempts (`..`, absolute paths, symlinks pointing outside the sandbox) return **HTTP 400** with no filesystem access. The fix addresses CWE-22 and shipped in v2.0.0.

---

## 9. Troubleshooting

This section provides guidance on common issues encountered with the Chatterbox TTS Server.

### 9.1 Common Issues and Solutions

| Issue                                         | Possible Cause(s)                                                                                                | Suggested Solution(s)                                                                                                                                                                                             |
| :-------------------------------------------- | :--------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Server Fails to Start**                     | Port conflict; Python environment issues; missing critical dependencies; `config.yaml` corruption.                 | Check terminal logs for specific error messages. Ensure selected port is free. Verify virtual environment activation and `pip install -r requirements.txt`. Delete `config.yaml` to regenerate on next start.       |
| **Apple Silicon (MPS) Not Available**          | macOS version too old; non-Apple Silicon Mac; incorrect PyTorch version; device not configured properly.           | Ensure macOS 12.3+, Apple Silicon Mac (M1/M2/M3+). Install PyTorch first: `pip install torch torchvision torchaudio`. Set `device: mps` in `config.yaml`. Verify: `python -c "import torch; print(torch.backends.mps.is_available())"`|
| **Apple Silicon Installation Conflicts**       | Version conflicts between PyTorch and chatterbox-tts dependencies; ONNX build failures.                           | Follow exact Apple Silicon installation sequence in Section 4.5.1. Install PyTorch first, then use `--no-deps` for chatterbox-tts. Use `pip install onnx==1.16.0` for compatible ONNX version.                    |
| **"CUDA not available" or Slow Performance**  | NVIDIA drivers not installed/updated; incorrect PyTorch (CUDA) version; GPU not selected/available.                | Follow Section [4.5 GPU Acceleration Setup (NVIDIA)](#45-gpu-acceleration-setup-nvidia). Set `tts_engine.device` to `cuda` in `config.yaml`. Check `nvidia-smi`.                                                    |
| **VRAM Out of Memory (OOM) Errors**           | GPU has insufficient VRAM for the model; other applications consuming GPU memory.                                  | Ensure GPU meets minimum requirements. Close other GPU-heavy applications. If problem persists, consider a GPU with more VRAM. For very long texts, ensure chunking is active and `chunk_size` is reasonable.    |
| **Model Download Fails**                      | Internet connectivity issues; Hugging Face Hub issues; incorrect `model.repo_id` in `config.yaml`; cache problems. | Check internet connection. Verify `model.repo_id`. Try clearing Hugging Face cache (`HF_HOME` or default location).                                                                                                   |
| **Voice Cloning Poor Quality/Fails**          | Poor quality reference audio (noise, reverb); reference audio too short/long; incorrect file format.               | Use clean, clear reference audio (5-20 seconds typical). Ensure `.wav` or `.mp3` format. Check `audio_output.max_reference_duration_sec`. Experiment with generation parameters.                                   |
| **Predefined Voice Not Found**                | Voice file missing from `voices/` directory; incorrect filename in UI/API.                                       | Verify file exists in the path specified by `tts_engine.predefined_voices_path`. Ensure correct filename is used. Use "Refresh" button in UI.                                                                    |
| **Audio Output Issues (No sound, distorted)** | Incorrect audio processing settings; sample rate mismatch; TTS engine error.                                     | Check `audio_output.sample_rate` and `audio_output.format` in `config.yaml`. Review server logs for synthesis errors. Try simpler text or different voice. Disable optional audio post-processing features to isolate. |
| **UI Not Loading or Behaving Erratically**    | JavaScript errors; browser cache issues; API connectivity problems.                                              | Clear browser cache and cookies. Check browser's developer console (F12) for errors. Ensure server is running and accessible.                                                                                      |
| **Configuration Changes Not Taking Effect**   | Server not restarted after critical changes (host, port, paths, model settings).                                   | Restart the server application after modifying these types of settings in `config.yaml`.                                                                                                                            |
| **File Upload Failures**                      | Incorrect file type; file too large (if server imposes limits); permissions issues on server.                    | Ensure uploading supported formats (`.wav`, `.mp3`). Check server logs for detailed error. Verify write permissions for `reference_audio/` and `voices/` directories.                                            |

### 9.2 Log Files
*   The primary server log file is specified by `server.log_file_path` in `config.yaml` (default: `logs/tts_server.log` [1]).
*   Logs are rotated based on `log_file_max_size_mb` and `log_file_backup_count`.
*   Review these logs for detailed error messages and operational information. Standard output in the terminal also provides real-time logging.

---

## 10. Project Architecture

This section outlines the software architecture of the Chatterbox TTS Server.

### 10.1 Key Modules and Their Roles

*   **`server.py` [1]:**
    *   The main application entry point, built with FastAPI.
    *   Defines all API endpoints (e.g., `/tts`, `/api/ui/initial-data`, configuration endpoints).
    *   Handles incoming HTTP requests, validates them using Pydantic models (from `models.py` [1]).
    *   Serves the static files for the Web UI (`ui/` directory [1]).
    *   Orchestrates the TTS generation process by calling `engine.py` and `utils.py` functions.
    *   Manages application lifecycle events (startup, shutdown), including model loading.
*   **`engine.py` [1]**:
    *   Responsible for loading and managing the `chatterbox-tts` model instance.
    *   `load_model()`: Initializes `ChatterboxTTS.from_pretrained()`, handling device selection (CUDA/CPU).
    *   `synthesize()`: Takes text and generation parameters, invokes the core `chatterbox_model.generate()` method, and returns the audio tensor.
*   **`config.py` [1]**:
    *   Implements the `YamlConfigManager` class for loading, saving, and accessing configuration from `config.yaml`.
    *   Defines the default configuration structure (`DEFAULT_CONFIG`).
    *   Provides convenient accessor functions (e.g., `get_port()`, `get_model_repo_id()`) for other modules to retrieve settings.
*   **`utils.py` [1]**:
    *   Contains a collection of helper functions:
        *   **Text Processing:** `split_into_sentences()`, `chunk_text_by_sentences()` for preparing text for TTS.
        *   **Audio Processing:** `encode_audio()` (to WAV/Opus), `save_audio_to_file()`, `apply_speed_factor()`, optional silence trimming and unvoiced segment removal functions.
        *   **File System Utilities:** `get_valid_reference_files()`, `get_predefined_voices()`, `sanitize_filename()`, `validate_reference_audio()`.
        *   `PerformanceMonitor` class.
*   **`models.py` [1]**:
    *   Defines Pydantic models used for API request body validation and structuring API responses (e.g., `CustomTTSRequest`, `ErrorResponse`).
*   **`ui/` directory [1]**:
    *   `index.html`: The main HTML file for the single-page Web UI.
    *   `script.js`: Client-side JavaScript that handles all UI logic, interacts with the server's API endpoints, manages audio playback with WaveSurfer.js, and updates the DOM dynamically.
    *   `presets.yaml`: Contains example texts and parameters for the UI's preset feature.
*   **External Libraries:** (e.g., `chatterbox-tts`, `fastapi`, `torch`, `librosa`, `soundfile`) provide core functionalities.

### 10.2 Data Flow for TTS Generation (via `/tts` API)

1.  **Client Request:** User (via Web UI or API client) sends a POST request to `/tts` with a JSON payload (`CustomTTSRequest`).
2.  **FastAPI (`server.py`):**
    *   Receives and validates the request against `CustomTTSRequest` model.
    *   Extracts text, voice mode, generation parameters, and chunking options.
3.  **Text Processing (`utils.py`):**
    *   If `split_text` is true, `chunk_text_by_sentences()` is called to divide the input text into manageable chunks.
4.  **TTS Engine (`engine.py`):**
    *   For each text chunk:
        *   `server.py` determines the `audio_prompt_path` based on `voice_mode` (predefined or clone).
        *   `engine.synthesize()` is called with the chunk text, audio prompt path, and generation parameters.
        *   `engine.synthesize()` invokes `chatterbox_model.generate()`.
        *   The raw audio tensor is returned.
5.  **Audio Processing (`utils.py` in `server.py`):**
    *   The audio tensor from the engine is converted to a NumPy array.
    *   Speed factor is applied via `apply_speed_factor()`.
    *   Optional post-processing (silence trimming, etc.) is applied if configured.
    *   Processed audio segments (if chunked) are concatenated.
6.  **Encoding (`utils.py`):**
    *   The final NumPy audio array is encoded into the desired `output_format` (WAV or Opus) by `encode_audio()`, which also handles resampling to the target output sample rate.
7.  **FastAPI Response (`server.py`):**
    *   The encoded audio bytes are streamed back to the client as a `StreamingResponse` with appropriate media type and download headers.
8.  **Client (Web UI - `script.js`):**
    *   Receives the audio blob.
    *   Creates an object URL for the blob.
    *   Initializes WaveSurfer.js to play and visualize the audio.

---

## 11. Testing (Conceptual)

While this project does not include a formal automated test suite in the provided codebase, testing can be approached through several methods:

*   **Manual UI Testing:**
    *   Thoroughly test all UI elements: text input, sliders, dropdowns, buttons, file uploads, audio player.
    *   Test with various text lengths, including very short and very long inputs (to verify chunking).
    *   Test different voice modes (predefined, clone) with valid and invalid selections.
    *   Verify session persistence of UI settings.
    *   Test theme switching.
    *   Check behavior across different browsers (e.g., Chrome, Firefox, Edge).
*   **API Endpoint Testing:**
    *   Use tools like Swagger UI (at `/docs`), Postman, or `curl` to send requests to all API endpoints.
    *   Test `/tts` with various valid and invalid parameter combinations.
        *   Different `output_format` values.
        *   Chunking enabled and disabled.
        *   Different generation parameters (seed, temperature, etc.).
        *   Valid and invalid `predefined_voice_id` and `reference_audio_filename`.
    *   Test `/v1/audio/speech` (OpenAI compatible) similarly, focusing on its specific parameter mapping.
    *   Test configuration endpoints (`/save_settings`, `/reset_settings`) and verify changes in `config.yaml`.
    *   Test file upload endpoints (`/upload_reference`, `/upload_predefined_voice`) with valid and invalid file types/sizes.
    *   Test helper endpoints (`/get_reference_files`, etc.).
*   **Output Audio Quality Assessment:**
    *   Listen to generated audio for clarity, naturalness, artifacts, and correctness based on input text and parameters.
    *   Verify that speed factor, silence trimming, and other audio processing features work as expected.
*   **Configuration Testing:**
    *   Modify `config.yaml` with different valid and invalid values to ensure the server handles them gracefully (e.g., falls back to defaults, logs errors).
    *   Test server startup with a missing `config.yaml` to verify default generation.
*   **Performance Testing (Basic):**
    *   Measure response times for API requests, especially for long text synthesis.
    *   Monitor CPU, GPU, and RAM usage under load. The `PerformanceMonitor` class in `utils.py` [1] can be enabled for more detailed internal timings.
*   **Docker Deployment Testing:**
    *   Build the Docker image and run the container using `docker-compose.yml`.
    *   Verify all functionalities within the containerized environment, including volume mounts and GPU access (if applicable).

For a more robust setup, unit tests (e.g., using `pytest`) could be added for functions in `utils.py` and `config.py`, and integration tests could be written for API endpoints using `FastAPI`'s `TestClient`.

---

## 12. License and Disclaimer

*   **License:** This project is licensed under the MIT License.
*   **Disclaimer:**
    This software is provided "as is," without warranty of any kind, express or implied. The developers and contributors are not liable for any claim, damages, or other liability arising from the use of this software.
    Users are responsible for ensuring that their use of this TTS server and any generated audio complies with all applicable laws, regulations, and ethical guidelines, including those related to copyright, privacy, and voice impersonation.
    It is strongly recommended to use this technology responsibly, primarily with synthetic voices or with explicit consent when using voice cloning features that might resemble real individuals. The project authors disclaim responsibility for any misuse of this technology.