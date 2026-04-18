# utils.py
# Utility functions for the TTS server application.
# This module includes functions for audio processing, text manipulation,
# file system operations, and performance monitoring.

import os
import logging
import re
import time
import io
import uuid
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, Set, List
from pydub import AudioSegment

import numpy as np
import soundfile as sf
import torchaudio  # For saving PyTorch tensors and potentially speed adjustment.
import torch

# Configuration manager to get paths dynamically.
# Assumes config.py and its config_manager are in the same directory or accessible via PYTHONPATH.
from config import get_predefined_voices_path, get_reference_audio_path, config_manager

# Optional import for librosa (for audio resampling, e.g., Opus encoding and time stretching)
try:
    import librosa

    LIBROSA_AVAILABLE = True
    logger = logging.getLogger(
        __name__
    )  # Initialize logger here if librosa is available
    logger.info(
        "Librosa library found and will be used for audio resampling and time stretching."
    )
except ImportError:
    LIBROSA_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(
        "Librosa library not found. Advanced audio resampling features (e.g., for Opus encoding) "
        "and pitch-preserving speed adjustment will be limited. Speed adjustment will fall back to basic method if enabled."
    )

# Optional import for Parselmouth (for unvoiced segment detection)
try:
    import parselmouth

    PARSELMOUTH_AVAILABLE = True
    logger.info(
        "Parselmouth library found and will be used for unvoiced segment removal if enabled."
    )
except ImportError:
    PARSELMOUTH_AVAILABLE = False
    logger.warning(
        "Parselmouth library not found. Unvoiced segment removal feature will be disabled."
    )


# --- Filename Sanitization ---

def validate_safe_path(base_dir: Path, filename: str) -> Path:
    """
    Validate that a user-supplied filename resolves to a path within base_dir.
    Raises ValueError if the resolved path escapes the base directory.
    """
    if not filename:
        raise ValueError("Filename must not be empty.")
    # Reject any path separators (both Unix and Windows style)
    if '/' in filename or '\\' in filename:
        raise ValueError(f"Invalid filename: {filename!r}")
    # Use only the basename to strip any directory components
    safe_name = Path(filename).name
    if not safe_name or safe_name != filename or safe_name in ('.', '..'):
        raise ValueError(f"Invalid filename: {filename!r}")
    resolved = (base_dir / safe_name).resolve()
    base_resolved = base_dir.resolve()
    if not str(resolved).startswith(str(base_resolved) + os.sep) and resolved != base_resolved:
        raise ValueError(f"Path escapes base directory: {filename!r}")
    return resolved

def sanitize_filename(filename: str) -> str:
    """
    Removes potentially unsafe characters and path components from a filename
    to make it safe for use in file paths. Replaces unsafe sequences with underscores.

    Args:
        filename: The original filename string.

    Returns:
        A sanitized filename string, ensuring it's not empty and reasonably short.
    """
    if not filename:
        # Generate a unique name if the input is empty.
        return f"unnamed_file_{uuid.uuid4().hex[:8]}"

    # Remove directory separators and leading/trailing whitespace.
    base_filename = Path(filename).name.strip()
    if not base_filename:
        return f"empty_basename_{uuid.uuid4().hex[:8]}"

    # Define a set of allowed characters (alphanumeric, underscore, hyphen, dot, space).
    # Spaces will be replaced by underscores later.
    safe_chars = set(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- "
    )
    sanitized_list = []
    last_char_was_underscore = False

    for char in base_filename:
        if char in safe_chars:
            # Replace spaces with underscores.
            sanitized_list.append("_" if char == " " else char)
            last_char_was_underscore = char == " "
        elif not last_char_was_underscore:
            # Replace any disallowed character sequence with a single underscore.
            sanitized_list.append("_")
            last_char_was_underscore = True

    sanitized = "".join(sanitized_list).strip("_")

    # Prevent names starting with multiple dots or consisting only of dots/underscores.
    if not sanitized or sanitized.lstrip("._") == "":
        return f"sanitized_file_{uuid.uuid4().hex[:8]}"

    # Limit filename length (e.g., 100 characters), preserving the extension.
    max_len = 100
    if len(sanitized) > max_len:
        name_part, ext_part = os.path.splitext(sanitized)
        # Ensure extension is not overly long itself; common extensions are short.
        ext_part = ext_part[:10]  # Limit extension length just in case.
        name_part = name_part[
            : max_len - len(ext_part) - 1
        ]  # -1 for the dot if ext exists
        sanitized = name_part + ext_part
        logger.warning(
            f"Original filename '{base_filename}' was truncated to '{sanitized}' due to length limits."
        )

    if not sanitized:  # Should not happen with previous checks, but as a failsafe.
        return f"final_fallback_name_{uuid.uuid4().hex[:8]}"

    return sanitized


# --- Constants for Text Processing ---
# Set of common abbreviations to help with sentence splitting.
ABBREVIATIONS: Set[str] = {
    "mr.",
    "mrs.",
    "ms.",
    "dr.",
    "prof.",
    "rev.",
    "hon.",
    "st.",
    "etc.",
    "e.g.",
    "i.e.",
    "vs.",
    "approx.",
    "apt.",
    "dept.",
    "fig.",
    "gen.",
    "gov.",
    "inc.",
    "jr.",
    "sr.",
    "ltd.",
    "no.",
    "p.",
    "pp.",
    "vol.",
    "op.",
    "cit.",
    "ca.",
    "cf.",
    "ed.",
    "esp.",
    "et.",
    "al.",
    "ibid.",
    "id.",
    "inf.",
    "sup.",
    "viz.",
    "sc.",
    "fl.",
    "d.",
    "b.",
    "r.",
    "c.",
    "v.",
    "u.s.",
    "u.k.",
    "a.m.",
    "p.m.",
    "a.d.",
    "b.c.",
}

