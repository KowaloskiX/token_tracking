# chatbot/services/llm/openai_llm.py
from typing import List, AsyncGenerator, Union, Dict, Any, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI
import json

load_dotenv()

# Shared AsyncOpenAI client to avoid spawning a new HTTPX AsyncClient per
# OpenAILLM instance (each one holds a connection-pool and background task).
_shared_async_openai: AsyncOpenAI | None = None

class LLMResponse:
    """Wrapper to include usage information with LLM responses"""
    def __init__(self, content: str, usage: Optional[Dict] = None, response_type: str = "text"):
        self.content = content
        self.usage = usage
        self.response_type = response_type
        
    def __str__(self):
        return self.content

class OpenAILLM:
    def __init__(
        self,
        model: str = "gpt-4.1",
        stream: bool = False,
        temperature: Optional[float] = 1.0,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        instructions: Optional[str] = None,
        response_format: Optional[dict[str, Any]] = None
    ):
        global _shared_async_openai
        if _shared_async_openai is None:
            _shared_async_openai = AsyncOpenAI()
        self.openai = _shared_async_openai
        self.model = model
        self.stream = stream
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tools = tools
        self.instructions = instructions
        self.response_format = response_format

    async def generate_response(self, messages: List[Dict[str, str]]) -> Union[str, LLMResponse, AsyncGenerator[Dict[str, Any], None]]:
        # Prepend system message if instructions are provided
        if self.instructions:
            messages = [{"role": "system", "content": self.instructions}] + messages

        params: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": self.stream,
        }

        # Add temperature unless it's o4-mini with 0.0, or if temperature is None
        if not (self.model == "o4-mini" and self.temperature == 0.0):
            if self.temperature is not None:
                params["temperature"] = self.temperature
        
        if self.max_tokens is not None:
            params["max_tokens"] = self.max_tokens
        
        if self.response_format is not None:
            params["response_format"] = self.response_format
            
        if self.tools:
            params["tools"] = self.tools
            params["tool_choice"] = "auto"

        if not self.stream:
            response = await self.openai.chat.completions.create(**params)
            choice = response.choices[0]
            
            # Extract usage information
            usage_info = None
            if hasattr(response, 'usage') and response.usage:
                usage_info = {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            
            if choice.message.content:
                return LLMResponse(choice.message.content, usage_info)
            elif choice.message.tool_calls:
                tool_call = choice.message.tool_calls[0]
                return LLMResponse(
                    json.dumps({
                        "type": "function_call",
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }),
                    usage_info,
                    "function_call"
                )
            return LLMResponse("", usage_info)
        
        else:
            stream = await self.openai.chat.completions.create(**params)
            
            async def stream_response():
                full_text = ""
                tool_name = None
                tool_arguments = ""
                
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        delta = chunk.choices[0].delta.content
                        full_text += delta
                        yield {"type": "text", "content": delta}
                    elif chunk.choices and chunk.choices[0].delta.tool_calls:
                        tool_call_delta = chunk.choices[0].delta.tool_calls[0]
                        if tool_call_delta.function.name and not tool_name:
                            tool_name = tool_call_delta.function.name
                        if tool_call_delta.function.arguments:
                            tool_arguments += tool_call_delta.function.arguments
                    elif chunk.choices and chunk.choices[0].finish_reason == "tool_calls":
                        if tool_name and tool_arguments:
                            yield {
                                "type": "function_call",
                                "name": tool_name,
                                "arguments": tool_arguments
                            }
                            tool_name = None
                            tool_arguments = ""
            
            return stream_response()

    # ------------------------------------------------------------------
    # Class helpers -----------------------------------------------------
    # ------------------------------------------------------------------

    @classmethod
    async def aclose_shared_client(cls):
        """Explicitly close the shared AsyncOpenAI HTTPX client (e.g. on shutdown)."""
        global _shared_async_openai
        if _shared_async_openai is not None:
            await _shared_async_openai.aclose()
            _shared_async_openai = None