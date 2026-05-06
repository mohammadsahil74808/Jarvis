import time
import json
import requests
import logging
from typing import Optional, List
from core.config import get_api_key, get_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AIRouter")

class AIRouter:
    """
    Multi-model AI client with fallback logic.
    Priority: DeepSeek Coder -> Mixtral -> Gemini
    """

    def __init__(self):
        self.openrouter_key = get_config().get("openrouter_api_key", "")
        self.gemini_key     = get_api_key()
        
        # Model Priority List
        self.models = [
            {"provider": "openrouter", "id": "deepseek/deepseek-chat"},
            {"provider": "openrouter", "id": "mistralai/mixtral-8x7b-instruct"},
            {"provider": "gemini",     "id": "gemini-2.0-flash"}
        ]

    def generate(self, prompt: str, system_instruction: str = "You are a senior code generator.") -> str:
        """
        Attempts to generate a response using models in priority order.
        """
        for model_info in self.models:
            provider = model_info["provider"]
            model_id = model_info["id"]

            logger.info(f"Attempting generation with {model_id} ({provider})...")
            
            try:
                if provider == "openrouter":
                    response = self._call_openrouter_with_retry(model_id, prompt, system_instruction)
                else:
                    response = self._call_gemini_with_retry(prompt, system_instruction)

                if response:
                    logger.info(f"Success with {model_id}")
                    return response
            except Exception as e:
                logger.error(f"Failed with {model_id}: {e}")
                continue

        return "Error: All AI models failed to respond."

    def _call_openrouter_with_retry(self, model: str, prompt: str, system: str, retries: int = 3) -> Optional[str]:
        if not self.openrouter_key:
            raise ValueError("OpenRouter API Key missing")

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/mohammadsahil74808/Jarvis",
            "X-Title": "JARVIS AI Assistant"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ]
        }

        for i in range(retries):
            try:
                response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    return data['choices'][0]['message']['content']
                
                if response.status_code in [503, 429]: # Service unavailable or rate limit
                    wait = (2 ** i) # Exponential backoff
                    logger.warning(f"OpenRouter busy ({response.status_code}). Retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                
                logger.error(f"OpenRouter Error {response.status_code}: {response.text}")
                break
            except requests.exceptions.Timeout:
                logger.warning("OpenRouter timeout. Retrying...")
                continue
            except Exception as e:
                logger.error(f"OpenRouter Request Error: {e}")
                break
        
        return None

    def _call_gemini_with_retry(self, prompt: str, system: str, retries: int = 2) -> Optional[str]:
        """Fallback to Google Gemini."""
        if not self.gemini_key:
            raise ValueError("Gemini API Key missing")

        # We use the existing config's client if possible, but AIRouter should be independent
        from google import genai
        client = genai.Client(api_key=self.gemini_key)

        for i in range(retries):
            try:
                # Note: Using gemini-2.0-flash as it's the current best fast model
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=f"System: {system}\n\nUser: {prompt}"
                )
                if response and response.text:
                    return response.text
            except Exception as e:
                if "503" in str(e) or "quota" in str(e).lower():
                    wait = (2 ** i)
                    time.sleep(wait)
                    continue
                logger.error(f"Gemini Error: {e}")
                break
        return None

# Singleton instance
_router = None
def get_ai_router():
    global _router
    if _router is None:
        _router = AIRouter()
    return _router
