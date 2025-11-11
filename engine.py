# File: engine.py
# Core TTS model loading and speech generation logic.

import logging
import random
import numpy as np
import torch
from typing import Optional, Tuple, Union
from pathlib import Path

from chatterbox.tts import ChatterboxTTS  # Main TTS engine class

# Try to import multilingual model if available (newer versions)
try:
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    MULTILINGUAL_AVAILABLE = True
except ImportError:
    ChatterboxMultilingualTTS = None  # type: ignore
    MULTILINGUAL_AVAILABLE = False
    logging.warning("Multilingual TTS model not available. Please upgrade chatterbox-tts for multilingual support.")

from chatterbox.models.s3gen.const import (
    S3GEN_SR,
)  # Default sample rate from the engine

# Import the singleton config_manager
from config import config_manager

logger = logging.getLogger(__name__)

# --- Global Module Variables ---
chatterbox_model: Optional[Union[ChatterboxTTS, 'ChatterboxMultilingualTTS']] = None
MODEL_LOADED: bool = False
model_device: Optional[str] = (
    None  # Stores the resolved device string ('cuda', 'mps', or 'cpu')
)
use_multilingual_model: bool = True  # Default to multilingual for broader language support


def set_seed(seed_value: int):
    """
    Sets the seed for torch, random, and numpy for reproducibility.
    This is called if a non-zero seed is provided for generation.
    """
    torch.manual_seed(seed_value)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed_value)
        torch.cuda.manual_seed_all(seed_value)  # if using multi-GPU
    if torch.backends.mps.is_available():
        torch.mps.manual_seed(seed_value)
    random.seed(seed_value)
    np.random.seed(seed_value)
    logger.info(f"Global seed set to: {seed_value}")


def _test_cuda_functionality() -> bool:
    """
    Tests if CUDA is actually functional, not just available.

    Returns:
        bool: True if CUDA works, False otherwise.
    """
    if not torch.cuda.is_available():
        return False

    try:
        test_tensor = torch.tensor([1.0])
        test_tensor = test_tensor.cuda()
        test_tensor = test_tensor.cpu()
        return True
    except Exception as e:
        logger.warning(f"CUDA functionality test failed: {e}")
        return False


def _test_mps_functionality() -> bool:
    """
    Tests if MPS is actually functional, not just available.

    Returns:
        bool: True if MPS works, False otherwise.
    """
    if not torch.backends.mps.is_available():
        return False

    try:
        test_tensor = torch.tensor([1.0])
        test_tensor = test_tensor.to("mps")
        test_tensor = test_tensor.cpu()
        return True
    except Exception as e:
        logger.warning(f"MPS functionality test failed: {e}")
        return False


def load_model() -> bool:
    """
    Loads the TTS model.
    This version directly attempts to load from the Hugging Face repository (or its cache)
    using `from_pretrained`, bypassing the local `paths.model_cache` directory.
    Automatically uses the multilingual model for broader language support.
    Updates global variables `chatterbox_model`, `MODEL_LOADED`, and `model_device`.

    Returns:
        bool: True if the model was loaded successfully, False otherwise.
    """
    global chatterbox_model, MODEL_LOADED, model_device, use_multilingual_model

    if MODEL_LOADED:
        logger.info("TTS model is already loaded.")
        return True

    try:
        # Determine processing device with robust CUDA detection and intelligent fallback
        device_setting = config_manager.get_string("tts_engine.device", "auto")

        if device_setting == "auto":
            if _test_cuda_functionality():
                resolved_device_str = "cuda"
                logger.info("CUDA functionality test passed. Using CUDA.")
            elif _test_mps_functionality():
                resolved_device_str = "mps"
                logger.info("MPS functionality test passed. Using MPS.")
            else:
                resolved_device_str = "cpu"
                logger.info("CUDA and MPS not functional or not available. Using CPU.")

        elif device_setting == "cuda":
            if _test_cuda_functionality():
                resolved_device_str = "cuda"
                logger.info("CUDA requested and functional. Using CUDA.")
            else:
                resolved_device_str = "cpu"
                logger.warning(
                    "CUDA was requested in config but functionality test failed. "
                    "PyTorch may not be compiled with CUDA support. "
                    "Automatically falling back to CPU."
                )

        elif device_setting == "mps":
            if _test_mps_functionality():
                resolved_device_str = "mps"
                logger.info("MPS requested and functional. Using MPS.")
            else:
                resolved_device_str = "cpu"
                logger.warning(
                    "MPS was requested in config but functionality test failed. "
                    "PyTorch may not be compiled with MPS support. "
                    "Automatically falling back to CPU."
                )

        elif device_setting == "cpu":
            resolved_device_str = "cpu"
            logger.info("CPU device explicitly requested in config. Using CPU.")

        else:
            logger.warning(
                f"Invalid device setting '{device_setting}' in config. "
                f"Defaulting to auto-detection."
            )
            if _test_cuda_functionality():
                resolved_device_str = "cuda"
            elif _test_mps_functionality():
                resolved_device_str = "mps"
            else:
                resolved_device_str = "cpu"
            logger.info(f"Auto-detection resolved to: {resolved_device_str}")

        model_device = resolved_device_str
        logger.info(f"Final device selection: {model_device}")

        # Check if multilingual model should be used (default: True for broader language support)
        use_multilingual_model = config_manager.get_bool("model.use_multilingual", True)
        
        # Check if multilingual model is actually available
        if use_multilingual_model and not MULTILINGUAL_AVAILABLE:
            logger.warning(
                "Multilingual model requested but not available in current chatterbox-tts version. "
                "Using English-only model. To enable multilingual support, upgrade chatterbox-tts: "
                "pip install --upgrade chatterbox-tts"
            )
            use_multilingual_model = False
        
        logger.info(
            f"Attempting to load {'multilingual' if use_multilingual_model else 'English-only'} model using from_pretrained."
        )
        try:
            # Directly use from_pretrained. This will utilize the standard Hugging Face cache.
            # The model's from_pretrained method handles downloading if the model is not in the cache.
            if use_multilingual_model and MULTILINGUAL_AVAILABLE:
                # Workaround for MPS/CPU: Patch torch.load to use map_location for non-CUDA devices
                original_torch_load = torch.load
                if model_device != "cuda":
                    device_obj = torch.device(model_device)
                    def patched_torch_load(f, *args, **kwargs):
                        if 'map_location' not in kwargs:
                            kwargs['map_location'] = device_obj
                        return original_torch_load(f, *args, **kwargs)
                    torch.load = patched_torch_load
                
                try:
                    chatterbox_model = ChatterboxMultilingualTTS.from_pretrained(device=model_device)
                    
                    # Fix for MPS: Set attention implementation to 'eager' to avoid SDPA issues
                    if hasattr(chatterbox_model, 't3') and hasattr(chatterbox_model.t3, 'tfmr'):
                        try:
                            chatterbox_model.t3.tfmr.config._attn_implementation = 'eager'
                            logger.info("Set attention implementation to 'eager' for MPS compatibility")
                        except Exception as e:
                            logger.warning(f"Could not set attention implementation: {e}")
                    
                    logger.info(
                        f"Successfully loaded Multilingual TTS model on {model_device}. Supports 23 languages including Hindi."
                    )
                finally:
                    # Restore original torch.load
                    torch.load = original_torch_load
            else:
                chatterbox_model = ChatterboxTTS.from_pretrained(device=model_device)
                logger.info(
                    f"Successfully loaded English-only TTS model on {model_device}."
                )
        except Exception as e_hf:
            logger.error(
                f"Failed to load {'multilingual' if use_multilingual_model else 'English-only'} model: {e_hf}",
                exc_info=True,
            )
            chatterbox_model = None
            MODEL_LOADED = False
            return False

        MODEL_LOADED = True
        if chatterbox_model:
            logger.info(
                f"TTS Model loaded successfully on {model_device}. Engine sample rate: {chatterbox_model.sr} Hz."
            )
        else:
            logger.error(
                "Model loading sequence completed, but chatterbox_model is None. This indicates an unexpected issue."
            )
            MODEL_LOADED = False
            return False

        return True

    except Exception as e:
        logger.error(
            f"An unexpected error occurred during model loading: {e}", exc_info=True
        )
        chatterbox_model = None
        MODEL_LOADED = False
        return False


