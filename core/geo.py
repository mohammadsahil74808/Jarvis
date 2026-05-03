import requests

def get_current_location() -> str:
    """
    Detects the current city based on the public IP address.
    Returns the city name as a string (e.g. "Delhi").
    Falls back to "Delhi" if detection fails.
    """
    try:
        # Using ipinfo.io (Free, HTTPS supported, no key needed)
        res = requests.get("https://ipinfo.io/json", timeout=5)
        if res.status_code == 200:
            data = res.json()
            city = data.get("city")
            if city:
                print(f"[Geo] 📍 Detected location: {city}")
                return city
    except Exception as e:
        print(f"[Geo] ⚠️ Location detection failed: {e}")
    
    return "Delhi" # Default fallback for this specific user
