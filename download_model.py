# File: download_model.py
# Utility script to download the TTS model and its components.
# This script focuses on ensuring the core engine model files are available locally
# in the path specified by the application's configuration.

import logging
import os
from pathlib import Path
from huggingface_hub import hf_hub_download, login

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

# Your Hugging Face token for authentication
HF_TOKEN = "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"

# Define the list of core model files expected by the TTS engine.
# These correspond to files typically found in the Hugging Face repository
# for the ChatterboxTTS engine.
CHATTERBOX_MODEL_FILES = [
    "ve.pt",  # Voice Encoder model
    "t3_cfg.pt",  # T3 model (Transformer Text-to-Token)
    "s3gen.pt",  # S3Gen model (Token-to-Waveform)
    "tokenizer.json",  # Text tokenizer configuration
    "conds.pt",  # Default conditioning data (e.g., for default voice)
]


def download_engine_files():
    """
    Downloads all necessary TTS engine files from the configured Hugging Face
    repository to the local model cache directory specified in `config.yaml`.
    """
    logger.info("--- Starting TTS Engine Model Download ---")

    # Login with your Hugging Face token
    try:
        login(token=HF_TOKEN)
        logger.info("Successfully authenticated with Hugging Face Hub")
    except Exception as e:
        logger.error(f"Failed to authenticate with Hugging Face Hub: {e}")
        return False

    model_cache_path_str = config_manager.get_string(
        "paths.model_cache", "./model_cache"
    )
    model_cache_path = Path(model_cache_path_str).resolve()  # Ensure absolute path

    model_repo_id = config_manager.get_string("model.repo_id", "ResembleAI/chatterbox")

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
                cache_dir=model_cache_path,
                local_dir=model_cache_path,
                local_dir_use_symlinks=False,
                force_download=False,
                resume_download=True,
                token=HF_TOKEN,  # Pass the token for each download
            )
            logger.info(
                f"Successfully downloaded or found '{filename}' in '{model_cache_path}'."
            )
        except Exception as e:
            logger.error(f"Failed to download '{filename}': {e}", exc_info=True)
            all_successful = False

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
        exit(1)
