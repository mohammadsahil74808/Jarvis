# actions/image_generator.py

import os
import sys
import time
from pathlib import Path
from datetime import datetime
from huggingface_hub import InferenceClient

# Fix path for imports
from core.config import BASE_DIR, get_huggingface_api_key
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

def generate_image(
    parameters:     dict,
    player          = None,
    session_memory  = None,
) -> str:
    """
    Generates an image using Hugging Face InferenceClient.
    - Models: FLUX.1-schnell (Main) -> SDXL (Fallback) -> SD 2.1
    - Saves locally with timestamp
    - Opens automatically
    """
    prompt_text = parameters.get("prompt_text") or parameters.get("prompt")
    
    if not prompt_text:
        return "I need a prompt to generate an image, sir."

    api_token = get_huggingface_api_key()
    if not api_token:
        return "Hugging Face API token is not configured, sir."

    # Models to try in order of priority
    models = [
        "black-forest-labs/FLUX.1-schnell",
        "stabilityai/stable-diffusion-xl-base-1.0",
        "stabilityai/stable-diffusion-2-1",
        "prompthero/openjourney"
    ]

    client = InferenceClient(api_key=api_token)
    
    if player:
        player.write_log(f"[IMAGE] Target: {prompt_text}")

    for model_id in models:
        try:
            if player:
                player.write_log(f"[IMAGE] Attempting model: {model_id}...")
            print(f"[IMAGE] Using model: {model_id}")

            # Use InferenceClient for text_to_image
            image = client.text_to_image(
                prompt_text,
                model=model_id
            )

            # Prepare storage
            output_dir = BASE_DIR / "generated_images"
            output_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"generated_{timestamp}.png"
            filepath = output_dir / filename
            
            # Save the image object (PIL Image)
            image.save(str(filepath))
            
            print(f"[IMAGE] Saved: {filepath}")
            if player:
                player.write_log(f"[IMAGE] Saved: {filename}")
            
            # Open image automatically (Windows)
            try:
                os.startfile(str(filepath))
            except Exception as e:
                print(f"[IMAGE] Failed to auto-open: {e}")

            return f"Image generated successfully sir. I've used {model_id} and opened the result for you."

        except Exception as e:
            error_str = str(e)
            print(f"[IMAGE] Model {model_id} failed: {error_str}")
            if "503" in error_str or "loading" in error_str.lower():
                if player:
                    player.write_log(f"[IMAGE] Model {model_id} is loading, trying fallback...")
                continue
            elif "403" in error_str or "401" in error_str:
                 if player:
                    player.write_log(f"[IMAGE] Access denied for {model_id}, skipping...")
                 continue
            continue

    return "Image generation failed sir. All models are currently busy or unavailable on the Hugging Face free tier."

if __name__ == "__main__":
    # Quick test
    res = generate_image({"prompt_text": "A cybernetic wolf in a neon city"})
    print(res)
