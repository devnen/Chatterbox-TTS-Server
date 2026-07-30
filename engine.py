# File: engine.py
# Core TTS model loading and speech generation logic.

import gc
import logging
import os
import random
import threading
import time
from collections import OrderedDict
import numpy as np
import torch
from typing import List, Optional, Tuple
from pathlib import Path

from chatterbox.tts import ChatterboxTTS  # Main TTS engine class
from chatterbox.models.s3gen.const import (
    S3GEN_SR,
)  # Default sample rate from the engine

# Defensive Turbo import - Turbo may not be available in older package versions
try:
    from chatterbox.tts_turbo import ChatterboxTurboTTS

    TURBO_AVAILABLE = True
except ImportError:
    ChatterboxTurboTTS = None
    TURBO_AVAILABLE = False

# Defensive Multilingual import
try:
    from chatterbox import ChatterboxMultilingualTTS, SUPPORTED_LANGUAGES

    MULTILINGUAL_AVAILABLE = True
except ImportError:
    ChatterboxMultilingualTTS = None
    SUPPORTED_LANGUAGES = {}
    MULTILINGUAL_AVAILABLE = False

# Import the singleton config_manager
from config import config_manager

logger = logging.getLogger(__name__)

# Log BF16 setting at module load so it's visible in startup logs
# (BF16_ENABLED is resolved after logger is set up — logged in initialize_tts_model)
if TURBO_AVAILABLE:
    logger.info("ChatterboxTurboTTS is available in the installed chatterbox package.")
else:
    logger.info("ChatterboxTurboTTS not available in installed chatterbox package.")

# Log Multilingual availability status at module load time
if MULTILINGUAL_AVAILABLE:
    logger.info("ChatterboxMultilingualTTS is available in the installed chatterbox package.")
    logger.info(f"Supported languages: {list(SUPPORTED_LANGUAGES.keys())}")
else:
    logger.info("ChatterboxMultilingualTTS not available in installed chatterbox package.")

# Model selector whitelist - maps config values to model types
MODEL_SELECTOR_MAP = {
    # Original model selectors
    "chatterbox": "original",
    "original": "original",
    "resembleai/chatterbox": "original",
    # Turbo model selectors
    "chatterbox-turbo": "turbo",
    "turbo": "turbo",
    "resembleai/chatterbox-turbo": "turbo",
    # Multilingual model selectors
    "chatterbox-multilingual": "multilingual",
    "multilingual": "multilingual",
}

# Paralinguistic tags supported by Turbo model
TURBO_PARALINGUISTIC_TAGS = [
    "laugh",
    "chuckle",
    "sigh",
    "gasp",
    "cough",
    "clear throat",
    "sniff",
    "groan",
    "shush",
]

# --- BF16 optimization flag ---
# TTS_BF16: controls whether T3 is converted to bfloat16 and whether
# autocast is used during inference. Off by default so existing users
# see no behavior change on upgrade — opt in for the speedup.
#   off (default) — keep T3 in float32, no autocast
#   on / 1 / true  — force-enable (assumes hardware supports bf16)
#   auto           — enable only if torch.cuda.is_bf16_supported()
def _resolve_bf16_setting() -> bool:
    val = os.environ.get("TTS_BF16", "off").strip().lower()
    if val in ("on", "1", "true"):
        return True
    if val == "auto":
        if torch.cuda.is_available():
            return torch.cuda.is_bf16_supported()
        return False
    # off / 0 / false / anything else
    return False

BF16_ENABLED: bool = _resolve_bf16_setting()

# --- Global Module Variables ---
chatterbox_model: Optional[ChatterboxTTS] = None
MODEL_LOADED: bool = False
model_device: Optional[str] = (
    None  # Stores the resolved device string ('cuda' or 'cpu')
)

# Track which model type is loaded
loaded_model_type: Optional[str] = None  # "original" or "turbo"
loaded_model_class_name: Optional[str] = None  # "ChatterboxTTS" or "ChatterboxTurboTTS"

