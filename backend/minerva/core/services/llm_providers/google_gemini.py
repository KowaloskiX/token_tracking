from __future__ import annotations

import asyncio
import os
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# ---------------------------------------------------------------------------
# Shared client -------------------------------------------------------------
# ---------------------------------------------------------------------------

_shared_genai_client: genai.Client | None = None


def _ensure_client() -> genai.Client:
    """Return a singleton ``genai.Client`` instance (Developer API or Vertex AI)."""
    global _shared_genai_client
    if _shared_genai_client is None:
        _shared_genai_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    return _shared_genai_client

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

    # ------------------------------------------------------------------
    # Public API --------------------------------------------------------
    # ------------------------------------------------------------------

    async def generate_response(
        self, messages: List[Dict[str, str]]
    ) -> Union[str, AsyncGenerator[Dict[str, Any], None]]:
        """Generate a response (sync or streaming) with proper config handling."""

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

        # --------------------------- Call model -------------------------
        if not self.stream:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=gen_config
            )
            return self._extract_first_candidate(response)

        # Streaming
        stream_iter = await self.client.aio.models.generate_content_stream(
            model=self.model_name,
            contents=contents,
            config=gen_config,
        )

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
        global _shared_genai_client
        if _shared_genai_client is not None:
            close = getattr(_shared_genai_client, "close_async", None)
            if close and asyncio.iscoroutinefunction(close):
                await close()
            else:
                _shared_genai_client.close()  # type: ignore[attr-defined]
            _shared_genai_client = None
