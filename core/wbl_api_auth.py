"""
Obtain Bearer tokens for wbl-backend API calls (workflow logs, etc.).

Priority:
1. API_ACCESS_TOKEN from .env (static JWT)
2. Login via AUTH_URL + AUTH_USERNAME + AUTH_PASSWORD
"""

from __future__ import annotations

import requests

from config.settings import settings
from core.logger import logger

_cached_token: str | None = None


def get_wbl_bearer_token(*, force_refresh: bool = False) -> str | None:
    """Return a JWT suitable for Authorization: Bearer ..."""
    global _cached_token

    if settings.API_ACCESS_TOKEN:
        return settings.API_ACCESS_TOKEN.strip()

    if _cached_token and not force_refresh:
        return _cached_token

    if not all(
        [
            settings.AUTH_URL,
            settings.AUTH_USERNAME,
            settings.AUTH_PASSWORD,
        ]
    ):
        return None

    try:
        payload = {
            "username": settings.AUTH_USERNAME,
            "password": settings.AUTH_PASSWORD,
        }
        response = requests.post(settings.AUTH_URL, data=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
        token = (
            data.get("access_token")
            or data.get("token")
            or data.get("data", {}).get("token")
            or data.get("result", {}).get("access_token")
        )
        if token:
            _cached_token = token
            logger.info("WBL API access token obtained successfully.")
            return token
        logger.error(f"Login response missing token field: {data}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"WBL API login failed: {e}")
        return None


def build_api_headers(json_body: bool = True) -> dict:
    """
    Headers for BACKEND_URL requests.
    Uses JWT when available; falls back to Bearer INTERNAL_SECRET_KEY or X-Internal-Secret.
    """
    headers: dict = {}
    if json_body:
        headers["Content-Type"] = "application/json"

    token = get_wbl_bearer_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
        return headers

    if settings.SCHEDULER_INTERNAL_SECRET:
        headers["X-Internal-Secret"] = settings.SCHEDULER_INTERNAL_SECRET
        return headers

    if settings.INTERNAL_SECRET_KEY:
        headers["Authorization"] = f"Bearer {settings.INTERNAL_SECRET_KEY}"

    return headers
