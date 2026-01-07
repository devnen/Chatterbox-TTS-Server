# File: llm_preprocessor.py
# LLM-based preprocessing for extracting TTS parameters from natural language input.
# Uses litellm for unified access to multiple LLM providers.

import logging
from typing import Optional

import litellm
from litellm import acompletion
from pydantic import BaseModel, Field

from config import (
    config_manager,
    get_llm_preprocessing_enabled,
    get_llm_preprocessing_model,
    get_llm_preprocessing_api_base,
    get_llm_preprocessing_api_key,
    get_llm_preprocessing_timeout,
    get_llm_preprocessing_fallback_on_error,
    get_llm_preprocessing_prompt,
)

logger = logging.getLogger(__name__)

# Enable schema validation for local models that may not natively support JSON schema
litellm.enable_json_schema_validation = True


class TTSParamsExtraction(BaseModel):
    """
    Strongly-typed extraction result for TTS parameters.
    Fields match CustomTTSRequest parameters that can be extracted from natural language.
    """

    text: str = Field(
        description="The cleaned text to synthesize, with instructions removed"
    )
    temperature: Optional[float] = Field(
        None, ge=0.0, le=1.5, description="Controls randomness (0.0-1.5)"
    )
    exaggeration: Optional[float] = Field(
        None, ge=0.25, le=2.0, description="Controls expressiveness (0.25-2.0)"
    )
    cfg_weight: Optional[float] = Field(
        None, ge=0.2, le=1.0, description="Classifier-Free Guidance weight (0.2-1.0)"
    )
    split_text: Optional[bool] = Field(
        None, description="Whether to split long text into chunks"
    )
    chunk_size: Optional[int] = Field(
        None, ge=50, le=500, description="Target chunk size in characters (50-500)"
    )
    language: Optional[str] = Field(
        None, description="Language code (e.g., 'en', 'es', 'fr')"
    )


async def preprocess_speech_input(input_text: str) -> TTSParamsExtraction:
    """
    Extract TTS parameters from natural language input using a configured LLM.

    Args:
        input_text: The raw input text that may contain natural language instructions
                   for TTS generation (e.g., "speak excitedly: Hello world!")

    Returns:
        TTSParamsExtraction with cleaned text and any extracted parameters.

    Raises:
        Exception: If LLM call fails and fallback_on_error is False.
    """
    if not get_llm_preprocessing_enabled():
        logger.debug("LLM preprocessing is disabled, returning original text")
        return TTSParamsExtraction(text=input_text)

    model = get_llm_preprocessing_model()
    prompt = get_llm_preprocessing_prompt()
    api_base = get_llm_preprocessing_api_base()
    api_key = get_llm_preprocessing_api_key()
    timeout = get_llm_preprocessing_timeout()
    fallback_on_error = get_llm_preprocessing_fallback_on_error()

    logger.info(f"Preprocessing input with LLM model: {model}")
    logger.debug(f"Input text: {input_text[:100]}...")

    try:
        response = await acompletion(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": input_text},
            ],
            response_format=TTSParamsExtraction,
            api_base=api_base,
            api_key=api_key,
            timeout=timeout,
        )

        # Parse the response content into our Pydantic model
        content = response.choices[0].message.content
        result = TTSParamsExtraction.model_validate_json(content)

        logger.info(f"LLM extracted params: text='{result.text[:50]}...', "
                   f"temperature={result.temperature}, exaggeration={result.exaggeration}, "
                   f"cfg_weight={result.cfg_weight}, split_text={result.split_text}, "
                   f"chunk_size={result.chunk_size}, language={result.language}")

        return result

    except Exception as e:
        logger.error(f"LLM preprocessing failed: {e}", exc_info=True)

        if fallback_on_error:
            logger.warning("Falling back to original text due to LLM error")
            return TTSParamsExtraction(text=input_text)
        else:
            raise


# --- End File: llm_preprocessor.py ---
