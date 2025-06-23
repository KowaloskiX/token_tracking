from typing import Optional, Dict

class LLMResponse:
    """Shared wrapper to include usage information with LLM responses"""
    def __init__(self, content: str, usage: Optional[Dict] = None, response_type: str = "text"):
        self.content = content
        self.usage = usage
        self.response_type = response_type
        
    def __str__(self):
        return self.content