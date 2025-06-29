from __future__ import annotations

import asyncio
import json
import os
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
import logging
from minerva.core.services.llm_providers.response import LLMResponse
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ClientError

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared client -------------------------------------------------------------
# ---------------------------------------------------------------------------

_shared_genai_client: genai.Client | None = None
_current_api_key_index: int = 0  # Track which API key we're currently using

# Available API keys in order of preference
_available_api_keys = [
    os.getenv("GEMINI_API_KEY"),
    os.getenv("GEMINI_API_KEY_2")
]

def _get_next_api_key() -> Optional[str]:
    """Get the next available API key, cycling through available keys."""
    global _current_api_key_index
    
    # Filter out None values
    valid_keys = [key for key in _available_api_keys if key is not None]
    
    if not valid_keys:
        return None
    
    # Get current key
    if _current_api_key_index < len(valid_keys):
        return valid_keys[_current_api_key_index]
    
    return None

def _rotate_api_key() -> Optional[str]:
    """Rotate to the next API key. Returns the new key or None if no more keys available."""
    global _current_api_key_index, _shared_genai_client
    
    _current_api_key_index += 1
    
    # Close existing client to force recreation with new key
    if _shared_genai_client is not None:
        try:
            _shared_genai_client.close()
        except:
            pass
        _shared_genai_client = None
    
    return _get_next_api_key()

def _reset_api_key_rotation():
    """Reset API key rotation to start from the first key."""
    global _current_api_key_index, _shared_genai_client
    _current_api_key_index = 0
    
    # Close existing client to force recreation
    if _shared_genai_client is not None:
        try:
            _shared_genai_client.close()
        except:
            pass
        _shared_genai_client = None

def _ensure_client() -> genai.Client:
    """Return a singleton ``genai.Client`` instance (Developer API or Vertex AI)."""
    global _shared_genai_client
    if _shared_genai_client is None:
        api_key = _get_next_api_key()
        if not api_key:
            raise ValueError("No valid Google API key available")
        _shared_genai_client = genai.Client(api_key=api_key)
    return _shared_genai_client

def _is_rate_limit_error(error: Exception) -> bool:
    """Check if the error is a rate limit error that should trigger API key rotation."""
    error_str = str(error).lower()
    rate_limit_indicators = [
        "quota", "resource_exhausted", "rate limit", "429", 
        "too many requests", "quota exceeded"
    ]
    return any(indicator in error_str for indicator in rate_limit_indicators)

def _clean_schema_for_gemini(schema: Any) -> Any:
    """
    Recursively remove unsupported fields from JSON schema for Gemini API.
    
    Gemini doesn't support:
    - additionalProperties
    - strict (this is OpenAI specific)
    """
    if isinstance(schema, dict):
        cleaned = {}
        for key, value in schema.items():
            # Skip unsupported fields
            if key in ("additionalProperties", "strict"):
                continue
            # Recursively clean nested objects
            cleaned[key] = _clean_schema_for_gemini(value)
        return cleaned
    elif isinstance(schema, list):
        return [_clean_schema_for_gemini(item) for item in schema]
    else:
        return schema


