# core/ai_router.py  ← REPLACE tera purana ai_router.py is se
# ══════════════════════════════════════════════════════════════
# JARVIS FREE AI ROUTER v2
# Sab FREE models — koi paid API nahi
#
# FREE MODELS INCLUDED:
#   Text/Code : Gemini Flash (Google FREE)
#               Groq LLaMA-3.3-70B (FREE)
#               NVIDIA Llama-3.1-70B (FREE with key)
#               OpenRouter free tier models
#               Hugging Face Inference (FREE)
#               Pollinations.ai (100% FREE, no key needed)
#
#   Image Gen : Pollinations.ai (FREE, no key)
#               Hugging Face FLUX (FREE)
#
# KEYS NEEDED (ALL FREE TO GET):
#   GEMINI_API_KEY   : aizasya... (ai.google.dev - FREE)
#   GROQ_API_KEY     : gsk_...    (console.groq.com - FREE)
#   NVIDIA_API_KEY   : nvapi-...  (build.nvidia.com - FREE $25 credit)
#   HF_API_KEY       : hf_...     (huggingface.co - FREE)
#   OPENROUTER_KEY   : sk-or-...  (openrouter.ai - FREE tier)
#   (Pollinations needs NO key at all)
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import json
import time
import logging
import requests
import urllib.parse
from typing import Optional
from core.config import get_config, get_api_key

logger = logging.getLogger("FreeAIRouter")


# ══════════════════════════════════════════════════════════════
# FREE MODEL CATALOGUE
# ══════════════════════════════════════════════════════════════

FREE_TEXT_MODELS = [
    # ── Tier 1: Best quality FREE models ──────────────────────
    {
        "id":       "groq-llama-70b",
        "provider": "groq",
        "model":    "llama-3.3-70b-versatile",
        "key_cfg":  "groq_api_key",
        "best_for": ["code", "analysis", "general"],
        "speed":    "fast",
    },
    {
        "id":       "nvidia-llama-70b",
        "provider": "nvidia",
        "model":    "meta/llama-3.1-70b-instruct",
        "key_cfg":  "nvidia_api_key",
        "best_for": ["code", "analysis", "general"],
        "speed":    "fast",
    },
    {
        "id":       "gemini-flash",
        "provider": "gemini",
        "model":    "gemini-2.0-flash",
        "key_cfg":  "gemini_api_key",
        "best_for": ["general", "vision", "long_context"],
        "speed":    "fast",
    },
    # ── Tier 2: Good free models ───────────────────────────────
    {
        "id":       "groq-llama-8b",
        "provider": "groq",
        "model":    "llama3-8b-8192",
        "key_cfg":  "groq_api_key",
        "best_for": ["quick", "chat"],
        "speed":    "very_fast",
    },
    {
        "id":       "nvidia-deepseek",
        "provider": "nvidia",
        "model":    "deepseek-ai/deepseek-r1",
        "key_cfg":  "nvidia_api_key",
        "best_for": ["code", "reasoning"],
        "speed":    "medium",
    },
    {
        "id":       "openrouter-free",
        "provider": "openrouter",
        "model":    "meta-llama/llama-3.2-3b-instruct:free",
        "key_cfg":  "openrouter_api_key",
        "best_for": ["general", "quick"],
        "speed":    "fast",
    },
    {
        "id":       "hf-mistral",
        "provider": "huggingface",
        "model":    "mistralai/Mistral-7B-Instruct-v0.3",
        "key_cfg":  "huggingface_api_key",
        "best_for": ["general"],
        "speed":    "medium",
    },
    # ── Tier 3: No API key needed (always works) ──────────────
    {
        "id":       "pollinations-free",
        "provider": "pollinations",
        "model":    "openai",   # pollinations proxies openai for free
        "key_cfg":  None,       # NO KEY NEEDED
        "best_for": ["general", "fallback"],
        "speed":    "medium",
    },
]

# Best model per task type
TASK_MODEL_MAP = {
    "code":         ["groq-llama-70b", "nvidia-deepseek", "nvidia-llama-70b", "gemini-flash"],
    "analysis":     ["groq-llama-70b", "nvidia-llama-70b", "gemini-flash"],
    "quick":        ["groq-llama-8b",  "groq-llama-70b",  "pollinations-free"],
    "general":      ["groq-llama-70b", "gemini-flash",    "nvidia-llama-70b"],
    "vision":       ["gemini-flash"],
    "long_context": ["gemini-flash"],
    "reasoning":    ["nvidia-deepseek","groq-llama-70b",  "gemini-flash"],
    "fallback":     ["pollinations-free"],
}