# Common titles that might appear without a period if cleaned by other means first.
TITLES_NO_PERIOD: Set[str] = {
    "mr",
    "mrs",
    "ms",
    "dr",
    "prof",
    "rev",
    "hon",
    "st",
    "sgt",
    "capt",
    "lt",
    "col",
    "gen",
}

# Regex patterns (pre-compiled for efficiency in text processing).
NUMBER_DOT_NUMBER_PATTERN = re.compile(
    r"(?<!\d\.)\d*\.\d+"
)  # Matches numbers like 3.14, .5, 123.456
VERSION_PATTERN = re.compile(
    r"[vV]?\d+(\.\d+)+"
)  # Matches version numbers like v1.0.2, 2.3.4
# Pattern to find potential sentence endings (punctuation followed by quote/space/end of string).
POTENTIAL_END_PATTERN = re.compile(r'([.!?])(["\']?)(\s+|$)')
# Pattern to detect start-of-line bullet points or numbered lists.
BULLET_POINT_PATTERN = re.compile(r"(?:^|\n)\s*([-•*]|\d+\.)\s+")
# Placeholder for non-verbal cues or special instructions within text (e.g., (laughs), (sighs)).
NON_VERBAL_CUE_PATTERN = re.compile(r"(\([\w\s'-]+\))")


# --- Audio Processing Utilities ---
def encode_audio(
    audio_array: np.ndarray,
    sample_rate: int,
    output_format: str = "opus",
    target_sample_rate: Optional[int] = None,
) -> Optional[bytes]:
    """
    Encodes a NumPy audio array into the specified format (Opus or WAV) in memory.
    Can resample the audio to a target sample rate before encoding if specified.

    Args:
        audio_array: NumPy array containing audio data (expected as float32, range [-1, 1]).
        sample_rate: Sample rate of the input audio data.
        output_format: Desired output format ('opus', 'wav' or 'mp3').
        target_sample_rate: Optional target sample rate to resample to before encoding.

    Returns:
        Bytes object containing the encoded audio, or None if encoding fails.
    """
    if audio_array is None or audio_array.size == 0:
        logger.warning("encode_audio received empty or None audio array.")
        return None

    # Ensure audio is float32 for consistent processing.
    if audio_array.dtype != np.float32:
        if np.issubdtype(audio_array.dtype, np.integer):
            max_val = np.iinfo(audio_array.dtype).max
            audio_array = audio_array.astype(np.float32) / max_val
        else:  # Fallback for other types, assuming they might be float64 or similar
            audio_array = audio_array.astype(np.float32)
        logger.debug(f"Converted audio array to float32 for encoding.")

    # Ensure audio is mono if it's (samples, 1)
    if audio_array.ndim == 2 and audio_array.shape[1] == 1:
        audio_array = audio_array.squeeze(axis=1)
        logger.debug(
            "Squeezed audio array from (samples, 1) to (samples,) for encoding."
        )
    elif (
        audio_array.ndim > 1
    ):  # Multi-channel not directly supported by simple encoding path, attempt to take first channel
        logger.warning(
            f"Multi-channel audio (shape: {audio_array.shape}) provided to encode_audio. Using only the first channel."
        )
        audio_array = audio_array[:, 0]

    # Resample if target_sample_rate is provided and different from current sample_rate
    if (
        target_sample_rate is not None
        and target_sample_rate != sample_rate
        and LIBROSA_AVAILABLE
    ):
        try:
            logger.info(
                f"Resampling audio from {sample_rate}Hz to {target_sample_rate}Hz using Librosa."
            )
            audio_array = librosa.resample(
                y=audio_array, orig_sr=sample_rate, target_sr=target_sample_rate
            )
            sample_rate = (
                target_sample_rate  # Update sample_rate for subsequent encoding
            )
        except Exception as e_resample:
            logger.error(
                f"Error resampling audio to {target_sample_rate}Hz: {e_resample}. Proceeding with original sample rate {sample_rate}.",
                exc_info=True,
            )
    elif target_sample_rate is not None and target_sample_rate != sample_rate:
        logger.warning(
            f"Librosa not available. Cannot resample audio from {sample_rate}Hz to {target_sample_rate}Hz. "
            f"Proceeding with original sample rate for encoding."
        )

    start_time = time.time()
    output_buffer = io.BytesIO()

    try:
        audio_to_write = audio_array
        rate_to_write = sample_rate

        if output_format == "opus":
            OPUS_SUPPORTED_RATES = {8000, 12000, 16000, 24000, 48000}
            TARGET_OPUS_RATE = 48000  # Preferred Opus rate.

            if rate_to_write not in OPUS_SUPPORTED_RATES:
                if LIBROSA_AVAILABLE:
                    logger.warning(
                        f"Current sample rate {rate_to_write}Hz not directly supported by Opus. "
                        f"Resampling to {TARGET_OPUS_RATE}Hz using Librosa for Opus encoding."
                    )
                    audio_to_write = librosa.resample(
                        y=audio_array, orig_sr=rate_to_write, target_sr=TARGET_OPUS_RATE
                    )
                    rate_to_write = TARGET_OPUS_RATE
                else:
                    logger.error(
                        f"Librosa not available. Cannot resample audio from {rate_to_write}Hz for Opus encoding. "
                        f"Opus encoding may fail or produce poor quality."
                    )
                    # Proceed with current rate, soundfile might handle it or fail.
            sf.write(
                output_buffer,
                audio_to_write,
                rate_to_write,
                format="ogg",
                subtype="opus",
            )

        elif output_format == "wav":
            # WAV typically uses int16 for broader compatibility.
            # Clip audio to [-1.0, 1.0] before converting to int16 to prevent overflow.
            audio_clipped = np.clip(audio_array, -1.0, 1.0)
            audio_int16 = (audio_clipped * 32767).astype(np.int16)
            audio_to_write = audio_int16  # Use the int16 version for WAV
            sf.write(
                output_buffer,
                audio_to_write,
                rate_to_write,
                format="wav",
                subtype="pcm_16",
            )

        elif output_format == "mp3":
            audio_clipped = np.clip(audio_array, -1.0, 1.0)
            audio_int16 = (audio_clipped * 32767).astype(np.int16)
            audio_segment = AudioSegment(
            audio_int16.tobytes(),
            frame_rate=sample_rate,
            sample_width=2,
            channels=1,
            )
            audio_segment.export(output_buffer, format="mp3")

        else:
            logger.error(
                f"Unsupported output format requested for encoding: {output_format}"
            )
            return None

        encoded_bytes = output_buffer.getvalue()
        end_time = time.time()
        logger.info(
            f"Encoded {len(encoded_bytes)} bytes to '{output_format}' at {rate_to_write}Hz in {end_time - start_time:.3f} seconds."
        )
        return encoded_bytes

    except ImportError as ie_sf:  # Specifically for soundfile import issues
        logger.critical(
            f"The 'soundfile' library or its dependency (libsndfile) is not installed or found. "
            f"Audio encoding/saving is not possible. Please install it. Error: {ie_sf}"
        )
        return None
    except Exception as e:
        logger.error(f"Error encoding audio to '{output_format}': {e}", exc_info=True)
        return None