# Voice conditioning cache: avoids re-encoding the same voice file on every request.
# Key: (resolved_path, file_mtime, exaggeration) — mtime invalidates if file changes.
#
# Bounded, because each entry pins GPU tensors for the process lifetime and this
# was previously an unbounded dict cleared only by unload_model(). Measured on a
# P106-100 (5.93 GiB) with chatterbox-turbo: cycling 28 reference voices grew
# live tensors from 4.09 to 5.46 GiB and left 0.11 GiB of headroom, after which
# 406 of 453 requests failed. The same load with one voice ran clean.
#
# This is not only a small-card concern. /upload_reference stores each uploaded
# file under its own path, so every distinct voice a deployment ever serves mints
# a permanent key — a larger card buys a higher ceiling, not a different outcome.
#
# CONDS_CACHE_MAX bounds the entry count. Measured cost is ~175 MB of VRAM per
# entry (live tensors grew 1.37 GiB across exactly 8 cached voices), so this is a
# far more expensive cache than it looks — budget it against free VRAM, not
# against an entry count that sounds small.
#
# The default of 4 costs ~700 MB, which leaves a 6 GB card ~1.1 GiB for
# generation after the 4.09 GiB model. On a 12 GB card 16+ is comfortable. Set 0
# to disable caching and re-encode the voice on every request.
def _resolve_conds_cache_max() -> int:
    """Read CONDS_CACHE_MAX, tolerating garbage rather than failing to import."""
    raw = os.environ.get("CONDS_CACHE_MAX", "4").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        logger.warning(
            f"CONDS_CACHE_MAX={raw!r} is not an integer; using the default of 4."
        )
        return 4


_CONDS_CACHE_MAX: int = _resolve_conds_cache_max()
_conds_cache: "OrderedDict[tuple, object]" = OrderedDict()

# synthesize() runs concurrently: server.py dispatches it through
# loop.run_in_executor(), so several threads can touch this cache at once.
# Reads are two steps (look up, then refresh recency) and writes are three
# (insert, refresh, evict), none of which are atomic — without this lock a
# thread can evict a key between another thread's lookup and its use, raising
# KeyError. The unbounded version could not hit this because nothing was ever
# removed.
_conds_cache_lock = threading.Lock()


def _conds_cache_get(key: tuple):
    """Return cached conds for `key` and mark it most-recently-used, else None."""
    if _CONDS_CACHE_MAX == 0:
        return None
    with _conds_cache_lock:
        conds = _conds_cache.get(key)
        if conds is not None:
            _conds_cache.move_to_end(key)
        return conds


def _conds_cache_store(key: tuple, conds) -> None:
    """Insert under an LRU bound, evicting the least recently used entries.

    Eviction drops the last reference to that entry's tensors; the caching
    allocator reuses the freed blocks, so VRAM is recovered without an explicit
    empty_cache() on the request path.
    """
    if _CONDS_CACHE_MAX == 0:
        return
    with _conds_cache_lock:
        _conds_cache[key] = conds
        _conds_cache.move_to_end(key)
        while len(_conds_cache) > _CONDS_CACHE_MAX:
            evicted_key, _ = _conds_cache.popitem(last=False)
            logger.debug(
                f"Voice cache evicted (LRU, max={_CONDS_CACHE_MAX}): {evicted_key[0]}"
            )


def _conds_cache_key(path: str, exaggeration: float) -> tuple:
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0.0
    return (path, mtime, exaggeration)


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


