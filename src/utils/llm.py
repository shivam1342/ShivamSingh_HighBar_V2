"""
LLM interface module - supports Ollama, OpenAI, Groq, and Hugging Face
"""
import requests
import json
from typing import Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)


class LLMClient:
    """Simple LLM client that works with multiple providers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.provider = config.get("provider", "ollama")
        self.model = config.get("model", "mistral")
        self.base_url = config.get("base_url", "http://localhost:11434")
        # Try environment variable first, then config
        self.api_key = os.getenv("LLM_API_KEY") or config.get("api_key", "")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 1000)
        
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate text from prompt using configured LLM
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt for context
            
        Returns:
            Generated text response
        """
        if self.provider == "ollama":
            return self._generate_ollama(prompt, system_prompt)
        elif self.provider == "openai":
            return self._generate_openai(prompt, system_prompt)
        elif self.provider == "groq":
            return self._generate_groq(prompt, system_prompt)
        elif self.provider == "huggingface":
            return self._generate_huggingface(prompt, system_prompt)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    def _generate_ollama(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate using Ollama API"""
        try:
            # Combine system and user prompt if system prompt provided
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens
                    }
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Ollama generation successful (model={self.model})")
            return result["response"]
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama API error: {e}")
            raise Exception(f"Failed to connect to Ollama. Is it running? Error: {e}")
    
    def _generate_openai(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate using OpenAI API"""
        try:
            import openai
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            logger.info(f"OpenAI generation successful (model={self.model})")
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise Exception(f"Failed to call OpenAI API: {e}")
    
    def _generate_groq(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate using Groq API (FAST and FREE)"""
        try:
            if not self.api_key:
                raise Exception("Groq API key required. Set LLM_API_KEY env variable or add to config")
            
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
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Groq generation successful (model={self.model})")
            return result["choices"][0]["message"]["content"]
            
        except requests.exceptions.HTTPError as e:
            error_detail = ""
            try:
                error_detail = response.json().get("error", {}).get("message", "")
            except:
                pass
            logger.error(f"Groq API error: {e}. Detail: {error_detail}")
            raise Exception(f"Groq API error: {error_detail or str(e)}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Groq API error: {e}")
            raise Exception(f"Failed to connect to Groq API: {e}")
    
    def _generate_huggingface(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate using Hugging Face Inference API (FREE)"""
        try:
            if not self.api_key:
                raise Exception("HuggingFace API key required. Get free key from https://huggingface.co/settings/tokens")
            
            # Combine prompts
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            response = requests.post(
                f"https://api-inference.huggingface.co/models/{self.model}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "inputs": full_prompt,
                    "parameters": {
                        "temperature": self.temperature,
                        "max_new_tokens": self.max_tokens,
                        "return_full_text": False
                    }
                },
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            
            # Handle different response formats
            if isinstance(result, list) and len(result) > 0:
                text = result[0].get("generated_text", "")
            elif isinstance(result, dict):
                text = result.get("generated_text", "")
            else:
                text = str(result)
            
            logger.info(f"HuggingFace generation successful (model={self.model})")
            return text
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HuggingFace API error: {e}")
            raise Exception(f"Failed to connect to HuggingFace API: {e}")
