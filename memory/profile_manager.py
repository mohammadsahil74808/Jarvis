import json
import os
from datetime import datetime

class ProfileManager:
    def __init__(self, profile_path=None):
        if profile_path is None:
            # Default path relative to this file
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.profile_path = os.path.join(base_dir, "memory", "user_profile.json")
        else:
            self.profile_path = profile_path
        
        self.profile_data = {}
        self.load_profile()

    def load_profile(self):
        """Loads profile from JSON or creates default if missing."""
        if not os.path.exists(self.profile_path):
            self.profile_data = self.get_default_profile()
            self.save_profile()
        else:
            try:
                with open(self.profile_path, 'r', encoding='utf-8') as f:
                    self.profile_data = json.load(f)
            except Exception as e:
                print(f"Error loading profile: {e}")
                self.profile_data = self.get_default_profile()

    def save_profile(self):
        """Saves current profile data to JSON."""
        try:
            os.makedirs(os.path.dirname(self.profile_path), exist_ok=True)
            self.profile_data["metadata"] = self.profile_data.get("metadata", {})
            self.profile_data["metadata"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
            with open(self.profile_path, 'w', encoding='utf-8') as f:
                json.dump(self.profile_data, f, indent=2)
        except Exception as e:
            print(f"Error saving profile: {e}")

    def get_age(self):
        """Calculates age automatically from DOB."""
        dob_str = self.profile_data.get("personal_info", {}).get("dob")
        if not dob_str:
            return None
        try:
            dob = datetime.strptime(dob_str, "%Y-%m-%d")
            today = datetime.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            return age
        except Exception:
            return None

    def get_profile(self):
        """Returns the full profile data with calculated age."""
        data = self.profile_data.copy()
        data["personal_info"]["age"] = self.get_age()
        return data

    def update_profile(self, section, key, value):
        """Updates a specific value in the profile and saves."""
        if section not in self.profile_data:
            self.profile_data[section] = {}
        self.profile_data[section][key] = value
        self.save_profile()

    def get_default_profile(self):
        """Returns a skeleton default profile."""
        return {
            "personal_info": {
                "name": "User",
                "dob": "2000-01-01",
                "location": "Unknown",
                "college": "Unknown",
                "college_city": "Unknown",
                "course": "Unknown",
                "specialization": "Unknown"
            },
            "skills": [],
            "interests": [],
            "personality": {"traits": [], "description": ""},
            "preferences": {
                "favorite_color": "Blue",
                "speech_style": "English",
                "tone": "Professional",
                "vibe": "Assistant"
            },
            "routine": {"wake_time": "08:00", "commute": ""},
            "gaming": {"level": "Casual", "priority": "Low"},
            "goals": {},
            "metadata": {"last_updated": ""}
        }

# Singleton instance helper
_manager = None
def get_manager():
    global _manager
    if _manager is None:
        _manager = ProfileManager()
    return _manager