def _get_model_class(selector: str) -> tuple:
    """
    Determines which model class to use based on the config selector value.

    Args:
        selector: The value from config model.repo_id

    Returns:
        Tuple of (model_class, model_type_string)

    Raises:
        ImportError: If Turbo or Multilingual is selected but not available in the package
    """
    selector_normalized = selector.lower().strip()
    model_type = MODEL_SELECTOR_MAP.get(selector_normalized)

    if model_type == "turbo":
        if not TURBO_AVAILABLE:
            raise ImportError(
                f"Model selector '{selector}' requires ChatterboxTurboTTS, "
                f"but it is not available in the installed chatterbox package. "
                f"Please update the chatterbox-tts package to the latest version, "
                f"or use 'chatterbox' to select the original model."
            )
        logger.info(
            f"Model selector '{selector}' resolved to Turbo model (ChatterboxTurboTTS)"
        )
        return ChatterboxTurboTTS, "turbo"

    if model_type == "multilingual":
        if not MULTILINGUAL_AVAILABLE:
            raise ImportError(
                f"Model selector '{selector}' requires ChatterboxMultilingualTTS, "
                f"but it is not available in the installed chatterbox package. "
                f"Please update the chatterbox-tts package to the latest version, "
                f"or use 'chatterbox' to select the original model."
            )
        logger.info(
            f"Model selector '{selector}' resolved to Multilingual model (ChatterboxMultilingualTTS)"
        )
        return ChatterboxMultilingualTTS, "multilingual"

    if model_type == "original":
        logger.info(
            f"Model selector '{selector}' resolved to Original model (ChatterboxTTS)"
        )
        return ChatterboxTTS, "original"

    # Unknown selector - default to original with warning
    logger.warning(
        f"Unknown model selector '{selector}'. "
        f"Valid values: chatterbox, chatterbox-turbo, chatterbox-multilingual, original, turbo, multilingual, "
        f"ResembleAI/chatterbox, ResembleAI/chatterbox-turbo. "
        f"Defaulting to original ChatterboxTTS model."
    )
    return ChatterboxTTS, "original"


def get_model_info() -> dict:
    """
    Returns information about the currently loaded model.
    Used by the API to expose model details to the UI.

    Returns:
        Dictionary containing model information
    """
    return {
        "loaded": MODEL_LOADED,
        "type": loaded_model_type,  # "original", "turbo", or "multilingual"
        "class_name": loaded_model_class_name,
        "device": model_device,
        "sample_rate": chatterbox_model.sr if chatterbox_model else None,
        "supports_paralinguistic_tags": loaded_model_type == "turbo",
        "available_paralinguistic_tags": (
            TURBO_PARALINGUISTIC_TAGS if loaded_model_type == "turbo" else []
        ),
        "turbo_available_in_package": TURBO_AVAILABLE,
        "multilingual_available_in_package": MULTILINGUAL_AVAILABLE,
        "supports_multilingual": loaded_model_type == "multilingual",
        "supported_languages": (
            SUPPORTED_LANGUAGES if loaded_model_type == "multilingual" else {"en": "English"}
        ),
    }