def save_audio_to_file(
    audio_array: np.ndarray, sample_rate: int, file_path_str: str
) -> bool:
    """
    Saves a NumPy audio array to a WAV file.

    Args:
        audio_array: NumPy array containing audio data (float32, range [-1, 1]).
        sample_rate: Sample rate of the audio data.
        file_path_str: String path to save the WAV file.

    Returns:
        True if saving was successful, False otherwise.
    """
    if audio_array is None or audio_array.size == 0:
        logger.warning("save_audio_to_file received empty or None audio array.")
        return False

    file_path = Path(file_path_str)
    if file_path.suffix.lower() != ".wav":
        logger.warning(
            f"File path '{file_path_str}' does not end with .wav. Appending .wav extension."
        )
        file_path = file_path.with_suffix(".wav")

    start_time = time.time()
    try:
        # Ensure output directory exists.
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Prepare audio for WAV (int16, clipped).
        if (
            audio_array.dtype != np.float32
        ):  # Ensure float32 before potential scaling to int16
            if np.issubdtype(audio_array.dtype, np.integer):
                max_val = np.iinfo(audio_array.dtype).max
                audio_array = audio_array.astype(np.float32) / max_val
            else:
                audio_array = audio_array.astype(np.float32)

        audio_clipped = np.clip(audio_array, -1.0, 1.0)
        audio_int16 = (audio_clipped * 32767).astype(np.int16)

        sf.write(
            str(file_path), audio_int16, sample_rate, format="wav", subtype="pcm_16"
        )
        end_time = time.time()
        logger.info(
            f"Saved WAV file to {file_path} in {end_time - start_time:.3f} seconds."
        )
        return True
    except ImportError:
        logger.critical("SoundFile library not found. Cannot save audio.")
        return False
    except Exception as e:
        logger.error(f"Error saving WAV file to {file_path}: {e}", exc_info=True)
        return False


def save_audio_tensor_to_file(
    audio_tensor: torch.Tensor,
    sample_rate: int,
    file_path_str: str,
    output_format: str = "wav",
) -> bool:
    """
    Saves a PyTorch audio tensor to a file using torchaudio.

    Args:
        audio_tensor: PyTorch tensor containing audio data.
        sample_rate: Sample rate of the audio data.
        file_path_str: String path to save the audio file.
        output_format: Desired output format (passed to torchaudio.save).

    Returns:
        True if saving was successful, False otherwise.
    """
    if audio_tensor is None or audio_tensor.numel() == 0:
        logger.warning("save_audio_tensor_to_file received empty or None audio tensor.")
        return False

    file_path = Path(file_path_str)
    start_time = time.time()
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # torchaudio.save expects tensor on CPU.
        audio_tensor_cpu = audio_tensor.cpu()
        # Ensure tensor is 2D (channels, samples) for torchaudio.save.
        if audio_tensor_cpu.ndim == 1:
            audio_tensor_cpu = audio_tensor_cpu.unsqueeze(0)

        torchaudio.save(
            str(file_path), audio_tensor_cpu, sample_rate, format=output_format
        )
        end_time = time.time()
        logger.info(
            f"Saved audio tensor to {file_path} (format: {output_format}) in {end_time - start_time:.3f} seconds."
        )
        return True
    except Exception as e:
        logger.error(f"Error saving audio tensor to {file_path}: {e}", exc_info=True)
        return False


