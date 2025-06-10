"""
Model configuration mappings for LLM providers.
This module provides a centralized way to manage model configurations including
provider mappings and token limits.
"""

from typing import Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    provider: str
    max_tokens: int
    context_length: int
    description: str = ""


# Model configuration registry
MODEL_CONFIGS: Dict[str, ModelConfig] = {
    # OpenAI Models
    "gpt-4o": ModelConfig(
        provider="openai",
        max_tokens=4096,
        context_length=128000,
        description="GPT-4o - High performance model"
    ),
    "gpt-4o-mini": ModelConfig(
        provider="openai",
        max_tokens=16384,
        context_length=128000,
        description="GPT-4o Mini - Cost-effective variant"
    ),
    "gpt-4.1-mini": ModelConfig(
        provider="openai",
        max_tokens=32768,
        context_length=104757,
        description="GPT-4.1 Mini - Latest mini variant"
    ),
    "gpt-4.1": ModelConfig(
        provider="openai",
        max_tokens=32768,
        context_length=104757,
        description="GPT-4.1 - Latest version"
    ),
    "o4-mini": ModelConfig(
        provider="openai",
        max_tokens=100000,
        context_length=200000,
        description="o4-mini - Optimized for reasoning"
    ),
    "o4-mini-high": ModelConfig(
        provider="openai",
        max_tokens=100000,
        context_length=200000,
        description="o4-mini High - Extended thinking mode"
    ),
    
    # Google Models
    "gemini-2.5-flash-preview-05-20": ModelConfig(
        provider="google",
        max_tokens=65536,
        context_length=1048576,
        description="Gemini 2.5 Flash Preview - Adaptive thinking"
    ),
    "gemini-2.5-pro-preview-06-05": ModelConfig(
        provider="google",
        max_tokens=65536,
        context_length=1048576,
        description="Gemini 2.5 Pro Preview - Advanced reasoning"
    ),
    "gemini-2.0-flash": ModelConfig(
        provider="google",
        max_tokens=8192,
        context_length=1048576,
        description="Gemini 2.0 Flash - Next generation features"
    ),
    "gemini-2.0-flash-lite": ModelConfig(
        provider="google",
        max_tokens=8192,
        context_length=1048576,
        description="Gemini 2.0 Flash Lite - Cost optimized"
    ),

    
    # Anthropic Models - Latest Claude 4 Generation
    "claude-opus-4-20250514": ModelConfig(
        provider="anthropic",
        max_tokens=32000,
        context_length=200000,
        description="Claude Opus 4 - Most powerful model, world's best coding model"
    ),
    "claude-sonnet-4-20250514": ModelConfig(
        provider="anthropic",
        max_tokens=64000,
        context_length=200000,
        description="Claude Sonnet 4 - High-performance model with exceptional reasoning"
    ),
    "claude-3-7-sonnet-20250219": ModelConfig(
        provider="anthropic",
        max_tokens=64000,
        context_length=200000,
        description="Claude 3.7 Sonnet - Hybrid reasoning with extended thinking"
    ),
    
    # Anthropic Models - Previous Generation (Claude 3.5)
    "claude-3-5-sonnet-20241022": ModelConfig(
        provider="anthropic",
        max_tokens=8192,
        context_length=200000,
        description="Claude 3.5 Sonnet v2 - Balanced performance"
    ),
    "claude-3-5-sonnet-20240620": ModelConfig(
        provider="anthropic",
        max_tokens=8192,
        context_length=200000,
        description="Claude 3.5 Sonnet - Original version"
    ),
    "claude-3-5-haiku-20241022": ModelConfig(
        provider="anthropic",
        max_tokens=8192,
        context_length=200000,
        description="Claude 3.5 Haiku - Fast and efficient"
    ),
    
    # Anthropic Models - Claude 3 Generation
    "claude-3-opus-20240229": ModelConfig(
        provider="anthropic",
        max_tokens=4096,
        context_length=200000,
        description="Claude 3 Opus - Previous highest capability"
    ),
    "claude-3-sonnet-20240229": ModelConfig(
        provider="anthropic",
        max_tokens=4096,
        context_length=200000,
        description="Claude 3 Sonnet - Previous balanced model"
    ),
    "claude-3-haiku-20240307": ModelConfig(
        provider="anthropic",
        max_tokens=4096,
        context_length=200000,
        description="Claude 3 Haiku - Previous fast model"
    ),
    
    # Aliases for convenience
    "claude-opus-4": ModelConfig(
        provider="anthropic",
        max_tokens=32000,
        context_length=200000,
        description="Claude Opus 4 - Alias for latest"
    ),
    "claude-sonnet-4": ModelConfig(
        provider="anthropic",
        max_tokens=64000,
        context_length=200000,
        description="Claude Sonnet 4 - Alias for latest"
    ),
    "claude-3.7-sonnet": ModelConfig(
        provider="anthropic",
        max_tokens=64000,
        context_length=200000,
        description="Claude 3.7 Sonnet - Alias for latest"
    ),
}