def load_model() -> bool:
    """
    Loads the TTS model.
    This version directly attempts to load from the Hugging Face repository (or its cache)
    using `from_pretrained`, bypassing the local `paths.model_cache` directory.
    Updates global variables `chatterbox_model`, `MODEL_LOADED`, and `model_device`.

    Returns:
        bool: True if the model was loaded successfully, False otherwise.
    """
    global chatterbox_model, MODEL_LOADED, model_device
    global loaded_model_type, loaded_model_class_name

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
        logger.info(
            f"BF16 optimization: {'enabled' if BF16_ENABLED else 'disabled'} "
            f"(TTS_BF16={os.environ.get('TTS_BF16', 'off')})"
        )

        # Get the model selector from config
        model_selector = config_manager.get_string("model.repo_id", "chatterbox-turbo")

        logger.info(f"Model selector from config: '{model_selector}'")

        try:
            # Determine which model class to use
            model_class, model_type = _get_model_class(model_selector)

            logger.info(
                f"Initializing {model_class.__name__} on device '{model_device}'..."
            )
            logger.info(f"Model type: {model_type}")
            if model_type == "turbo":
                logger.info(
                    f"Turbo model supports paralinguistic tags: {TURBO_PARALINGUISTIC_TAGS}"
                )

            # Load the model using from_pretrained - handles HuggingFace downloads automatically
            chatterbox_model = model_class.from_pretrained(device=model_device)

            # Convert T3 to bfloat16 if enabled.
            # Token generation is memory-bandwidth bound; bf16 halves bytes read per
            # forward pass. S3Gen is intentionally kept in float32 — it runs only
            # 2 CFM timesteps and bf16 causes token/mask size mismatches.
            if BF16_ENABLED:
                if hasattr(chatterbox_model, "t3"):
                    chatterbox_model.t3 = chatterbox_model.t3.bfloat16()
                    logger.info("T3 model converted to bfloat16 for faster token generation.")
            else:
                logger.info("BF16 optimization disabled (TTS_BF16=off or hardware unsupported).")

            # Store model metadata
            loaded_model_type = model_type
            loaded_model_class_name = model_class.__name__

            logger.info(f"Successfully loaded {model_class.__name__} on {model_device}")
            logger.info(f"Model sample rate: {chatterbox_model.sr} Hz")
        except ImportError as e_import:
            logger.error(
                f"Failed to load model due to import error: {e_import}",
                exc_info=True,
            )
            chatterbox_model = None
            MODEL_LOADED = False
            return False
        except Exception as e_hf:
            logger.error(
                f"Failed to load model using from_pretrained: {e_hf}",
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


# --- Chunk batching -----------------------------------------------------------
# Turbo's decode loop (T3.inference_turbo) is written with batch dimensions
# throughout and uses HuggingFace logits processors, which are batch-correct.
# Measured on a P106-100, batching identical-voice chunks scales well and costs
# almost no VRAM, because the weights dominate and only the KV cache grows:
#
#     batch   T3 time   s/item   speedup   peak VRAM
#       1      0.98s     0.976    1.00x      4.50 GiB
#       2      1.15s     0.575    1.70x      4.62 GiB
#       4      1.75s     0.438    2.23x      4.84 GiB
#       8      2.76s     0.346    2.82x      5.29 GiB
#
# /tts already splits long text into chunks that all share one voice, so those
# chunks can go through a single forward pass with no cross-request queueing and
# no added latency. TTS_BATCH_SIZE caps it; 4 is the defensible ceiling on a 6 GB
# card (batch 8 leaves only ~0.6 GiB, and real chunks are longer than the short
# test strings above).
def _resolve_batch_size() -> int:
    raw = os.environ.get("TTS_BATCH_SIZE", "4").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        logger.warning(f"TTS_BATCH_SIZE={raw!r} is not an integer; using 4.")
        return 4


TTS_BATCH_SIZE: int = _resolve_batch_size()

# Token ids at or above this are out-of-vocabulary for s3gen; turbo's own
# generate() filters on the same constant.
_S3GEN_TOKEN_LIMIT = 6561


def batching_available(text_count: int, seed: int) -> bool:
    """Whether synthesize_batch() can serve this request.

    Declines rather than silently changing behaviour when:
      - the model is not turbo (only inference_turbo takes a batch),
      - there is nothing to gain (one chunk, or batching disabled),
      - a seed was requested. Sequential chunks each re-seed from the same value,
        while a batch draws all rows from one generator, so seeded output would
        stop being reproducible. Reproducibility wins over speed here.
    """
    return (
        MODEL_LOADED
        and chatterbox_model is not None
        and loaded_model_type == "turbo"
        and TTS_BATCH_SIZE > 1
        and text_count > 1
        and seed == 0
    )


def _resolve_conds(audio_prompt_path: Optional[str], exaggeration: float):
    """Return the Conditionals for this voice, using the cache when possible.

    Returns the object rather than leaving the caller to read
    chatterbox_model.conds back: that attribute is shared process-wide, so a
    concurrent request can reassign it between the two statements and the batch
    would generate in the wrong voice. Holding a local reference sidesteps that
    entirely — the batch uses the conds it resolved, whatever else touches the
    model meanwhile.
    """
    if not audio_prompt_path or not hasattr(chatterbox_model, "conds"):
        return None
    ex_for_key = 0.0 if loaded_model_type == "turbo" else exaggeration
    conds_key = _conds_cache_key(audio_prompt_path, ex_for_key)
    cached = _conds_cache_get(conds_key)
    if cached is not None:
        logger.debug(f"Voice cache hit (batch): {audio_prompt_path}")
        return cached
    chatterbox_model.prepare_conditionals(audio_prompt_path, exaggeration=exaggeration)
    conds = chatterbox_model.conds
    if conds is not None:
        _conds_cache_store(conds_key, conds)
        logger.debug(f"Cached voice conditionals (batch) for: {audio_prompt_path}")
    return conds


def warmup_batch(audio_prompt_path: Optional[str]) -> bool:
    """Pay the one-time batched-kernel setup cost at startup instead of on a request.

    The first batched forward pass on a cold process costs ~10s on a P106-100
    while CUDA selects and loads kernels for a batch dimension the model has not
    seen. Measured: 13.5s first call, then 2.8s steady state. The cost is one-time
    and NOT per-shape — after warming at batch 2, fresh batch sizes of 3 and 4 ran
    at full speed — so a single small warmup covers every later batch.

    Without this the first real multi-chunk request eats the whole penalty, which
    would read as a latency regression rather than a speedup.
    """
    if not batching_available(text_count=2, seed=0) or not audio_prompt_path:
        return False
    try:
        started = time.time()
        wavs, _ = synthesize_batch(
            texts=["Warming up the batched path.", "Second row for the batch."],
            audio_prompt_path=audio_prompt_path,
        )
        if wavs is None:
            logger.warning("Batch warmup did not run; first batched request will be slow.")
            return False
        logger.info(f"Batched path warmed in {time.time() - started:.1f}s.")
        return True
    except Exception as e:
        logger.warning(f"Batch warmup failed ({e}); first batched request will be slow.")
        return False


def synthesize_batch(
    texts: List[str],
    audio_prompt_path: Optional[str] = None,
    temperature: float = 0.8,
    exaggeration: float = 0.5,
    cfg_weight: float = 0.5,
    seed: int = 0,
    language: str = "en",
) -> Tuple[Optional[List[torch.Tensor]], Optional[int]]:
    """Synthesize several texts sharing one voice in batched forward passes.

    Returns (list of wav tensors aligned with `texts`, sample_rate), or
    (None, None) if batching does not apply or fails — callers must fall back to
    per-item synthesize() on None rather than surfacing an error.
    """
    if not batching_available(len(texts), seed):
        return None, None

    try:
        # Imported here so a non-turbo install never needs these symbols.
        from chatterbox.tts_turbo import punc_norm, S3GEN_SIL

        model = chatterbox_model
        conds = _resolve_conds(audio_prompt_path, exaggeration)
        if conds is None:
            logger.warning("Batch synthesis has no voice conditionals; falling back.")
            return None, None

        stop_token = model.t3.hp.stop_speech_token
        wavs: List[torch.Tensor] = []

        for start in range(0, len(texts), TTS_BATCH_SIZE):
            group = texts[start : start + TTS_BATCH_SIZE]
            encoded = model.tokenizer(
                [punc_norm(t) for t in group],
                return_tensors="pt",
                padding=True,
                truncation=True,
            )
            text_tokens = encoded.input_ids.to(model.device)

            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=BF16_ENABLED):
                all_tokens = model.t3.inference_turbo(
                    t3_cond=conds.t3,
                    text_tokens=text_tokens,
                    temperature=temperature,
                )

            for row_idx in range(all_tokens.size(0)):
                row = all_tokens[row_idx]
                # inference_turbo only breaks once EVERY row has emitted stop, so
                # rows that finished early keep sampling. Those trailing tokens are
                # below the OOV limit and would survive the filter as audible
                # gibberish, so truncate at the first stop before filtering.
                hit = (row == stop_token).nonzero()
                if hit.numel():
                    row = row[: hit[0, 0]]
                row = row[row < _S3GEN_TOKEN_LIMIT]
                if row.numel() == 0:
                    logger.warning(
                        f"Batch row {start + row_idx} produced no usable tokens; falling back."
                    )
                    return None, None

                silence = torch.tensor(
                    [S3GEN_SIL] * 3, dtype=torch.long, device=model.device
                )
                row = torch.cat([row, silence])

                # s3gen runs per row: it accepted a batch in testing, but only with
                # equal-length token sequences, and real chunks differ in length.
                # Padding plus masking would be needed to batch this stage safely,
                # and T3 decode dominates the cost anyway.
                with torch.autocast("cuda", dtype=torch.bfloat16, enabled=BF16_ENABLED):
                    wav, _ = model.s3gen.inference(
                        speech_tokens=row, ref_dict=conds.gen, n_cfm_timesteps=2
                    )
                wav_np = wav.squeeze(0).detach().cpu().numpy()
                wav_np = model.watermarker.apply_watermark(wav_np, sample_rate=model.sr)
                wavs.append(torch.from_numpy(wav_np).unsqueeze(0))

        # Callers index this list per chunk, so a short list would be an
        # IndexError rather than a graceful fallback. Refuse instead.
        if len(wavs) != len(texts):
            logger.error(
                f"Batch produced {len(wavs)} wav(s) for {len(texts)} chunk(s); falling back."
            )
            return None, None

        logger.info(
            f"Batched {len(texts)} chunk(s) in "
            f"{(len(texts) + TTS_BATCH_SIZE - 1) // TTS_BATCH_SIZE} pass(es) "
            f"(batch size {TTS_BATCH_SIZE})."
        )
        return wavs, model.sr

    except Exception as e:
        logger.error(f"Batched synthesis failed, falling back: {e}", exc_info=True)
        return None, None


