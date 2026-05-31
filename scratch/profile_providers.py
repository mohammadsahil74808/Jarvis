# scratch/profile_providers.py
import time
import json
import requests
import numpy as np

print("[JARVIS API BENCHMARK] Initializing timing benchmarks...")

# Load Keys
try:
    with open("config/api_keys.json", "r", encoding="utf-8") as f:
        keys = json.load(f)
except Exception as e:
    print(f"Error loading keys: {e}")
    keys = {}

gemini_key = keys.get("gemini_api_key", "")
groq_key = keys.get("groq_api_key", "")
nvidia_key = keys.get("nvidia_api_key", "")
openrouter_key = keys.get("openrouter_api_key", "")

# We will run 3 real requests per provider to get stable benchmarks without hitting Rate Limits (RPM)
NUM_RUNS = 3
prompt = "Reply with exactly one word: Hello"

def benchmark_gemini():
    print("Benchmarking Gemini...")
    ttft_list = []
    tokens_sec_list = []
    failures = 0
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:streamGenerateContent?key={gemini_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    for _ in range(NUM_RUNS):
        try:
            t0 = time.perf_counter()
            r = requests.post(url, json=payload, stream=True, timeout=10)
            if r.status_code != 200:
                failures += 1
                continue
            
            first_chunk_time = None
            total_content = ""
            
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    if first_chunk_time is None:
                        first_chunk_time = time.perf_counter()
                        ttft = (first_chunk_time - t0) * 1000.0
                        ttft_list.append(ttft)
                    total_content += chunk.decode("utf-8", errors="ignore")
                    
            end_time = time.perf_counter()
            if first_chunk_time:
                duration = end_time - first_chunk_time
                # Estimate token count (4 chars = 1 token)
                tokens = max(1, len(total_content) // 4)
                tokens_sec = tokens / max(0.1, duration)
                tokens_sec_list.append(tokens_sec)
        except Exception:
            failures += 1
            
        time.sleep(1) # Gap to avoid rate limits
        
    return ttft_list, tokens_sec_list, failures

def benchmark_groq(model):
    print(f"Benchmarking Groq ({model})...")
    ttft_list = []
    tokens_sec_list = []
    failures = 0
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {groq_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True
    }
    
    for _ in range(NUM_RUNS):
        try:
            t0 = time.perf_counter()
            r = requests.post(url, headers=headers, json=payload, stream=True, timeout=10)
            if r.status_code != 200:
                failures += 1
                continue
                
            first_chunk_time = None
            total_content = ""
            for chunk in r.iter_content(chunk_size=256):
                if chunk:
                    if first_chunk_time is None:
                        first_chunk_time = time.perf_counter()
                        ttft = (first_chunk_time - t0) * 1000.0
                        ttft_list.append(ttft)
                    total_content += chunk.decode("utf-8", errors="ignore")
            
            end_time = time.perf_counter()
            if first_chunk_time:
                duration = end_time - first_chunk_time
                tokens = max(1, len(total_content) // 4)
                tokens_sec = tokens / max(0.1, duration)
                tokens_sec_list.append(tokens_sec)
        except Exception:
            failures += 1
            
        time.sleep(1)
        
    return ttft_list, tokens_sec_list, failures

def benchmark_nvidia():
    print("Benchmarking NVIDIA NIM...")
    ttft_list = []
    tokens_sec_list = []
    failures = 0
    
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {nvidia_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "meta/llama-3.1-70b-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "stream": True
    }
    
    for _ in range(NUM_RUNS):
        try:
            t0 = time.perf_counter()
            r = requests.post(url, headers=headers, json=payload, stream=True, timeout=10)
            if r.status_code != 200:
                failures += 1
                continue
                
            first_chunk_time = None
            total_content = ""
            for chunk in r.iter_content(chunk_size=256):
                if chunk:
                    if first_chunk_time is None:
                        first_chunk_time = time.perf_counter()
                        ttft = (first_chunk_time - t0) * 1000.0
                        ttft_list.append(ttft)
                    total_content += chunk.decode("utf-8", errors="ignore")
            
            end_time = time.perf_counter()
            if first_chunk_time:
                duration = end_time - first_chunk_time
                tokens = max(1, len(total_content) // 4)
                tokens_sec = tokens / max(0.1, duration)
                tokens_sec_list.append(tokens_sec)
        except Exception:
            failures += 1
            
        time.sleep(1)
        
    return ttft_list, tokens_sec_list, failures

def benchmark_openrouter():
    print("Benchmarking OpenRouter...")
    ttft_list = []
    tokens_sec_list = []
    failures = 0
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openrouter_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://jarvis-ai.local"
    }
    payload = {
        "model": "meta-llama/llama-3.2-3b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
        "stream": True
    }
    
    for _ in range(NUM_RUNS):
        try:
            t0 = time.perf_counter()
            r = requests.post(url, headers=headers, json=payload, stream=True, timeout=10)
            if r.status_code != 200:
                failures += 1
                continue
                
            first_chunk_time = None
            total_content = ""
            for chunk in r.iter_content(chunk_size=256):
                if chunk:
                    if first_chunk_time is None:
                        first_chunk_time = time.perf_counter()
                        ttft = (first_chunk_time - t0) * 1000.0
                        ttft_list.append(ttft)
                    total_content += chunk.decode("utf-8", errors="ignore")
            
            end_time = time.perf_counter()
            if first_chunk_time:
                duration = end_time - first_chunk_time
                tokens = max(1, len(total_content) // 4)
                tokens_sec = tokens / max(0.1, duration)
                tokens_sec_list.append(tokens_sec)
        except Exception:
            failures += 1
            
        time.sleep(1)
        
    return ttft_list, tokens_sec_list, failures

def benchmark_pollinations():
    print("Benchmarking Pollinations...")
    ttft_list = []
    tokens_sec_list = []
    failures = 0
    
    url = "https://text.pollinations.ai/"
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "stream": True
    }
    
    for _ in range(NUM_RUNS):
        try:
            t0 = time.perf_counter()
            r = requests.post(url, json=payload, stream=True, timeout=10)
            if r.status_code != 200:
                failures += 1
                continue
                
            first_chunk_time = None
            total_content = ""
            for chunk in r.iter_content(chunk_size=256):
                if chunk:
                    if first_chunk_time is None:
                        first_chunk_time = time.perf_counter()
                        ttft = (first_chunk_time - t0) * 1000.0
                        ttft_list.append(ttft)
                    total_content += chunk.decode("utf-8", errors="ignore")
            
            end_time = time.perf_counter()
            if first_chunk_time:
                duration = end_time - first_chunk_time
                tokens = max(1, len(total_content) // 4)
                tokens_sec = tokens / max(0.1, duration)
                tokens_sec_list.append(tokens_sec)
        except Exception:
            failures += 1
            
        time.sleep(1)
        
    return ttft_list, tokens_sec_list, failures

# Run benchmarks
providers = {}
providers["Gemini Live (gemini-2.0-flash)"] = benchmark_gemini()
providers["Groq Llama 3.3 70B"] = benchmark_groq("llama-3.3-70b-versatile")
providers["Groq Llama 3.1 8B"] = benchmark_groq("llama-3.1-8b-instant")
providers["NVIDIA NIM (Llama 3.1 70B)"] = benchmark_nvidia()
providers["OpenRouter (Llama 3.2 3B)"] = benchmark_openrouter()
providers["Pollinations"] = benchmark_pollinations()

print("\n=== BENCHMARK REPORT ===")
for name, (ttfts, t_secs, fails) in providers.items():
    if len(ttfts) > 0:
        avg_ttft = np.mean(ttfts)
        p95_ttft = np.percentile(ttfts, 95)
        avg_tsec = np.mean(t_secs)
    else:
        avg_ttft, p95_ttft, avg_tsec = 0.0, 0.0, 0.0
        
    fail_rate = (fails / NUM_RUNS) * 100.0
    print(f"{name}:")
    print(f"  - Average TTFT: {avg_ttft:.2f} ms")
    print(f"  - P95 TTFT    : {p95_ttft:.2f} ms")
    print(f"  - Tokens/sec  : {avg_tsec:.2f}")
    print(f"  - Failure Rate: {fail_rate:.1f}%")