# --- Audio Manipulation Utilities ---
def apply_speed_factor(
    audio_tensor: torch.Tensor, sample_rate: int, speed_factor: float
) -> Tuple[torch.Tensor, int]:
    """
    Applies a speed factor to an audio tensor.
    Uses librosa.effects.time_stretch if available for pitch preservation.
    Falls back to simple resampling via torchaudio.transforms.Resample if librosa is not available,
    which will alter pitch.

    Args:
        audio_tensor: Input audio waveform (PyTorch tensor, expected mono).
        sample_rate: Sample rate of the input audio.
        speed_factor: Desired speed factor (e.g., 1.0 is normal, 1.5 is faster, 0.5 is slower).

    Returns:
        A tuple of the speed-adjusted audio tensor and its sample rate (which remains unchanged).
        Returns the original tensor and sample rate if speed_factor is 1.0 or if adjustment fails.
    """
    if speed_factor == 1.0:
        return audio_tensor, sample_rate
    if speed_factor <= 0:
        logger.warning(
            f"Invalid speed_factor {speed_factor}. Must be positive. Returning original audio."
        )
        return audio_tensor, sample_rate

    audio_tensor_cpu = audio_tensor.cpu()
    # Ensure tensor is 1D mono for librosa and consistent handling
    if audio_tensor_cpu.ndim == 2:
        if audio_tensor_cpu.shape[0] == 1:
            audio_tensor_cpu = audio_tensor_cpu.squeeze(0)
        elif audio_tensor_cpu.shape[1] == 1:
            audio_tensor_cpu = audio_tensor_cpu.squeeze(1)
        else:  # True stereo or multi-channel
            logger.warning(
                f"apply_speed_factor received multi-channel audio (shape {audio_tensor_cpu.shape}). Using first channel only."
            )
            audio_tensor_cpu = audio_tensor_cpu[0, :]

    if audio_tensor_cpu.ndim != 1:
        logger.error(
            f"apply_speed_factor: audio_tensor_cpu is not 1D after processing (shape {audio_tensor_cpu.shape}). Returning original audio."
        )
        return audio_tensor, sample_rate

    if LIBROSA_AVAILABLE:
        try:
            audio_np = audio_tensor_cpu.numpy()
            # librosa.effects.time_stretch changes duration, not sample rate directly.
            # The 'rate' parameter in time_stretch is equivalent to speed_factor.
            stretched_audio_np = librosa.effects.time_stretch(
                y=audio_np, rate=speed_factor
            )
            speed_adjusted_tensor = torch.from_numpy(stretched_audio_np)
            logger.info(
                f"Applied speed factor {speed_factor} using librosa.effects.time_stretch. Original SR: {sample_rate}"
            )
            return speed_adjusted_tensor, sample_rate  # Sample rate is preserved
        except Exception as e_librosa:
            logger.error(
                f"Failed to apply speed factor {speed_factor} using librosa: {e_librosa}. "
                f"Falling back to basic resampling (pitch will change).",
                exc_info=True,
            )
            # Fallback to simple resampling (changes pitch)
            try:
                new_sample_rate_for_speedup = int(sample_rate / speed_factor)
                resampler = torchaudio.transforms.Resample(
                    orig_freq=sample_rate, new_freq=new_sample_rate_for_speedup
                )
                # Resample to new_sample_rate_for_speedup to change duration, then resample back to original SR
                # This is effectively what sox 'speed' does, but 'tempo' is better (which librosa does)
                # For simplicity in fallback, just resample and note pitch change
                # To actually change speed without changing sample rate and preserving pitch using *only* torchaudio is more complex
                # and typically involves phase vocoder or similar, which is beyond a simple fallback.
                # The torchaudio.functional.pitch_shift and then torchaudio.functional.speed is one way,
                # but librosa is simpler.
                # Given the instruction "Fallback to original audio" if librosa not available or fails, we'll stick to that.
                # Original plan: "If Librosa is not available, log a warning and return the original audio"
                logger.warning(
                    f"Librosa failed for speed factor. Returning original audio as primary fallback."
                )
                return audio_tensor, sample_rate

            except Exception as e_resample_fallback:
                logger.error(
                    f"Fallback resampling for speed factor {speed_factor} also failed: {e_resample_fallback}. Returning original audio.",
                    exc_info=True,
                )
                return audio_tensor, sample_rate

    else:  # Librosa not available
        logger.warning(
            f"Librosa not available for pitch-preserving speed adjustment (factor: {speed_factor}). "
            f"Returning original audio. Install librosa for this feature."
        )
        return audio_tensor, sample_rate


def trim_lead_trail_silence(
    audio_array: np.ndarray,
    sample_rate: int,
    silence_threshold_db: float = -40.0,
    min_silence_duration_ms: int = 100,
    padding_ms: int = 50,
) -> np.ndarray:
    """
    Trims silence from the beginning and end of a NumPy audio array using a dB threshold.

    Args:
        audio_array: NumPy array (float32) of the audio.
        sample_rate: Sample rate of the audio.
        silence_threshold_db: Silence threshold in dBFS. Segments below this are considered silent.
        min_silence_duration_ms: Minimum duration of silence to be trimmed (ms).
        padding_ms: Padding to leave at the start/end after trimming (ms).

    Returns:
        Trimmed NumPy audio array. Returns original if no significant silence is found or on error.
    """
    if audio_array is None or audio_array.size == 0:
        return audio_array

    try:
        if not LIBROSA_AVAILABLE:
            logger.warning("Librosa not available, skipping silence trimming.")
            return audio_array

        top_db_threshold = abs(silence_threshold_db)

        frame_length = 2048
        hop_length = 512

        trimmed_audio, index = librosa.effects.trim(
            y=audio_array,
            top_db=top_db_threshold,
            frame_length=frame_length,
            hop_length=hop_length,
        )

        start_sample, end_sample = index[0], index[1]

        padding_samples = int((padding_ms / 1000.0) * sample_rate)
        final_start = max(0, start_sample - padding_samples)
        final_end = min(len(audio_array), end_sample + padding_samples)

        if final_end > final_start:  # Ensure the slice is valid
            # Check if significant trimming occurred
            original_length = len(audio_array)
            trimmed_length_with_padding = final_end - final_start
            # Heuristic: if length changed by more than just padding, or if original silence was more than min_duration
            # For simplicity, if librosa.effects.trim found *any* indices different from [0, original_length],
            # it means some trimming potential was identified.
            if index[0] > 0 or index[1] < original_length:
                logger.debug(
                    f"Silence trimmed: original samples {original_length}, new effective samples {trimmed_length_with_padding} (indices before padding: {index})"
                )
                return audio_array[final_start:final_end]

        logger.debug(
            "No significant leading/trailing silence found to trim, or result would be empty."
        )
        return audio_array

    except Exception as e:
        logger.error(f"Error during silence trimming: {e}", exc_info=True)
        return audio_array


