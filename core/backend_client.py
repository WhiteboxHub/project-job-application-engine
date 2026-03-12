"""
Backend Client - Communicates with wbl-backend to fetch weekly workflows.
"""

import requests

from config.settings import settings
from core.logger import logger


class BackendClient:
    """Client for fetching candidate data from the wbl-backend."""

    @staticmethod
    def fetch_pending_candidates() -> dict:
        """
        Fetches the pending candidate run JSON from the backend trigger endpoint.
        Returns the parsed JSON response if successful, or {} on failure/empty.
        """
        if not settings.BACKEND_URL or not settings.TRIGGER_ENDPOINT:
            logger.error(
                "Missing backend API configuration (BACKEND_URL or TRIGGER_ENDPOINT)."
            )
            return {}

        # Merge URL robustly using URL joining to prevent double slashes
        base = settings.BACKEND_URL.rstrip("/")
        endpoint = settings.TRIGGER_ENDPOINT.lstrip("/")
        url = f"{base}/{endpoint}"

        headers = {}
        if settings.INTERNAL_SECRET_KEY:
            headers["Authorization"] = f"Bearer {settings.INTERNAL_SECRET_KEY}"

        logger.info(f"Fetching run_parameters from Backend API: {url}...")

        try:
            response = requests.get(url, headers=headers, timeout=15)
            # Backend may return 404 or empty list if no candidate is pending
            if response.status_code == 200:
                data = response.json()
                # Backend endpoint could return an array, dict, or message string
                if data:
                    logger.info(
                        "Successfully fetched candidate run_parameters from backend."
                    )
                    return data
                else:
                    logger.info("No active candidates to process according to backend.")
                    return {}
            else:
                logger.warning(
                    f"Backend API returned status {response.status_code}: {response.text}"
                )
                return {}

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to communicate with Backend API: {e}")
            return {}


backend_client = BackendClient()
