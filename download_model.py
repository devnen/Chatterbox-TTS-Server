# File: download_model.py
# Utility script to download the TTS model and its components.
# This script focuses on ensuring the core engine model files are available locally
# in the path specified by the application's configuration.

import logging
import os
from pathlib import Path
from huggingface_hub import hf_hub_download

# Configure basic logging for the script
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ModelDownloader")

# Import configuration manager to access paths and model settings
try:
    from config import config_manager
except ImportError:
    logger.error("Failed to import config_manager. Ensure config.py is accessible.")
    exit(1)


# Map UI sentinel values to actual Hugging Face repository IDs.
MODEL_REPO_MAP = {
    "chatterbox": "ResembleAI/chatterbox",
    "original": "ResembleAI/chatterbox",
    "resembleai/chatterbox": "ResembleAI/chatterbox",
    "chatterbox-multilingual": "ResembleAI/chatterbox",
    "multilingual": "ResembleAI/chatterbox",
    "resembleai/chatterbox-multilingual": "ResembleAI/chatterbox",
    "chatterbox-turbo": "ResembleAI/chatterbox-turbo",
    "turbo": "ResembleAI/chatterbox-turbo",
    "resembleai/chatterbox-turbo": "ResembleAI/chatterbox-turbo",
}


# Define the list of core model files expected by the TTS engine.
# These correspond to files typically found in the Hugging Face repository
# for the ChatterboxTTS engine.
CHATTERBOX_MODEL_FILES = [
    "ve.pt",  # Voice Encoder model
    "t3_cfg.pt",  # T3 model (Transformer Text-to-Token)
    "s3gen.pt",  # S3Gen model (Token-to-Waveform)
    "tokenizer.json",  # Text tokenizer configuration
    "conds.pt",  # Default conditioning data (e.g., for default voice)
    # "ve.safetensors",
    # "t3_cfg.safetensors",
    # "t3_mtl23ls_v2.safetensors",
    # "s3gen.safetensors",
]


def download_engine_files():
    """
    Downloads all necessary TTS engine files from the configured Hugging Face
    repository to the local model cache directory specified in `config.yaml`.
    """
    logger.info("--- Starting TTS Engine Model Download ---")

    model_cache_path_str = config_manager.get_string(
        "paths.model_cache", "./model_cache"
    )
    model_cache_path = Path(model_cache_path_str).resolve()  # Ensure absolute path

    configured_repo_id = config_manager.get_string(
        "model.repo_id", "ResembleAI/chatterbox"
    )
    model_repo_id = _resolve_model_repo_id(configured_repo_id)

    logger.info(f"Target model repository: {model_repo_id}")
    logger.info(f"Local download directory: {model_cache_path}")

    # Ensure the target local directory exists
    try:
        model_cache_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured download directory exists: {model_cache_path}")
    except Exception as e:
        logger.error(
            f"Could not create or access download directory '{model_cache_path}': {e}",
            exc_info=True,
        )
        return False

    all_successful = True
    for filename in CHATTERBOX_MODEL_FILES:
        logger.info(f"Attempting to download '{filename}'...")
        try:
            hf_hub_download(
                repo_id=model_repo_id,
                filename=filename,
                cache_dir=model_cache_path,  # Use this to control the *huggingface cache structure* if preferred
                local_dir=model_cache_path,  # This ensures files are placed directly here
                local_dir_use_symlinks=False,  # Store actual files, not symlinks
                force_download=False,  # Set to True to always re-download
                resume_download=True,
            )
            logger.info(
                f"Successfully downloaded or found '{filename}' in '{model_cache_path}'."
            )
        except Exception as e:
            logger.error(f"Failed to download '{filename}': {e}", exc_info=True)
            all_successful = False
            # Optionally, continue trying to download other files

    if all_successful:
        logger.info(
            "--- All TTS engine model files downloaded/verified successfully. ---"
        )
    else:
        logger.error("--- Some model files failed to download. Please check logs. ---")

    return all_successful


if __name__ == "__main__":
    if download_engine_files():
        logger.info("Model download process completed. You can now start the server.")
    else:
        logger.error(
            "Model download process encountered errors. The server might not start correctly."
        )
        exit(1)  # Exit with error code if essential downloads failed


# --- End File: download_model.py ---
def _resolve_model_repo_id(raw_value: str) -> str:
    """
    Resolves UI sentinel values (e.g., 'chatterbox-multilingual') to actual
    Hugging Face repository IDs required by hf_hub_download.
    """
    if not raw_value:
        return "ResembleAI/chatterbox"

    normalized = raw_value.lower().strip()
    resolved = MODEL_REPO_MAP.get(normalized)
    if resolved:
        if resolved != raw_value:
            logger.info(
                f"Resolved model repo '{raw_value}' to Hugging Face repo '{resolved}'."
            )
        return resolved

    logger.info(
        f"Using custom/explicit model repo id '{raw_value}' (no sentinel mapping applied)."
    )
    return raw_value