def fix_internal_silence(
    audio_array: np.ndarray,
    sample_rate: int,
    silence_threshold_db: float = -40.0,
    min_silence_to_fix_ms: int = 700,
    max_allowed_silence_ms: int = 300,
) -> np.ndarray:
    """
    Reduces long internal silences in a NumPy audio array to a specified maximum duration.
    Uses Librosa to split by silence.

    Args:
        audio_array: NumPy array (float32) of the audio.
        sample_rate: Sample rate of the audio.
        silence_threshold_db: Silence threshold in dBFS.
        min_silence_to_fix_ms: Minimum duration of an internal silence to be shortened (ms).
        max_allowed_silence_ms: Target maximum duration for long silences (ms).

    Returns:
        NumPy audio array with long internal silences shortened. Original if no fix needed or on error.
    """
    if audio_array is None or audio_array.size == 0:
        return audio_array

    try:
        if not LIBROSA_AVAILABLE:
            logger.warning("Librosa not available, skipping internal silence fixing.")
            return audio_array

        top_db_threshold = abs(silence_threshold_db)
        min_silence_len_samples = int((min_silence_to_fix_ms / 1000.0) * sample_rate)
        max_silence_samples_to_keep = int(
            (max_allowed_silence_ms / 1000.0) * sample_rate
        )

        non_silent_intervals = librosa.effects.split(
            y=audio_array,
            top_db=top_db_threshold,
            frame_length=2048,  # Can be tuned
            hop_length=512,  # Can be tuned
        )

        if len(non_silent_intervals) <= 1:
            logger.debug("No significant internal silences found to fix.")
            return audio_array

        fixed_audio_parts = []
        last_nonsilent_end = 0

        for i, (start_sample, end_sample) in enumerate(non_silent_intervals):
            silence_duration_samples = start_sample - last_nonsilent_end
            if silence_duration_samples > 0:
                if silence_duration_samples >= min_silence_len_samples:
                    silence_to_add = audio_array[
                        last_nonsilent_end : last_nonsilent_end
                        + max_silence_samples_to_keep
                    ]
                    fixed_audio_parts.append(silence_to_add)
                    logger.debug(
                        f"Shortened internal silence from {silence_duration_samples} to {max_silence_samples_to_keep} samples."
                    )
                else:
                    fixed_audio_parts.append(
                        audio_array[last_nonsilent_end:start_sample]
                    )
            fixed_audio_parts.append(audio_array[start_sample:end_sample])
            last_nonsilent_end = end_sample

        # Handle potential silence after the very last non-silent segment
        # This part is tricky as librosa.effects.split only gives non-silent parts.
        # The trim_lead_trail_silence should handle overall trailing silence.
        # This function focuses on *between* non-silent segments.
        if last_nonsilent_end < len(audio_array):
            trailing_segment = audio_array[last_nonsilent_end:]
            # Check if this trailing segment is mostly silence and long enough to shorten
            # For simplicity, we'll assume trim_lead_trail_silence handles the very end.
            # Or, we could append it if it's short, or shorten it if it's long silence.
            # To avoid over-complication here, let's just append what's left.
            # The primary goal is internal silences.
            # However, if the last "non_silent_interval" was short and followed by a long silence,
            # that silence needs to be handled here too.
            silence_duration_samples = len(audio_array) - last_nonsilent_end
            if silence_duration_samples > 0:
                if silence_duration_samples >= min_silence_len_samples:
                    fixed_audio_parts.append(
                        audio_array[
                            last_nonsilent_end : last_nonsilent_end
                            + max_silence_samples_to_keep
                        ]
                    )
                    logger.debug(
                        f"Shortened trailing silence from {silence_duration_samples} to {max_silence_samples_to_keep} samples."
                    )
                else:
                    fixed_audio_parts.append(trailing_segment)

        if not fixed_audio_parts:  # Should not happen if non_silent_intervals > 1
            logger.warning(
                "Internal silence fixing resulted in no audio parts; returning original."
            )
            return audio_array

        return np.concatenate(fixed_audio_parts)

    except Exception as e:
        logger.error(f"Error during internal silence fixing: {e}", exc_info=True)
        return audio_array


