# File: models.py
# Pydantic models for API request and response validation.

from typing import Optional, Literal
from pydantic import BaseModel, Field


class GenerationParams(BaseModel):
    """Common parameters for TTS generation."""

    temperature: Optional[float] = Field(
        None,  # Defaulting to None means server will use config default if not provided
        ge=0.0,
        le=1.5,  # Based on Chatterbox Gradio app for temperature
        description="Controls randomness. Lower is more deterministic. (Range: 0.0-1.5)",
    )
    exaggeration: Optional[float] = Field(
        None,
        ge=0.5,  # Based on Chatterbox tutorial notebook
        le=3.0,  # Based on Chatterbox tutorial notebook
        description="Controls expressiveness/exaggeration. Lower values are more subdued/calm, higher values are more dramatic/energetic. (Range: 0.5-3.0)",
    )
    cfg_weight: Optional[float] = Field(
        None,
        ge=0.2,  # Based on Chatterbox Gradio app
        le=1.0,  # Based on Chatterbox Gradio app
        description="Classifier-Free Guidance weight. Influences adherence to prompt/style and pacing. (Range: 0.2-1.0)",
    )
    seed: Optional[int] = Field(
        None,
        ge=0,  # Seed should be non-negative, 0 often implies random.
        description="Seed for generation. 0 may indicate random behavior based on engine.",
    )
    speed_factor: Optional[float] = Field(
        None,
        ge=0.25,
        le=4.0,
        description="Speed factor for the generated audio. 1.0 is normal speed. Applied post-generation.",
    )
    language: Optional[str] = Field(
        None,
        description="Language of the text. (Primarily for UI, actual engine may infer)",
    )


class CustomTTSRequest(BaseModel):
    """Request model for the custom /tts endpoint."""

    text: str = Field(..., min_length=1, description="Text to be synthesized.")

    voice_mode: Literal["predefined", "clone"] = Field(
        "predefined",  # Default voice mode
        description="Voice mode: 'predefined' for a built-in voice, 'clone' for voice cloning using a reference audio.",
    )
    predefined_voice_id: Optional[str] = Field(
        None,
        description="Filename of the predefined voice to use (e.g., 'default_sample.wav'). Required if voice_mode is 'predefined'.",
    )
    reference_audio_filename: Optional[str] = Field(
        None,
        description="Filename of a user-uploaded reference audio for voice cloning. Required if voice_mode is 'clone'.",
    )

    output_format: Optional[Literal["wav", "opus", "mp3"]] = Field(  # Added "mp3"
        "wav", description="Desired audio output format."  # Default output format
    )

    split_text: Optional[bool] = Field(
        True,  # Default to splitting enabled
        description="Whether to automatically split long text into chunks for processing.",
    )
    chunk_size: Optional[int] = Field(
        120,  # Default target chunk size from config
        ge=50,  # Minimum reasonable chunk size
        le=500,  # Maximum reasonable chunk size
        description="Approximate target character length for text chunks when splitting is enabled (50-500).",
    )

    # Embed generation parameters directly
    temperature: Optional[float] = Field(
        None, description="Overrides default temperature if provided."
    )
    exaggeration: Optional[float] = Field(
        None, description="Overrides default exaggeration if provided."
    )
    cfg_weight: Optional[float] = Field(
        None, description="Overrides default CFG weight if provided."
    )
    seed: Optional[int] = Field(None, description="Overrides default seed if provided.")
    speed_factor: Optional[float] = Field(
        None, description="Overrides default speed factor if provided."
    )
    language: Optional[str] = Field(
        None, description="Overrides default language if provided."
    )


class ErrorResponse(BaseModel):
    """Standard error response model for API errors."""

    detail: str = Field(..., description="A human-readable explanation of the error.")


class UpdateStatusResponse(BaseModel):
    """Response model for status updates, e.g., after saving settings."""

    message: str = Field(
        ..., description="A message describing the result of the operation."
    )
    restart_needed: Optional[bool] = Field(
        False,
        description="Indicates if a server restart is recommended or required for changes to take full effect.",
    )