def _translate_response_format(response_format: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translate OpenAI response_format to Google Gemini format.
    
    OpenAI format:
    {
        "type": "json_schema",
        "json_schema": {
            "name": "schema_name",
            "strict": True,
            "schema": { ... actual JSON schema ... }
        }
    }
    
    Google format:
    {
        "response_mime_type": "application/json",
        "response_schema": { ... cleaned JSON schema ... }
    }
    """
    if not response_format:
        return {}
    
    # Check if it's OpenAI json_schema format
    if (response_format.get("type") == "json_schema" and 
        "json_schema" in response_format):
        
        json_schema = response_format["json_schema"]
        schema = json_schema.get("schema", {})
        
        # Clean the schema to remove unsupported fields
        cleaned_schema = _clean_schema_for_gemini(schema)
        
        return {
            "response_mime_type": "application/json",
            "response_schema": cleaned_schema
        }
    
    # If it's already in Google format or unknown format, return as is
    return response_format

# ---------------------------------------------------------------------------
# Main wrapper --------------------------------------------------------------
# ---------------------------------------------------------------------------

class GeminiLLM:
    """OpenAI‑compatible wrapper for Google Gemini models."""

    def __init__(
        self,
        model: str = "gemini-2.5-flash-preview-05-20",
        *,
        stream: bool = False,
        temperature: Optional[float] = 1.0,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        instructions: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None
    ) -> None:
        self.client = _ensure_client()
        self.model_name = model
        self.stream = stream
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tools = tools
        self.instructions = instructions
        self.response_format = response_format or {}

    def _refresh_client(self):
        """Force refresh the client (used after API key rotation)."""
        self.client = _ensure_client()

    async def _try_with_api_key_rotation(self, operation_func, *args, **kwargs):
        """
        Try an operation with API key rotation on rate limit errors.
        
        Args:
            operation_func: The async function to call
            *args, **kwargs: Arguments to pass to the operation function
        
        Returns:
            The result of the operation
        
        Raises:
            The last exception if all API keys fail
        """
        last_exception = None
        max_attempts = len([key for key in _available_api_keys if key is not None])
        
        for attempt in range(max_attempts):
            try:
                return await operation_func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                # Check if this is a rate limit error that should trigger rotation
                if _is_rate_limit_error(e) and attempt < max_attempts - 1:
                    logger.warning(f"Gemini API key {_current_api_key_index + 1} hit rate limit, rotating to next key")
                    
                    # Try to rotate to next API key
                    next_key = _rotate_api_key()
                    if next_key:
                        logger.info(f"Rotated to Gemini API key {_current_api_key_index + 1}")
                        # Refresh our client with the new key
                        self._refresh_client()
                        continue
                    else:
                        logger.error("No more Gemini API keys available for rotation")
                        break
                else:
                    # Not a rate limit error, or we've exhausted all attempts
                    break
        
        # If we get here, all attempts failed
        raise last_exception

    # ------------------------------------------------------------------
    # Public API --------------------------------------------------------
    # ------------------------------------------------------------------

    async def generate_response(
        self, messages: List[Dict[str, str]]
    ) -> Union[str, LLMResponse, AsyncGenerator[Dict[str, Any], None]]:
        """Generate a response (sync or streaming) with proper config handling and usage tracking."""

        # Always reset API key rotation to start with the first key for each new request
        _reset_api_key_rotation()
        self._refresh_client()

        # Convert chat messages → Gemini ``Content`` objects.
        contents: List[types.Content] = []
        for msg in messages:
            role = msg.get("role", "user")
            text = msg.get("content", "")
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=text)] if text else [],
                )
            )

        # --------------------------- Build GenerateContentConfig --------
        cfg_kwargs: Dict[str, Any] = {}
        if self.temperature is not None:
            cfg_kwargs["temperature"] = self.temperature
        if self.max_tokens is not None:
            cfg_kwargs["max_output_tokens"] = self.max_tokens

        # Translate OpenAI response_format → Gemini response_mime_type / schema
        cfg_kwargs.update(_translate_response_format(self.response_format))

        if self.tools:
            cfg_kwargs["tools"] = self.tools
        if self.instructions:
            cfg_kwargs["system_instruction"] = self.instructions

        gen_config: Optional[types.GenerateContentConfig] = (
            types.GenerateContentConfig(**cfg_kwargs, thinking_config=types.ThinkingConfig(thinking_budget=0)) if cfg_kwargs else None
        )

        # --------------------------- Call model with API key rotation -------------------------
        if not self.stream:
            async def _generate_content():
                response = await self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=gen_config
                )
                return response
            
            response = await self._try_with_api_key_rotation(_generate_content)
            
            # Extract usage information from Gemini response
            usage_info = None
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage_info = {
                    'prompt_tokens': getattr(response.usage_metadata, 'prompt_token_count', 0),
                    'completion_tokens': getattr(response.usage_metadata, 'candidates_token_count', 0),
                    'total_tokens': getattr(response.usage_metadata, 'total_token_count', 0)
                }
            
            # Extract content from response
            content = self._extract_first_candidate(response)
            
            # Return LLMResponse wrapper with usage info for cost tracking
            if isinstance(content, str):
                return LLMResponse(content, usage_info, "text")
            elif isinstance(content, dict) and content.get("type") == "function_call":
                # Convert function call dict to JSON string
                return LLMResponse(
                    json.dumps(content),
                    usage_info,
                    "function_call"
                )
            else:
                return LLMResponse(str(content), usage_info, "text")

        # Streaming with API key rotation
        async def _generate_content_stream():
            return await self.client.aio.models.generate_content_stream(
                model=self.model_name,
                contents=contents,
                config=gen_config,
            )

        stream_iter = await self._try_with_api_key_rotation(_generate_content_stream)

        async def _stream() -> AsyncGenerator[Dict[str, Any], None]:
            async for chunk in stream_iter:
                for cand in chunk.candidates or []:
                    for part in cand.content.parts:
                        if text := getattr(part, "text", None):
                            yield {"type": "text", "content": text}
                        elif fc := getattr(part, "function_call", None):
                            yield {
                                "type": "function_call",
                                "name": fc.name,
                                "arguments": fc.args or {},
                            }
        return _stream()

    # ------------------------------------------------------------------
    # Helper to pick first candidate -----------------------------------
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_first_candidate(resp: Any) -> Union[str, Dict[str, Any]]:  # noqa: ANN401
        """Extract content from the first candidate in the response."""
        if not resp or not getattr(resp, "candidates", None):
            return ""
        first = resp.candidates[0]
        for part in first.content.parts:
            if (text := getattr(part, "text", None)):
                return text
            if (fc := getattr(part, "function_call", None)):
                return {
                    "type": "function_call",
                    "name": fc.name,
                    "arguments": fc.args or {},
                }
        return ""

    # ------------------------------------------------------------------
    # Close shared client ----------------------------------------------
    # ------------------------------------------------------------------
    @classmethod
    async def aclose_shared_client(cls) -> None:
        """Close the shared Gemini client."""
        global _shared_genai_client
        if _shared_genai_client is not None:
            close = getattr(_shared_genai_client, "close_async", None)
            if close and asyncio.iscoroutinefunction(close):
                await close()
            else:
                _shared_genai_client.close()  # type: ignore[attr-defined]
            _shared_genai_client = None

    @classmethod  
    def reset_api_key_rotation(cls):
        """Reset API key rotation to start from the first key. Useful for testing or manual resets."""
        _reset_api_key_rotation()