def remove_long_unvoiced_segments(
    audio_array: np.ndarray,
    sample_rate: int,
    min_unvoiced_duration_ms: int = 300,
    pitch_floor: float = 75.0,
    pitch_ceiling: float = 600.0,
) -> np.ndarray:
    """
    Removes segments from a NumPy audio array that are unvoiced for longer than
    the specified duration, using Parselmouth for pitch analysis.

    Args:
        audio_array: NumPy array (float32) of the audio.
        sample_rate: Sample rate of the audio.
        min_unvoiced_duration_ms: Minimum duration (ms) of an unvoiced segment to be removed.
        pitch_floor: Minimum pitch (Hz) to consider for voicing.
        pitch_ceiling: Maximum pitch (Hz) to consider for voicing.

    Returns:
        NumPy audio array with long unvoiced segments removed. Original if Parselmouth not available or on error.
    """
    if not PARSELMOUTH_AVAILABLE:
        logger.warning("Parselmouth not available, skipping unvoiced segment removal.")
        return audio_array
    if audio_array is None or audio_array.size == 0:
        return audio_array

    try:
        sound = parselmouth.Sound(
            audio_array.astype(np.float64), sampling_frequency=sample_rate
        )
        pitch = sound.to_pitch(pitch_floor=pitch_floor, pitch_ceiling=pitch_ceiling)
        voiced_unvoiced = pitch.get_VoicedVoicelessUnvoiced()

        segments_to_keep = []
        current_segment_start_sample = 0
        min_unvoiced_samples = int((min_unvoiced_duration_ms / 1000.0) * sample_rate)

        for i in range(len(voiced_unvoiced.time_intervals)):
            interval_start_time, interval_end_time, is_voiced_str = (
                voiced_unvoiced.time_intervals[i]
            )
            is_voiced = is_voiced_str == "voiced"

            interval_start_sample = int(interval_start_time * sample_rate)
            interval_end_sample = int(interval_end_time * sample_rate)
            interval_duration_samples = interval_end_sample - interval_start_sample

            if is_voiced:
                segments_to_keep.append(
                    audio_array[current_segment_start_sample:interval_end_sample]
                )
                current_segment_start_sample = interval_end_sample
            else:  # Unvoiced segment
                if interval_duration_samples < min_unvoiced_samples:
                    segments_to_keep.append(
                        audio_array[current_segment_start_sample:interval_end_sample]
                    )
                    current_segment_start_sample = interval_end_sample
                else:
                    logger.debug(
                        f"Removing long unvoiced segment from {interval_start_time:.2f}s to {interval_end_time:.2f}s."
                    )
                    # Append the audio *before* this long unvoiced segment (if any)
                    if interval_start_sample > current_segment_start_sample:
                        segments_to_keep.append(
                            audio_array[
                                current_segment_start_sample:interval_start_sample
                            ]
                        )
                    current_segment_start_sample = interval_end_sample

        if current_segment_start_sample < len(audio_array):
            segments_to_keep.append(audio_array[current_segment_start_sample:])

        if not segments_to_keep:
            logger.warning(
                "Unvoiced segment removal resulted in empty audio; returning original."
            )
            return audio_array

        return np.concatenate(segments_to_keep)

    except Exception as e:
        logger.error(f"Error during unvoiced segment removal: {e}", exc_info=True)
        return audio_array


# --- Text Processing Utilities ---
def _is_valid_sentence_end(text: str, period_index: int) -> bool:
    """
    Checks if a period at a given index in the text is likely a valid sentence terminator,
    rather than part of an abbreviation, number, or version string.
    """
    word_start_before_period = period_index - 1
    scan_limit = max(0, period_index - 10)
    while (
        word_start_before_period >= scan_limit
        and not text[word_start_before_period].isspace()
    ):
        word_start_before_period -= 1
    word_before_period = text[word_start_before_period + 1 : period_index + 1].lower()
    if word_before_period in ABBREVIATIONS:
        return False

    context_start = max(0, period_index - 10)
    context_end = min(len(text), period_index + 10)
    context_segment = text[context_start:context_end]
    relative_period_index_in_context = period_index - context_start

    for pattern in [NUMBER_DOT_NUMBER_PATTERN, VERSION_PATTERN]:
        for match in pattern.finditer(context_segment):
            if match.start() <= relative_period_index_in_context < match.end():
                is_last_char_of_numeric_match = (
                    relative_period_index_in_context == match.end() - 1
                )
                is_followed_by_space_or_eos = (
                    period_index + 1 == len(text) or text[period_index + 1].isspace()
                )
                if not (is_last_char_of_numeric_match and is_followed_by_space_or_eos):
                    return False
    return True


def _split_text_by_punctuation(text: str) -> List[str]:
    """
    Splits text into sentences based on common punctuation marks (.!?),
    while trying to avoid splitting on periods used in abbreviations or numbers.
    """
    sentences: List[str] = []
    last_split_index = 0
    text_length = len(text)

    for match in POTENTIAL_END_PATTERN.finditer(text):
        punctuation_char_index = match.start(1)
        punctuation_char = text[punctuation_char_index]
        slice_end_after_punctuation = match.start(1) + 1 + len(match.group(2) or "")

        if punctuation_char in ["!", "?"]:
            current_sentence_text = text[
                last_split_index:slice_end_after_punctuation
            ].strip()
            if current_sentence_text:
                sentences.append(current_sentence_text)
            last_split_index = match.end()
            continue

        if punctuation_char == ".":
            if (
                punctuation_char_index > 0 and text[punctuation_char_index - 1] == "."
            ) or (
                punctuation_char_index < text_length - 1
                and text[punctuation_char_index + 1] == "."
            ):
                continue

            if _is_valid_sentence_end(text, punctuation_char_index):
                current_sentence_text = text[
                    last_split_index:slice_end_after_punctuation
                ].strip()
                if current_sentence_text:
                    sentences.append(current_sentence_text)
                last_split_index = match.end()

    remaining_text_segment = text[last_split_index:].strip()
    if remaining_text_segment:
        sentences.append(remaining_text_segment)

    sentences = [s for s in sentences if s]
    if not sentences and text.strip():
        return [text.strip()]
    return sentences


