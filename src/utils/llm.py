"""
LLM interface module - Groq API client
"""
import requests
import json
from typing import Dict, Any, Optional
import logging
import os

from src.utils.exceptions import LLMAPIError, TimeoutError as CustomTimeoutError
from src.utils.retry import exponential_backoff_with_jitter

logger = logging.getLogger(__name__)


class LLMClient:
    """Groq API client for fast LLM inference"""
    
    def __init__(self, config: Dict[str, Any]):
        self.model = config.get("model", "llama-3.3-70b-versatile")
        # Try environment variable first, then config
        self.api_key = os.getenv("LLM_API_KEY") or config.get("api_key", "")
        self.temperature = config.get("temperature", 0.5)
        self.max_tokens = config.get("max_tokens", 1500)
        self.timeout = config.get("timeout", 60)
        
        if not self.api_key:
            raise LLMAPIError("Groq API key required. Set LLM_API_KEY environment variable or add to config")
        
    @exponential_backoff_with_jitter(
        max_retries=3,
        base_delay=1.0,
        retriable_exceptions=(LLMAPIError, CustomTimeoutError, requests.exceptions.RequestException)
    )
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate text from prompt using Groq API with automatic retry on failures
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt for context
            
        Returns:
            Generated text response
            
        Raises:
            LLMAPIError: API request failed (rate limit, auth, model error)
            CustomTimeoutError: Request timed out
        """
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens
                },
                timeout=self.timeout
            )
            
            # Handle HTTP errors with proper categorization
            if response.status_code == 429:
                raise LLMAPIError("Rate limit exceeded", status_code=429, provider="groq")
            elif response.status_code == 401:
                raise LLMAPIError("Invalid API key", status_code=401, provider="groq")
            elif response.status_code >= 500:
                raise LLMAPIError("Groq server error", status_code=response.status_code, provider="groq")
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Groq generation successful (model={self.model})")
            return result["choices"][0]["message"]["content"]
            
        except requests.exceptions.Timeout as e:
            logger.error(f"Groq API timeout after {self.timeout}s: {e}")
            raise CustomTimeoutError(f"Groq API timeout after {self.timeout}s", timeout_seconds=self.timeout)
            
        except requests.exceptions.HTTPError as e:
            error_detail = ""
            status_code = None
            try:
                error_detail = response.json().get("error", {}).get("message", "")
                status_code = response.status_code
            except:
                pass
            logger.error(f"Groq API HTTP error: {e}. Detail: {error_detail}")
            raise LLMAPIError(
                f"Groq API error: {error_detail or str(e)}", 
                status_code=status_code, 
                provider="groq"
            )
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Groq API connection error: {e}")
            raise LLMAPIError(f"Failed to connect to Groq API: {e}", provider="groq")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Groq API request error: {e}")
            raise LLMAPIError(f"Groq API request failed: {e}", provider="groq")
