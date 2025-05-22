# chatbot/services/llm/anthropic_llm.py
import os
from anthropic import AsyncAnthropic
from typing import List, AsyncGenerator, Union, Dict, Any, Optional
from dotenv import load_dotenv
import json

load_dotenv()

class AnthropicLLM:
    def __init__(
        self,
        model: str = "claude-3-7-sonnet-20250219",
        stream: bool = False,
        temperature: Optional[float] = 1.0,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        instructions: Optional[str] = None,
        response_format: Optional[dict[str, Any]] = None
    ):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.client = AsyncAnthropic(api_key=api_key)
        
        self.model = model
        self.stream = stream
        self.temperature = min(max(temperature, 0.0), 1.0) if temperature is not None else 1.0
        self.max_tokens = max_tokens
        self.tools = tools
        self.instructions = instructions or "When a tool is provided and relevant to the query, use it to provide accurate information."

    async def generate_response(self, messages: List[Dict[str, str]]) -> Union[str, AsyncGenerator[Dict[str, Any], None]]:
        params = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if self.tools is not None:
            params["tools"] = self.tools
            params["tool_choice"] = {"type": "auto"}
        if self.instructions is not None:
            params["system"] = self.instructions
        
        if not self.stream:
            response = await self.client.messages.create(**params)
            tool_response = None
            text_response = None
            for content_block in response.content:
                if content_block.type == "tool_use":
                    tool_response = {
                        "type": "function_call",
                        "name": content_block.name,
                        "arguments": json.dumps(content_block.input)
                    }
                    break
                elif content_block.type == "text":
                    text_response = content_block.text
            return tool_response if tool_response is not None else text_response if text_response is not None else ""
            
        else:
            stream = self.client.messages.stream(**params)
            
            async def stream_response():
                full_text = ""
                tool_name = None
                tool_arguments = ""
                
                async with stream as s:
                    async for event in s:
                        if event.type == "content_block_delta" and event.delta.type == "text_delta":
                            full_text += event.delta.text
                            yield {"type": "text", "content": event.delta.text}
                        elif event.type == "content_block_start" and event.content_block.type == "tool_use":
                            tool_name = event.content_block.name
                            tool_arguments = ""
                        elif event.type == "content_block_delta" and event.delta.type == "input_json_delta":
                            tool_arguments += event.delta.partial_json
                        elif event.type == "content_block_stop" and tool_name:
                            yield {
                                "type": "function_call",
                                "name": tool_name,
                                "arguments": tool_arguments
                            }
                            tool_name = None
                            tool_arguments = ""
                        elif event.type == "message_stop":
                            break
            
            return stream_response()