def split_into_sentences(text: str) -> List[str]:
    """
    Splits a given text into sentences. Handles normalization of line breaks
    and considers bullet points as potential sentence separators.
    This is the primary entry point for sentence splitting.
    """
    if not text or text.isspace():
        return []

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    bullet_point_matches = list(BULLET_POINT_PATTERN.finditer(text))

    if bullet_point_matches:
        logger.debug("Bullet points detected in text; splitting by bullet items.")
        processed_sentences: List[str] = []
        current_position = 0
        for i, bullet_match in enumerate(bullet_point_matches):
            bullet_actual_start_index = bullet_match.start()
            if i == 0 and bullet_actual_start_index > current_position:
                pre_bullet_segment = text[
                    current_position:bullet_actual_start_index
                ].strip()
                if pre_bullet_segment:
                    processed_sentences.extend(
                        s for s in _split_text_by_punctuation(pre_bullet_segment) if s
                    )

            next_bullet_start_index = (
                bullet_point_matches[i + 1].start()
                if i + 1 < len(bullet_point_matches)
                else len(text)
            )
            bullet_item_segment = text[
                bullet_actual_start_index:next_bullet_start_index
            ].strip()
            if bullet_item_segment:
                processed_sentences.append(bullet_item_segment)
            current_position = next_bullet_start_index

        if current_position < len(text):
            post_bullet_segment = text[current_position:].strip()
            if post_bullet_segment:
                processed_sentences.extend(
                    s for s in _split_text_by_punctuation(post_bullet_segment) if s
                )
        return [s for s in processed_sentences if s]
    else:
        logger.debug(
            "No bullet points detected; using punctuation-based sentence splitting."
        )
        return _split_text_by_punctuation(text)


def _preprocess_and_segment_text(full_text: str) -> List[Tuple[Optional[str], str]]:
    """
    Internal helper to segment text by non-verbal cues (e.g., (laughs)) and then
    further split those segments into sentences.
    Assigns a placeholder "tag" (here, None or empty string) as this system is single-speaker.
    The tuple structure (tag, sentence) is maintained for compatibility with chunking logic
    that might expect it, even if the tag itself isn't used for speaker differentiation.

    Args:
        full_text: The complete input text.

    Returns:
        A list of tuples, where each tuple is (placeholder_tag, sentence_text).
    """
    if not full_text or full_text.isspace():
        return []

    placeholder_tag: Optional[str] = None
    segmented_with_tags: List[Tuple[Optional[str], str]] = []
    parts_and_cues = NON_VERBAL_CUE_PATTERN.split(full_text)

    for part in parts_and_cues:
        if not part or part.isspace():
            continue
        if NON_VERBAL_CUE_PATTERN.fullmatch(part):
            segmented_with_tags.append((placeholder_tag, part.strip()))
        else:
            sentences_from_part = split_into_sentences(part.strip())
            for sentence in sentences_from_part:
                if sentence:
                    segmented_with_tags.append((placeholder_tag, sentence))

    if not segmented_with_tags and full_text.strip():
        segmented_with_tags.append((placeholder_tag, full_text.strip()))

    logger.debug(
        f"Preprocessed text into {len(segmented_with_tags)} segments/sentences."
    )
    return segmented_with_tags


def chunk_text_by_sentences(
    full_text: str,
    chunk_size: int,
) -> List[str]:
    """
    Chunks text into manageable pieces for TTS processing, respecting sentence boundaries
    and a maximum chunk character length. Designed for single-speaker text, but maintains
    a structure that can handle segments (like non-verbal cues) separately.

    Args:
        full_text: The complete text to be chunked.
        chunk_size: The desired maximum character length for each chunk.
                    Sentences longer than this will form their own chunk.

    Returns:
        A list of text chunks, ready for TTS.
    """
    if not full_text or full_text.isspace():
        return []
    if chunk_size <= 0:
        chunk_size = float("inf")

    processed_segments = _preprocess_and_segment_text(full_text)
    if not processed_segments:
        return []

    text_chunks: List[str] = []
    current_chunk_sentences: List[str] = []
    current_chunk_length = 0

    for (
        _,
        segment_text,
    ) in processed_segments:
        segment_len = len(segment_text)

        if not current_chunk_sentences:
            current_chunk_sentences.append(segment_text)
            current_chunk_length = segment_len
        elif current_chunk_length + 1 + segment_len <= chunk_size:
            current_chunk_sentences.append(segment_text)
            current_chunk_length += 1 + segment_len
        else:
            if current_chunk_sentences:
                text_chunks.append(" ".join(current_chunk_sentences))
            current_chunk_sentences = [segment_text]
            current_chunk_length = segment_len

        if current_chunk_length > chunk_size and len(current_chunk_sentences) == 1:
            logger.info(
                f"A single segment (length {current_chunk_length}) exceeds chunk_size {chunk_size}. "
                f"It will form its own chunk."
            )
            text_chunks.append(" ".join(current_chunk_sentences))
            current_chunk_sentences = []
            current_chunk_length = 0

    if current_chunk_sentences:
        text_chunks.append(" ".join(current_chunk_sentences))

    text_chunks = [chunk for chunk in text_chunks if chunk.strip()]

    if not text_chunks and full_text.strip():
        logger.warning(
            "Text chunking resulted in zero chunks despite non-empty input. Returning full text as one chunk."
        )
        return [full_text.strip()]

    logger.info(f"Text chunking complete. Generated {len(text_chunks)} chunk(s).")
    return text_chunks


# --- File System Utilities ---
def get_valid_reference_files() -> List[str]:
    """
    Scans the configured reference audio directory and returns a sorted list of
    valid audio filenames (.wav, .mp3).
    """
    ref_audio_dir_path = get_reference_audio_path()
    valid_files: List[str] = []
    allowed_extensions = (".wav", ".mp3")

    try:
        if ref_audio_dir_path.is_dir():
            for item in ref_audio_dir_path.iterdir():
                if (
                    item.is_file()
                    and not item.name.startswith(".")
                    and item.suffix.lower() in allowed_extensions
                ):
                    valid_files.append(item.name)
        else:
            logger.warning(
                f"Reference audio directory not found: {ref_audio_dir_path}. Creating it."
            )
            ref_audio_dir_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(
            f"Error reading reference audio directory '{ref_audio_dir_path}': {e}",
            exc_info=True,
        )
    return sorted(valid_files)


