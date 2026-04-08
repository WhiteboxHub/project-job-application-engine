import requests

from config.settings import settings
from core.logger import logger


class AuthService:
    """Login to wbl-backend and cache JWT (same contract as hiring-cafe-engine)."""

    def __init__(self):
        self.auth_url = settings.AUTH_URL
        self.username = settings.AUTH_USERNAME
        self.password = settings.AUTH_PASSWORD
        self._access_token = None

    def get_access_token(self, force_refresh: bool = False):
        if self._access_token and not force_refresh:
            return self._access_token

        if not all([self.auth_url, self.username, self.password]):
            return None

        try:
            logger.info("Requesting backend access token (login)...")
            payload = {"username": self.username, "password": self.password}
            response = requests.post(self.auth_url, data=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            token = (
                data.get("access_token")
                or data.get("token")
                or data.get("data", {}).get("token")
                or data.get("result", {}).get("access_token")
            )
            if token:
                logger.info("Access token obtained successfully")
                self._access_token = token
                return token
            logger.error(f"Token not found in login response keys: {list(data.keys())}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Login request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during login: {e}")
        return None


auth_service = AuthService()