# ══════════════════════════════════════════════════════════════
class FreeAIRouter:
    """
    Routes requests to best available FREE model.
    Falls through chain until one works.
    Last resort: Pollinations (no key, always works).
    """

    def __init__(self):
        self._config = {}
        self._refresh_keys()

    def _refresh_keys(self):
        """Refresh keys from config (supports hot-reload)."""
        cfg = get_config()
        self._config = {
            "groq_api_key":       cfg.get("groq_api_key",       ""),
            "nvidia_api_key":     cfg.get("nvidia_api_key",     ""),
            "gemini_api_key":     get_api_key(),
            "openrouter_api_key": cfg.get("openrouter_api_key", ""),
            "huggingface_api_key":cfg.get("huggingface_api_key",""),
        }

    # ─────────────────────────────────────────────────────────
    def generate(
        self,
        prompt:      str,
        system:      str  = "You are a helpful AI assistant.",
        task:        str  = "general",
        max_tokens:  int  = 2048,
    ) -> str:
        """
        Main entry point. Auto-selects best free model for task.

        Parameters
        ----------
        prompt     : user message
        system     : system instruction
        task       : "code" | "analysis" | "quick" | "general" | "reasoning"
        max_tokens : max response length
        """
        self._refresh_keys()

        # Get model priority for this task
        model_order = TASK_MODEL_MAP.get(task, TASK_MODEL_MAP["general"])

        # Build ordered list of model configs
        ordered = []
        for mid in model_order:
            m = next((x for x in FREE_TEXT_MODELS if x["id"] == mid), None)
            if m:
                ordered.append(m)

        # Add any remaining models as fallback
        for m in FREE_TEXT_MODELS:
            if m not in ordered:
                ordered.append(m)

        # Try each model
        for model_info in ordered:
            key_cfg = model_info.get("key_cfg")
            # Skip if key needed but not configured
            if key_cfg and not self._config.get(key_cfg, ""):
                continue

            try:
                logger.info(f"Trying {model_info['id']} ({model_info['provider']})...")
                result = self._call_model(model_info, prompt, system, max_tokens)
                if result and result.strip():
                    logger.info(f"Success: {model_info['id']}")
                    return result
            except Exception as e:
                logger.warning(f"Failed {model_info['id']}: {e}")
                continue

        return "Error: All free AI models failed. Check your internet connection."

    # ─────────────────────────────────────────────────────────
    def _call_model(self, info: dict, prompt: str,
                    system: str, max_tokens: int) -> Optional[str]:
        provider = info["provider"]
        if provider == "groq":
            return self._call_groq(info["model"], prompt, system, max_tokens)
        elif provider == "nvidia":
            return self._call_nvidia(info["model"], prompt, system, max_tokens)
        elif provider == "gemini":
            return self._call_gemini(info["model"], prompt, system)
        elif provider == "openrouter":
            return self._call_openrouter(info["model"], prompt, system, max_tokens)
        elif provider == "huggingface":
            return self._call_huggingface(info["model"], prompt, system)
        elif provider == "pollinations":
            return self._call_pollinations(prompt, system)
        return None

    # ─────────────────────────────────────────────────────────
    # GROQ — Free, fast, 100K tokens/day
    # Sign up: console.groq.com (free)
    # ─────────────────────────────────────────────────────────
    def _call_groq(self, model: str, prompt: str,
                   system: str, max_tokens: int) -> Optional[str]:
        import groq
        client = groq.Groq(api_key=self._config["groq_api_key"])
        resp   = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.2,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content

    # ─────────────────────────────────────────────────────────
    # NVIDIA NIM — Free $25 credit (almost unlimited for students)
    # Sign up: build.nvidia.com (free account)
    # Has: Llama-3.1-70B, DeepSeek-R1, Qwen2.5-Coder, many more
    # ─────────────────────────────────────────────────────────
    def _call_nvidia(self, model: str, prompt: str,
                     system: str, max_tokens: int) -> Optional[str]:
        url  = "https://integrate.api.nvidia.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._config['nvidia_api_key']}",
            "Content-Type":  "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens":  max_tokens,
            "stream":      False,
        }
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        logger.warning(f"NVIDIA {r.status_code}: {r.text[:200]}")
        return None

    # ─────────────────────────────────────────────────────────
    # GEMINI — Free tier (15 req/min, 1M tokens/day)
    # Already in JARVIS, key already there
    # ─────────────────────────────────────────────────────────
    def _call_gemini(self, model: str, prompt: str,
                     system: str) -> Optional[str]:
        from google import genai
        client = genai.Client(api_key=self._config["gemini_api_key"])
        resp   = client.models.generate_content(
            model=model,
            contents=f"System: {system}\n\nUser: {prompt}",
        )
        return resp.text if resp and resp.text else None

    # ─────────────────────────────────────────────────────────
    # OPENROUTER — Free tier models (many free models available)
    # Sign up: openrouter.ai (free)
    # ─────────────────────────────────────────────────────────
    def _call_openrouter(self, model: str, prompt: str,
                         system: str, max_tokens: int) -> Optional[str]:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._config['openrouter_api_key']}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "https://jarvis-ai.local",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            "max_tokens": max_tokens,
        }
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        return None

    # ─────────────────────────────────────────────────────────
    # HUGGING FACE — Free inference API
    # Sign up: huggingface.co (free)
    # ─────────────────────────────────────────────────────────
    def _call_huggingface(self, model: str, prompt: str,
                          system: str) -> Optional[str]:
        url = f"https://api-inference.huggingface.co/models/{model}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._config['huggingface_api_key']}",
            "Content-Type":  "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            "max_tokens": 1024,
            "stream":     False,
        }
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        if r.status_code == 200:
            data = r.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"]
        return None

    # ─────────────────────────────────────────────────────────
    # POLLINATIONS — 100% FREE, NO API KEY, NO SIGNUP
    # Just works. Always. Good for fallback.
    # ─────────────────────────────────────────────────────────
    def _call_pollinations(self, prompt: str, system: str) -> Optional[str]:
        url  = "https://text.pollinations.ai/openai"
        payload = {
            "model": "openai",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
        }
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code == 200:
            try:
                return r.json()["choices"][0]["message"]["content"]
            except Exception:
                return r.text if r.text else None
        return None

    # ─────────────────────────────────────────────────────────
    # IMAGE GENERATION (FREE)
    # ─────────────────────────────────────────────────────────
    def generate_image(
        self,
        prompt:   str,
        width:    int = 1024,
        height:   int = 1024,
        save_path: str = None,
    ) -> str:
        """
        Generate image using FREE services.
        Returns path to saved image or URL.

        Tries:
          1. Pollinations.ai (completely free, no key)
          2. Hugging Face FLUX (free with HF key)
        """
        # Try Pollinations first (no key needed)
        try:
            result = self._pollinations_image(prompt, width, height, save_path)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Pollinations image failed: {e}")

        # Try Hugging Face FLUX
        if self._config.get("huggingface_api_key"):
            try:
                result = self._hf_flux_image(prompt, save_path)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"HF FLUX failed: {e}")

        return "Image generation failed — check internet connection"

    def _pollinations_image(self, prompt: str, width: int,
                             height: int, save_path: str = None) -> Optional[str]:
        """Pollinations.ai — completely free image generation."""
        from pathlib import Path
        import hashlib

        encoded = urllib.parse.quote(prompt)
        url     = (f"https://image.pollinations.ai/prompt/{encoded}"
                   f"?width={width}&height={height}&nologo=true")

        r = requests.get(url, timeout=60, stream=True)
        if r.status_code != 200:
            return None

        if not save_path:
            h         = hashlib.md5(prompt.encode()).hexdigest()[:8]
            save_path = str(Path.home() / "Desktop" / f"jarvis_img_{h}.jpg")

        with open(save_path, "wb") as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)

        return save_path

    def _hf_flux_image(self, prompt: str,
                        save_path: str = None) -> Optional[str]:
        """Hugging Face FLUX.1 — free with HF account."""
        from pathlib import Path
        import hashlib

        url  = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-dev"
        headers = {
            "Authorization": f"Bearer {self._config['huggingface_api_key']}",
        }
        r = requests.post(url, headers=headers,
                          json={"inputs": prompt}, timeout=120)
        if r.status_code != 200:
            return None

        if not save_path:
            h         = hashlib.md5(prompt.encode()).hexdigest()[:8]
            save_path = str(Path.home() / "Desktop" / f"jarvis_flux_{h}.jpg")

        with open(save_path, "wb") as f:
            f.write(r.content)
        return save_path


# ── Singleton ──────────────────────────────────────────────
_router: Optional[FreeAIRouter] = None

def get_ai_router() -> FreeAIRouter:
    global _router
    if _router is None:
        _router = FreeAIRouter()
    return _router