def synthesize(
    text: str,
    audio_prompt_path: Optional[str] = None,
    temperature: float = 0.8,
    exaggeration: float = 0.5,
    cfg_weight: float = 0.5,
    seed: int = 0,
    language_id: Optional[str] = None,
) -> Tuple[Optional[torch.Tensor], Optional[int]]:
    """
    Synthesizes audio from text using the loaded TTS model.

    Args:
        text: The text to synthesize.
        audio_prompt_path: Path to an audio file for voice cloning or predefined voice.
        temperature: Controls randomness in generation.
        exaggeration: Controls expressiveness.
        cfg_weight: Classifier-Free Guidance weight.
        seed: Random seed for generation. If 0, default randomness is used.
              If non-zero, a global seed is set for reproducibility.
        language_id: Language code for multilingual model (e.g., 'hi' for Hindi, 'en' for English).
                     Only used with multilingual model. If None, defaults to config language.

    Returns:
        A tuple containing the audio waveform (torch.Tensor) and the sample rate (int),
        or (None, None) if synthesis fails.
    """
    global chatterbox_model, use_multilingual_model

    if not MODEL_LOADED or chatterbox_model is None:
        logger.error("TTS model is not loaded. Cannot synthesize audio.")
        return None, None

    try:
        # Set seed globally if a specific seed value is provided and is non-zero.
        if seed != 0:
            logger.info(f"Applying user-provided seed for generation: {seed}")
            set_seed(seed)
        else:
            logger.info(
                "Using default (potentially random) generation behavior as seed is 0."
            )

        logger.debug(
            f"Synthesizing with params: audio_prompt='{audio_prompt_path}', temp={temperature}, "
            f"exag={exaggeration}, cfg_weight={cfg_weight}, seed_applied_globally_if_nonzero={seed}, "
            f"language_id={language_id}"
        )

        # Call the core model's generate method
        # For multilingual model, include language_id parameter if available
        if use_multilingual_model and MULTILINGUAL_AVAILABLE and isinstance(chatterbox_model, ChatterboxMultilingualTTS):
            # Use provided language_id or default from config
            effective_language = language_id or config_manager.get_string("generation_defaults.language", "en")
            logger.info(f"Generating speech for language: {effective_language}")
            wav_tensor = chatterbox_model.generate(
                text=text,
                audio_prompt_path=audio_prompt_path,
                temperature=temperature,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
                language_id=effective_language,
            )
        else:
            # English-only model doesn't use language_id parameter
            if language_id and language_id != "en":
                logger.warning(
                    f"Language '{language_id}' requested but multilingual model not available. "
                    "Generating in English. Upgrade chatterbox-tts for multilingual support."
                )
            wav_tensor = chatterbox_model.generate(
                text=text,
                audio_prompt_path=audio_prompt_path,
                temperature=temperature,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
            )

        # The model's generate method already returns a CPU tensor.
        return wav_tensor, chatterbox_model.sr

    except Exception as e:
        logger.error(f"Error during TTS synthesis: {e}", exc_info=True)
        return None, None


# --- End File: engine.py ---