def synthesize(
    text: str,
    audio_prompt_path: Optional[str] = None,
    temperature: float = 0.8,
    exaggeration: float = 0.5,
    cfg_weight: float = 0.5,
    seed: int = 0,
    language: str = "en",
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
        language: Language code for multilingual model (e.g., 'en', 'it', 'de').

    Returns:
        A tuple containing the audio waveform (torch.Tensor) and the sample rate (int),
        or (None, None) if synthesis fails.
    """
    global chatterbox_model

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
            f"language={language}"
        )

        # Voice conditioning cache: skip re-encoding the same voice file.
        # Turbo ignores exaggeration in conds; others include it in the key.
        effective_prompt = audio_prompt_path
        conds_key = None
        if audio_prompt_path and hasattr(chatterbox_model, "conds"):
            ex_for_key = 0.0 if loaded_model_type == "turbo" else exaggeration
            conds_key = _conds_cache_key(audio_prompt_path, ex_for_key)
            # Single locked lookup that also refreshes recency — checking
            # membership and then indexing would race with eviction.
            cached_conds = _conds_cache_get(conds_key)
            if cached_conds is not None:
                chatterbox_model.conds = cached_conds
                effective_prompt = None  # conds already set, skip prepare_conditionals
                logger.debug(f"Voice cache hit: {audio_prompt_path}")

        # Call the core model's generate method.
        # autocast promotes float32 inputs to bfloat16 to match T3/S3Gen weights,
        # keeping numerically sensitive ops (softmax, norms) in float32 automatically.
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=BF16_ENABLED):
            if loaded_model_type == "multilingual":
                wav_tensor = chatterbox_model.generate(
                    text=text,
                    language_id=language,
                    audio_prompt_path=effective_prompt,
                    temperature=temperature,
                    exaggeration=exaggeration,
                    cfg_weight=cfg_weight,
                )
            else:
                wav_tensor = chatterbox_model.generate(
                    text=text,
                    audio_prompt_path=effective_prompt,
                    temperature=temperature,
                    exaggeration=exaggeration,
                    cfg_weight=cfg_weight,
                )

        # Store conds in cache after first compute for this voice.
        if conds_key is not None and effective_prompt is not None:
            if chatterbox_model.conds is not None:
                _conds_cache_store(conds_key, chatterbox_model.conds)
                logger.debug(f"Cached voice conditionals for: {audio_prompt_path}")

        # The ChatterboxTTS.generate method already returns a CPU tensor.
        return wav_tensor, chatterbox_model.sr

    except Exception as e:
        logger.error(f"Error during TTS synthesis: {e}", exc_info=True)
        return None, None


def unload_model() -> bool:
    """
    Unloads the current model and releases all GPU memory.
    Does NOT reload the model - use reload_model() for that.

    Returns:
        bool: True if the model was unloaded successfully, False otherwise.
    """
    global chatterbox_model, MODEL_LOADED, model_device, loaded_model_type, loaded_model_class_name

    logger.info("Initiating model unload sequence...")

    # 1. Unload existing model
    if chatterbox_model is not None:
        logger.info("Unloading TTS model from memory...")
        del chatterbox_model
        chatterbox_model = None

    # 2. Reset state flags
    MODEL_LOADED = False
    model_device = None
    loaded_model_type = None
    loaded_model_class_name = None

    # 3. Force Python Garbage Collection
    gc.collect()
    logger.info("Python garbage collection completed.")

    # 4. Clear GPU Cache (CUDA)
    if torch.cuda.is_available():
        logger.info("Clearing CUDA cache...")
        torch.cuda.empty_cache()

    # 5. Clear GPU Cache (MPS - Apple Silicon)
    if torch.backends.mps.is_available():
        try:
            torch.mps.empty_cache()
            logger.info("Cleared MPS cache.")
        except AttributeError:
            logger.debug(
                "torch.mps.empty_cache() not available in this PyTorch version."
            )

    logger.info("Model unloaded and GPU memory released.")
    return True


def reload_model() -> bool:
    """
    Unloads the current model, clears GPU memory, and reloads the model
    based on the current configuration. Used for hot-swapping models
    without restarting the server process.

    Returns:
        bool: True if the new model loaded successfully, False otherwise.
    """
    global chatterbox_model, MODEL_LOADED, model_device, loaded_model_type, loaded_model_class_name, _conds_cache

    logger.info("Initiating model hot-swap/reload sequence...")

    # 1. Unload existing model
    if chatterbox_model is not None:
        logger.info("Unloading existing TTS model from memory...")
        del chatterbox_model
        chatterbox_model = None

    # 2. Reset state flags and clear voice cache (conds are model-specific)
    MODEL_LOADED = False
    loaded_model_type = None
    loaded_model_class_name = None
    with _conds_cache_lock:
        _conds_cache.clear()
    logger.info("Voice conditioning cache cleared.")

    # 3. Force Python Garbage Collection
    gc.collect()
    logger.info("Python garbage collection completed.")

    # 4. Clear GPU Cache (CUDA)
    if torch.cuda.is_available():
        logger.info("Clearing CUDA cache...")
        torch.cuda.empty_cache()

    # 5. Clear GPU Cache (MPS - Apple Silicon)
    if torch.backends.mps.is_available():
        try:
            torch.mps.empty_cache()
            logger.info("Cleared MPS cache.")
        except AttributeError:
            # Older PyTorch versions may not have mps.empty_cache()
            logger.debug(
                "torch.mps.empty_cache() not available in this PyTorch version."
            )

    # 6. Reload model from the (now updated) configuration
    logger.info("Memory cleared. Reloading model from updated config...")
    return load_model()


# --- End File: engine.py ---