def get_predefined_voices() -> List[Dict[str, str]]:
    """
    Scans the configured predefined voices directory, formats their display names,
    and returns a sorted list of voice dictionaries. Handles duplicate base names.

    Returns:
        List of dictionaries: [{"display_name": "Formatted Name", "filename": "original_file.wav"}, ...]
    """
    voices_dir_path = get_predefined_voices_path()
    predefined_voice_list: List[Dict[str, str]] = []
    allowed_extensions = (".wav", ".mp3")

    try:
        if not voices_dir_path.is_dir():
            logger.warning(
                f"Predefined voices directory not found: {voices_dir_path}. Creating it."
            )
            voices_dir_path.mkdir(parents=True, exist_ok=True)
            return []

        temp_voice_info_list = []
        for item in voices_dir_path.iterdir():
            if (
                item.is_file()
                and not item.name.startswith(".")
                and item.suffix.lower() in allowed_extensions
            ):
                base_name = item.stem
                formatted_display_name = base_name.replace("_", " ").replace("-", " ")
                formatted_display_name = " ".join(
                    word.capitalize() for word in formatted_display_name.split()
                )
                if not formatted_display_name:
                    formatted_display_name = base_name

                temp_voice_info_list.append(
                    {
                        "original_filename": item.name,
                        "display_name_base": formatted_display_name,
                    }
                )

        temp_voice_info_list.sort(key=lambda x: x["display_name_base"].lower())
        display_name_counts: Dict[str, int] = {}

        for voice_info in temp_voice_info_list:
            base_display = voice_info["display_name_base"]
            final_display_name = base_display
            if base_display in display_name_counts:
                display_name_counts[base_display] += 1
                final_display_name = (
                    f"{base_display} ({display_name_counts[base_display]})"
                )
            else:
                display_name_counts[base_display] = 1

            predefined_voice_list.append(
                {
                    "display_name": final_display_name,
                    "filename": voice_info["original_filename"],
                }
            )

        predefined_voice_list.sort(key=lambda x: x["display_name"].lower())
        logger.info(
            f"Found {len(predefined_voice_list)} predefined voices in {voices_dir_path}"
        )

    except Exception as e:
        logger.error(
            f"Error reading predefined voices directory '{voices_dir_path}': {e}",
            exc_info=True,
        )
        predefined_voice_list = []
    return predefined_voice_list


def validate_reference_audio(
    file_path: Path, max_duration_sec: Optional[int] = None
) -> Tuple[bool, str]:
    """
    Validates a reference audio file. Checks for existence, valid audio type (WAV/MP3),
    and optionally enforces a maximum duration.

    Args:
        file_path: Path object for the reference audio file.
        max_duration_sec: Optional maximum duration in seconds. If None, duration is not checked.

    Returns:
        A tuple (is_valid: bool, message: str).
    """
    if not file_path.exists() or not file_path.is_file():
        return False, f"Reference audio file not found at: {file_path}"

    if file_path.suffix.lower() not in [".wav", ".mp3"]:
        return False, "Invalid reference audio file type. Please use WAV or MP3 format."

    if max_duration_sec is not None and max_duration_sec > 0:
        try:
            audio_info = sf.info(str(file_path))
            duration = audio_info.duration
            if duration <= 0:
                return (
                    False,
                    f"Reference audio file '{file_path.name}' has zero or negative duration.",
                )
            if duration > max_duration_sec:
                return (
                    False,
                    f"Reference audio duration ({duration:.2f}s) exceeds maximum allowed ({max_duration_sec}s).",
                )
        except Exception as e:
            logger.warning(
                f"Could not accurately determine duration of reference audio '{file_path.name}': {e}. "
                f"Skipping duration check for this file."
            )
    return True, "Reference audio appears valid."


# --- Performance Monitoring Utility ---
class PerformanceMonitor:
    """
    A simple helper class for recording and reporting elapsed time for different
    stages of an operation. Useful for debugging performance bottlenecks.
    """

    def __init__(
        self, enabled: bool = True, logger_instance: Optional[logging.Logger] = None
    ):
        self.enabled: bool = enabled
        self.logger = (
            logger_instance
            if logger_instance is not None
            else logging.getLogger(__name__)
        )
        self.start_time: float = 0.0
        self.events: List[Tuple[str, float]] = []
        if self.enabled:
            self.start_time = time.monotonic()
            self.events.append(("Monitoring Started", self.start_time))

    def record(self, event_name: str):
        if not self.enabled:
            return
        self.events.append((event_name, time.monotonic()))

    def report(self, log_level: int = logging.DEBUG) -> str:
        if not self.enabled or not self.events:
            return "Performance monitoring was disabled or no events recorded."

        report_lines = ["Performance Report:"]
        last_event_time = self.events[0][1]

        for i in range(1, len(self.events)):
            event_name, timestamp = self.events[i]
            prev_event_name, _ = self.events[i - 1]
            duration_since_last = timestamp - last_event_time
            duration_since_start = timestamp - self.start_time
            report_lines.append(
                f"  - Event: '{event_name}' (after '{prev_event_name}') "
                f"took {duration_since_last:.4f}s. Total elapsed: {duration_since_start:.4f}s"
            )
            last_event_time = timestamp

        total_duration = self.events[-1][1] - self.start_time
        report_lines.append(f"Total Monitored Duration: {total_duration:.4f}s")
        full_report_str = "\n".join(report_lines)

        if self.logger:
            self.logger.log(log_level, full_report_str)
        return full_report_str
