"""
Shared OpenAI client configuration module.
This module provides consistent timeout and retry configuration for all OpenAI clients.
"""

import os
import httpx
from typing import Optional
from openai import OpenAI, AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# Timeout configuration from environment variables
OPENAI_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "600"))  # 600 seconds default
OPENAI_CONNECT_TIMEOUT = int(os.getenv("OPENAI_CONNECT_TIMEOUT", "30"))  # 30 seconds for connection
OPENAI_READ_TIMEOUT = int(os.getenv("OPENAI_READ_TIMEOUT", "120"))  # 120 seconds for reading response
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "3"))  # 3 retries default

# Shared clients to avoid creating multiple instances
_shared_sync_openai: Optional[OpenAI] = None
_shared_async_openai: Optional[AsyncOpenAI] = None


def _create_timeout_config() -> httpx.Timeout:
    """Create httpx timeout configuration."""
    return httpx.Timeout(
        timeout=OPENAI_TIMEOUT,
        connect=OPENAI_CONNECT_TIMEOUT,
        read=OPENAI_READ_TIMEOUT,
        write=OPENAI_TIMEOUT,
        pool=10.0  # timeout for acquiring connection from pool
    )


def _create_limits_config() -> httpx.Limits:
    """Create httpx limits configuration."""
    return httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20
    )


def create_sync_openai_client() -> OpenAI:
    """Create a sync OpenAI client with proper timeout configuration."""
    timeout = _create_timeout_config()
    
    # Create httpx client with timeout configuration
    http_client = httpx.Client(
        timeout=timeout,
        limits=_create_limits_config()
    )
    
    return OpenAI(
        http_client=http_client,
        max_retries=OPENAI_MAX_RETRIES,
        timeout=OPENAI_TIMEOUT
    )


def create_async_openai_client() -> AsyncOpenAI:
    """Create an async OpenAI client with proper timeout configuration."""
    timeout = _create_timeout_config()
    
    # Create httpx client with timeout configuration
    http_client = httpx.AsyncClient(
        timeout=timeout,
        limits=_create_limits_config()
    )
    
    return AsyncOpenAI(
        http_client=http_client,
        max_retries=OPENAI_MAX_RETRIES,
        timeout=OPENAI_TIMEOUT
    )


def get_shared_sync_openai_client() -> OpenAI:
    """Get a shared sync OpenAI client instance."""
    global _shared_sync_openai
    if _shared_sync_openai is None:
        _shared_sync_openai = create_sync_openai_client()
    return _shared_sync_openai


def get_shared_async_openai_client() -> AsyncOpenAI:
    """Get a shared async OpenAI client instance."""
    global _shared_async_openai
    if _shared_async_openai is None:
        _shared_async_openai = create_async_openai_client()
    return _shared_async_openai


async def close_shared_clients():
    """Close all shared OpenAI clients."""
    global _shared_sync_openai, _shared_async_openai
    
    if _shared_sync_openai is not None:
        _shared_sync_openai.close()
        _shared_sync_openai = None
    
    if _shared_async_openai is not None:
        await _shared_async_openai.aclose()
        _shared_async_openai = None


# Backward compatibility exports
def get_configured_openai_client() -> OpenAI:
    """Get a configured sync OpenAI client (backward compatibility)."""
    return get_shared_sync_openai_client()


def get_configured_async_openai_client() -> AsyncOpenAI:
    """Get a configured async OpenAI client (backward compatibility)."""
    return get_shared_async_openai_client() 