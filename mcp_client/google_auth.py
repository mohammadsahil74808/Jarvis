import os
import json
import glob
from typing import Optional

TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "drive_token.json")
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
SCOPES = ["https://www.googleapis.com/auth/drive"]

def get_google_drive_token() -> str:
    """
    Safely retrieves a valid Google Drive OAuth 2.0 access token without exposing secrets.
    Checks environment variables and local cached token files (outside git control).
    If expired, attempts automatic silent refresh.
    Raises RuntimeError if manual OAuth setup/authentication is required.
    """
    # 1. Check environment variable override
    env_token = os.getenv("GOOGLE_DRIVE_OAUTH_TOKEN") or os.getenv("GOOGLE_DRIVE_TOKEN") or os.getenv("GOOGLE_OAUTH_TOKEN")
    if env_token and env_token.strip():
        return env_token.strip()

    # 2. Try loading from saved local token file
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        raise RuntimeError("Google Auth SDK library not found. Install google-auth google-auth-oauthlib.")

    creds: Optional[Credentials] = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            creds = None

    # 3. Check validity or refresh if possible
    if creds and creds.valid:
        return str(creds.token)
    elif creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
            return str(creds.token)
        except Exception:
            pass # Refresh failed, will need re-auth

    # 4. If no valid credentials, check if a client_secret file is available and inform user
    secret_files = glob.glob(os.path.join(CONFIG_DIR, "*client_secret*.json")) + glob.glob(os.path.join(CONFIG_DIR, "credentials.json"))
    if not secret_files:
        raise RuntimeError(
            "Google Drive OAuth credentials not found. To configure:\n"
            "1. Create an OAuth Client ID (Desktop app) in Google Cloud Console with Drive API enabled.\n"
            f"2. Save the downloaded JSON as '{os.path.join(CONFIG_DIR, 'client_secret.json')}'.\n"
            "3. Run the interactive authentication helper to generate drive_token.json."
        )
    else:
        raise RuntimeError(
            f"Found OAuth client secret file ({os.path.basename(secret_files[0])}), but no authorized token exists.\n"
            f"Please run interactive login to authorize JARVIS and generate '{TOKEN_FILE}'."
        )

def interactive_oauth_login(client_secret_path: Optional[str] = None) -> str:
    """
    Performs one-time desktop interactive OAuth login and saves token securely to drive_token.json.
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise RuntimeError("google_auth_oauthlib not installed. Cannot run desktop OAuth flow.")

    if not client_secret_path:
        secret_files = glob.glob(os.path.join(CONFIG_DIR, "*client_secret*.json")) + glob.glob(os.path.join(CONFIG_DIR, "credentials.json"))
        if not secret_files:
            raise RuntimeError(f"No client_secret.json found in {CONFIG_DIR}.")
        client_secret_path = secret_files[0]

    flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
    creds = flow.run_local_server(port=0)
    
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    
    return str(creds.token)