# Provider aliases for flexibility
PROVIDER_ALIASES = {
    "openai": "openai",
    "google": "google", 
    "anthropic": "anthropic",
    "gpt": "openai",
    "gemini": "google",
    "claude": "anthropic",
}


def get_model_config(model_name: str) -> Tuple[str, int]:
    """
    Get the provider and max_tokens for a given model name.
    
    Args:
        model_name: The name of the model
        
    Returns:
        Tuple of (provider, max_tokens)
        
    Raises:
        ValueError: If the model is not supported
    """
    if model_name not in MODEL_CONFIGS:
        raise ValueError(
            f"Unsupported model: {model_name}. "
            f"Supported models: {list(MODEL_CONFIGS.keys())}"
        )
    
    config = MODEL_CONFIGS[model_name]
    return config.provider, config.max_tokens


def get_full_model_config(model_name: str) -> ModelConfig:
    """
    Get the full configuration for a given model name.
    
    Args:
        model_name: The name of the model
        
    Returns:
        ModelConfig object containing all configuration
        
    Raises:
        ValueError: If the model is not supported
    """
    if model_name not in MODEL_CONFIGS:
        raise ValueError(
            f"Unsupported model: {model_name}. "
            f"Supported models: {list(MODEL_CONFIGS.keys())}"
        )
    
    return MODEL_CONFIGS[model_name]


def is_model_supported(model_name: str) -> bool:
    """
    Check if a model is supported.
    
    Args:
        model_name: The name of the model
        
    Returns:
        True if the model is supported, False otherwise
    """
    return model_name in MODEL_CONFIGS


def get_models_by_provider(provider: str) -> Dict[str, ModelConfig]:
    """
    Get all models for a specific provider.
    
    Args:
        provider: The provider name (openai, google, anthropic)
        
    Returns:
        Dictionary of model names to their configurations
    """
    provider = PROVIDER_ALIASES.get(provider.lower(), provider.lower())
    return {
        name: config for name, config in MODEL_CONFIGS.items()
        if config.provider == provider
    }


def get_recommended_model_for_task(task_type: str = "general") -> str:
    """
    Get a recommended model for a specific task type.
    
    Args:
        task_type: The type of task (general, reasoning, fast, cost_effective, coding, premium)
        
    Returns:
        Recommended model name
    """
    recommendations = {
        "general": "gemini-2.5-flash-preview-05-20",
        "reasoning": "claude-sonnet-4",
        "coding": "claude-opus-4",
        "premium": "claude-opus-4",
        "extended_thinking": "claude-3.7-sonnet",
        "fast": "gemini-2.0-flash",
        "cost_effective": "gpt-4o-mini",
        "long_context": "gemini-1.5-pro",
    }
    
    return recommendations.get(task_type, "gemini-2.5-flash-preview-05-20")


def get_optimal_max_tokens(model_name: str, task_complexity: str = "medium") -> int:
    """
    Get optimal max_tokens based on model and task complexity.
    
    Args:
        model_name: The name of the model
        task_complexity: low, medium, high
        
    Returns:
        Recommended max_tokens value
    """
    if not is_model_supported(model_name):
        raise ValueError(f"Unsupported model: {model_name}")
    
    config = MODEL_CONFIGS[model_name]
    base_tokens = config.max_tokens
    
    # Adjust based on task complexity
    complexity_multipliers = {
        "low": 0.25,
        "medium": 0.5,
        "high": 0.8,
    }
    
    multiplier = complexity_multipliers.get(task_complexity, 0.5)
    return min(int(base_tokens * multiplier), base_tokens)